"""E2EE job-order chat: server stores ciphertext and key wrappers only."""

import base64
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models import (
    AssignmentStatus,
    JobOrder,
    JobOrderChatKeyWrapper,
    JobOrderChatMessage,
    Shift,
    ShiftAssignment,
    User,
    UserChatIdentity,
    UserRole,
)
from app.schemas.job_order_chat import (
    ChatIdentityPut,
    ChatIdentityStatusOut,
    ChatJobRowOut,
    ChatMessageCreate,
    ChatMessageOut,
    ChatParticipantKeyOut,
    ChatParticipantOut,
    ChatWrapperOut,
    ChatWrapperPut,
)
from app.services.job_order_chat_access import (
    list_chat_participants,
    participant_user_ids,
    user_can_access_job_order_chat,
    worker_profile_for_user,
)
from app.services.ta_client_contracts import get_active_contract_for_org, list_contracted_org_ids_for_ta

router = APIRouter(prefix="/job-order-chat", tags=["job-order-chat"])

MAX_CIPHERTEXT_BYTES = 32 * 1024
MAX_WRAPPED_KEY_BYTES = 2048
MAX_IV_BYTES = 32


CHAT_MIGRATION_HINT = (
    "Job messaging tables are missing. Run database migrations: `alembic upgrade head` "
    "(or redeploy with the latest migration that adds job_order_chat_* tables)."
)


async def _assert_chat_schema(db: AsyncSession) -> None:
    """Avoid opaque 500s when Alembic migration 019 has not been applied (covers all chat tables)."""
    for stmt in (
        select(UserChatIdentity.user_id).limit(1),
        select(JobOrderChatKeyWrapper.id).limit(1),
        select(JobOrderChatMessage.id).limit(1),
    ):
        try:
            await db.execute(stmt)
        except (ProgrammingError, OperationalError, DBAPIError) as e:
            raise HTTPException(status_code=503, detail=CHAT_MIGRATION_HINT) from e


async def _last_message_times_safe(db: AsyncSession, job_ids: list[int]) -> dict[int, datetime]:
    if not job_ids:
        return {}
    try:
        r = await db.execute(
            select(JobOrderChatMessage.job_order_id, func.max(JobOrderChatMessage.created_at))
            .where(JobOrderChatMessage.job_order_id.in_(job_ids))
            .group_by(JobOrderChatMessage.job_order_id)
        )
        return {int(row[0]): row[1] for row in r.all() if row[0] is not None and row[1] is not None}
    except (ProgrammingError, OperationalError):
        return {}


async def _require_non_admin_chat_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role == UserRole.admin:
        raise HTTPException(status_code=403, detail="Admins cannot access job-order chat")
    if user.role not in (UserRole.worker, UserRole.client, UserRole.ta):
        raise HTTPException(status_code=403, detail="Not allowed")
    return user


def _b64decode(label: str, data_b64: str, max_len: int) -> bytes:
    try:
        raw = base64.b64decode(data_b64, validate=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 for {label}") from e
    if len(raw) > max_len:
        raise HTTPException(status_code=400, detail=f"{label} too large")
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail=f"{label} empty")
    return raw


async def _get_job_or_404(db: AsyncSession, job_id: int) -> JobOrder:
    job = await db.get(JobOrder, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _job_if_chat_access(db: AsyncSession, user: User, job_id: int) -> JobOrder:
    job = await _get_job_or_404(db, job_id)
    if not await user_can_access_job_order_chat(db, user, job):
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _ta_message_visibility_cutoff(db: AsyncSession, user: User, job: JobOrder) -> datetime | None:
    """If TA got contracted later, hide earlier history from that TA."""
    if user.role != UserRole.ta:
        return None
    contract = await get_active_contract_for_org(db, job.client_org_id)
    if not contract or contract.ta_user_id != user.id:
        return None
    return contract.responded_at or contract.requested_at


@router.get("/me/identity", response_model=ChatIdentityStatusOut)
async def get_my_chat_identity(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_require_non_admin_chat_user)],
):
    await _assert_chat_schema(db)
    row = await db.get(UserChatIdentity, user.id)
    return ChatIdentityStatusOut(registered=row is not None)


