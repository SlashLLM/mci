"""Who may access job-order E2EE chat and participant metadata for key wrapping."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssignmentStatus,
    ClientProfile,
    JobOrder,
    Shift,
    ShiftAssignment,
    User,
    UserRole,
    WorkerProfile,
)
from app.services.ta_client_contracts import get_active_contract_for_org, ta_has_active_contract_with_org


@dataclass(frozen=True)
class ChatParticipant:
    user_id: int
    role: str  # "worker" | "client" | "ta"
    display_name: str


async def worker_profile_for_user(db: AsyncSession, user_id: int) -> WorkerProfile | None:
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user_id))
    return r.scalar_one_or_none()


async def user_can_access_job_order_chat(db: AsyncSession, user: User, job: JobOrder) -> bool:
    if user.role == UserRole.admin:
        return False
    if user.role == UserRole.client:
        return user.client_org_id is not None and user.client_org_id == job.client_org_id
    if user.role == UserRole.ta:
        return await ta_has_active_contract_with_org(db, user.id, job.client_org_id)
    if user.role == UserRole.worker:
        wp = await worker_profile_for_user(db, user.id)
        if not wp:
            return False
        r = await db.execute(
            select(ShiftAssignment.id)
            .join(Shift, ShiftAssignment.shift_id == Shift.id)
            .where(
                Shift.job_order_id == job.id,
                ShiftAssignment.worker_id == wp.id,
                ShiftAssignment.status == AssignmentStatus.confirmed,
            )
            .limit(1)
        )
        return r.scalar_one_or_none() is not None
    return False


async def list_chat_participants(db: AsyncSession, job: JobOrder) -> list[ChatParticipant]:
    """All user_ids that belong in this job chat (for key wrapping)."""
    out: list[ChatParticipant] = []

    # Explicit join — avoid lazy/async selectinload edge cases (MissingGreenlet) on client_profile.
    r_clients = await db.execute(
        select(User, ClientProfile)
        .outerjoin(ClientProfile, ClientProfile.user_id == User.id)
        .where(User.client_org_id == job.client_org_id, User.role == UserRole.client)
    )
    for u, cp in r_clients.all():
        name = (u.display_name or "").strip()
        if not name and cp is not None:
            name = (cp.contact_name or cp.company_name or "").strip()
        out.append(ChatParticipant(user_id=u.id, role="client", display_name=name or f"Client #{u.id}"))

    contract = await get_active_contract_for_org(db, job.client_org_id)
    if contract:
        ta = await db.get(User, contract.ta_user_id)
        if ta and ta.role == UserRole.ta:
            name = (ta.display_name or "").strip() or f"TA #{ta.id}"
            out.append(ChatParticipant(user_id=ta.id, role="ta", display_name=name))

    r_workers = await db.execute(
        select(User, WorkerProfile)
        .join(WorkerProfile, WorkerProfile.user_id == User.id)
        .join(ShiftAssignment, ShiftAssignment.worker_id == WorkerProfile.id)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .where(
            Shift.job_order_id == job.id,
            ShiftAssignment.status == AssignmentStatus.confirmed,
        )
        )
    seen_worker_users: set[int] = set()
    for u, wp in r_workers.all():
        if u.id in seen_worker_users:
            continue
        seen_worker_users.add(u.id)
        name = (u.display_name or "").strip() or (wp.full_name or "").strip() or f"Worker #{wp.id}"
        out.append(ChatParticipant(user_id=u.id, role="worker", display_name=name))

    out.sort(key=lambda p: (p.role != "client", p.role != "ta", p.display_name.lower()))
    return out


async def participant_user_ids(db: AsyncSession, job: JobOrder) -> set[int]:
    return {p.user_id for p in await list_chat_participants(db, job)}