@router.put("/me/identity", response_model=ChatIdentityStatusOut)
async def put_my_chat_identity(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_require_non_admin_chat_user)],
    body: ChatIdentityPut,
):
    await _assert_chat_schema(db)
    pk = _b64decode("x25519_public_key", body.x25519_public_key_b64, 64)
    if len(pk) != 32:
        raise HTTPException(status_code=400, detail="x25519 public key must be 32 bytes")
    existing = await db.get(UserChatIdentity, user.id)
    now = datetime.now(timezone.utc)
    if existing:
        existing.x25519_public_key = pk
        existing.updated_at = now
    else:
        db.add(UserChatIdentity(user_id=user.id, x25519_public_key=pk, updated_at=now))
    await db.flush()
    return ChatIdentityStatusOut(registered=True)


@router.get("", response_model=list[ChatJobRowOut])
async def list_chat_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_require_non_admin_chat_user)],
):
    """List jobs without joining chat tables so the list works even before migration 019 (last_at omitted)."""
    if user.role == UserRole.client:
        if not user.client_org_id:
            return []
        q = (
            select(JobOrder)
            .where(JobOrder.client_org_id == user.client_org_id)
            .order_by(JobOrder.updated_at.desc())
        )
    elif user.role == UserRole.ta:
        org_ids = await list_contracted_org_ids_for_ta(db, user.id)
        if not org_ids:
            return []
        q = select(JobOrder).where(JobOrder.client_org_id.in_(org_ids)).order_by(JobOrder.updated_at.desc())
    else:
        wp = await worker_profile_for_user(db, user.id)
        if not wp:
            return []
        r_ids = await db.execute(
            select(JobOrder.id)
            .join(Shift, Shift.job_order_id == JobOrder.id)
            .join(ShiftAssignment, ShiftAssignment.shift_id == Shift.id)
            .where(
                ShiftAssignment.worker_id == wp.id,
                ShiftAssignment.status == AssignmentStatus.confirmed,
            )
            .distinct()
        )
        job_ids = [row[0] for row in r_ids.all()]
        if not job_ids:
            return []
        q = select(JobOrder).where(JobOrder.id.in_(job_ids)).order_by(JobOrder.updated_at.desc())

    r = await db.execute(q)
    jobs = list(r.scalars().all())
    last_map = await _last_message_times_safe(db, [j.id for j in jobs])
    return [
        ChatJobRowOut(
            id=job.id,
            title=job.title,
            status=job.status.value,
            last_message_at=last_map.get(job.id),
        )
        for job in jobs
    ]


@router.get("/{job_id}/participants", response_model=list[ChatParticipantOut])
async def get_participants(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_require_non_admin_chat_user)],
):
    await _assert_chat_schema(db)
    job = await _job_if_chat_access(db, user, job_id)
    parts = await list_chat_participants(db, job)
    return [ChatParticipantOut(user_id=p.user_id, role=p.role, display_name=p.display_name) for p in parts]


@router.get("/{job_id}/participant-keys", response_model=list[ChatParticipantKeyOut])
async def get_participant_public_keys(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_require_non_admin_chat_user)],
):
    await _assert_chat_schema(db)
    job = await _job_if_chat_access(db, user, job_id)
    allowed = await participant_user_ids(db, job)
    if not allowed:
        return []
    r = await db.execute(select(UserChatIdentity).where(UserChatIdentity.user_id.in_(allowed)))
    rows = r.scalars().all()
    return [
        ChatParticipantKeyOut(
            user_id=row.user_id,
            x25519_public_key_b64=base64.b64encode(row.x25519_public_key).decode("ascii"),
        )
        for row in rows
    ]


@router.get("/{job_id}/wrappers/me", response_model=ChatWrapperOut)
async def get_my_wrapper(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_require_non_admin_chat_user)],
):
    await _assert_chat_schema(db)
    await _job_if_chat_access(db, user, job_id)
    r = await db.execute(
        select(JobOrderChatKeyWrapper).where(
            JobOrderChatKeyWrapper.job_order_id == job_id,
            JobOrderChatKeyWrapper.user_id == user.id,
        )
    )
    w = r.scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="No wrapped key for this user yet")
    return ChatWrapperOut(
        user_id=w.user_id,
        wrapped_key_b64=base64.b64encode(w.wrapped_key).decode("ascii"),
    )


@router.put("/{job_id}/wrappers", response_model=ChatWrapperOut)
async def put_wrapper_for_user(
    job_id: int,
    body: ChatWrapperPut,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_require_non_admin_chat_user)],
):
    await _assert_chat_schema(db)
    job = await _job_if_chat_access(db, user, job_id)
    allowed = await participant_user_ids(db, job)
    if user.id not in allowed:
        raise HTTPException(status_code=404, detail="Job not found")
    if body.target_user_id not in allowed:
        raise HTTPException(status_code=400, detail="target_user_id is not a chat participant")
    target_identity = await db.get(UserChatIdentity, body.target_user_id)
    if not target_identity:
        raise HTTPException(status_code=400, detail="Target user has not registered chat keys yet")
    wrapped = _b64decode("wrapped_key", body.wrapped_key_b64, MAX_WRAPPED_KEY_BYTES)

    r = await db.execute(
        select(JobOrderChatKeyWrapper).where(
            JobOrderChatKeyWrapper.job_order_id == job_id,
            JobOrderChatKeyWrapper.user_id == body.target_user_id,
        )
    )
    row = r.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row:
        row.wrapped_key = wrapped
        row.created_at = now
    else:
        row = JobOrderChatKeyWrapper(job_order_id=job_id, user_id=body.target_user_id, wrapped_key=wrapped, created_at=now)
        db.add(row)
    await db.flush()
    return ChatWrapperOut(
        user_id=row.user_id,
        wrapped_key_b64=base64.b64encode(row.wrapped_key).decode("ascii"),
    )


@router.get("/{job_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_require_non_admin_chat_user)],
    since_id: Optional[int] = None,
    before_id: Optional[int] = None,
    limit: int = 50,
):
    await _assert_chat_schema(db)
    job = await _job_if_chat_access(db, user, job_id)
    lim = min(max(limit, 1), 100)
    q = select(JobOrderChatMessage).where(JobOrderChatMessage.job_order_id == job_id)
    ta_cutoff = await _ta_message_visibility_cutoff(db, user, job)
    if ta_cutoff is not None:
        q = q.where(JobOrderChatMessage.created_at >= ta_cutoff)
    if since_id is not None:
        q = q.where(JobOrderChatMessage.id > since_id).order_by(JobOrderChatMessage.id.asc()).limit(lim)
    elif before_id is not None:
        q = q.where(JobOrderChatMessage.id < before_id).order_by(JobOrderChatMessage.id.desc()).limit(lim)
    else:
        q = q.order_by(JobOrderChatMessage.id.desc()).limit(lim)

    r = await db.execute(q)
    msgs = list(r.scalars().all())
    if since_id is None and before_id is None:
        msgs.reverse()
    elif before_id is not None:
        msgs.reverse()
    return [
        ChatMessageOut(
            id=m.id,
            sender_user_id=m.sender_user_id,
            ciphertext_b64=base64.b64encode(m.ciphertext).decode("ascii"),
            iv_b64=base64.b64encode(m.iv).decode("ascii"),
            created_at=m.created_at,
        )
        for m in msgs
    ]


@router.post("/{job_id}/messages", response_model=ChatMessageOut)
async def post_message(
    job_id: int,
    body: ChatMessageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(_require_non_admin_chat_user)],
):
    await _assert_chat_schema(db)
    await _job_if_chat_access(db, user, job_id)
    ct = _b64decode("ciphertext", body.ciphertext_b64, MAX_CIPHERTEXT_BYTES)
    iv = _b64decode("iv", body.iv_b64, MAX_IV_BYTES)
    now = datetime.now(timezone.utc)
    msg = JobOrderChatMessage(
        job_order_id=job_id,
        sender_user_id=user.id,
        ciphertext=ct,
        iv=iv,
        created_at=now,
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg)
    return ChatMessageOut(
        id=msg.id,
        sender_user_id=msg.sender_user_id,
        ciphertext_b64=base64.b64encode(msg.ciphertext).decode("ascii"),
        iv_b64=base64.b64encode(msg.iv).decode("ascii"),
        created_at=msg.created_at,
    )
