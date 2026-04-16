from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import AuditLog, JobOrder, Shift, User, UserRole, WorkerProfile, WorkerStatus
from app.services.audit import log_audit
from app.services.no_show import mark_no_shows_for_shift

router = APIRouter(prefix="/admin", tags=["admin"])


class PersonaBlacklistBody(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


async def _latest_blacklist_reason(db: AsyncSession, user_id: int) -> str | None:
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.action == "persona_blacklisted",
            AuditLog.entity_type == "User",
            AuditLog.entity_id == str(user_id),
        )
        .order_by(AuditLog.id.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row or not isinstance(row.new_values, dict):
        return None
    reason = row.new_values.get("reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    return None


@router.post("/pdpa/user/{user_id}/deactivate")
async def pdpa_deactivate_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.admin))],
):
    """MVP: deactivate account (retention policies apply); hard delete can be Phase 2."""
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(404)
    target.is_active = False
    await log_audit(
        db,
        actor_user_id=user.id,
        action="pdpa_user_deactivate",
        entity_type="User",
        entity_id=str(user_id),
    )
    return {"ok": True}


@router.get("/personas/{persona_role}")
async def list_personas(
    persona_role: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.admin))],
    include_inactive: bool = True,
    q: str | None = None,
):
    role_map = {
        "worker": UserRole.worker,
        "client": UserRole.client,
        "ta": UserRole.ta,
    }
    role_enum = role_map.get(persona_role.strip().lower())
    if role_enum is None:
        raise HTTPException(status_code=400, detail="Invalid persona role")

    query = (q or "").strip().lower()
    out: list[dict] = []
    if role_enum == UserRole.worker:
        stmt = select(WorkerProfile, User).join(User, WorkerProfile.user_id == User.id)
        if not include_inactive:
            stmt = stmt.where(User.is_active.is_(True), WorkerProfile.status == WorkerStatus.active)
        rows = (await db.execute(stmt)).all()
        for worker_profile, worker_user in rows:
            display_name = (worker_profile.full_name or worker_user.display_name or "").strip()
            email = (worker_user.email or "").strip()
            phone = (worker_user.phone or "").strip()
            if query and query not in " ".join(
                [display_name.lower(), email.lower(), phone.lower(), str(worker_user.id)]
            ):
                continue
            out.append(
                {
                    "user_id": worker_user.id,
                    "persona_id": worker_profile.id,
                    "role": "worker",
                    "display_name": display_name,
                    "email": worker_user.email,
                    "phone": worker_user.phone,
                    "is_active": bool(worker_user.is_active),
                    "status": worker_profile.status.value,
                    "blacklist_reason": await _latest_blacklist_reason(db, worker_user.id)
                    if worker_profile.status == WorkerStatus.blacklisted
                    else None,
                }
            )
        return out

    stmt = select(User).where(User.role == role_enum)
    if not include_inactive:
        stmt = stmt.where(User.is_active.is_(True))
    rows = (await db.execute(stmt)).scalars().all()
    for target in rows:
        display_name = (target.display_name or target.username or "").strip()
        email = (target.email or "").strip()
        phone = (target.phone or "").strip()
        if query and query not in " ".join([display_name.lower(), email.lower(), phone.lower(), str(target.id)]):
            continue
        out.append(
            {
                "user_id": target.id,
                "persona_id": None,
                "role": target.role.value,
                "display_name": display_name,
                "email": target.email,
                "phone": target.phone,
                "is_active": bool(target.is_active),
                "status": "active" if target.is_active else "blacklisted",
                "blacklist_reason": await _latest_blacklist_reason(db, target.id) if not target.is_active else None,
            }
        )
    return out


@router.post("/personas/{user_id}/blacklist")
async def blacklist_persona(
    user_id: int,
    body: PersonaBlacklistBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.admin))],
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role not in (UserRole.worker, UserRole.client, UserRole.ta):
        raise HTTPException(status_code=400, detail="Unsupported persona role")

    old_values: dict[str, object] = {"is_active": bool(target.is_active)}
    target.is_active = False
    new_values: dict[str, object] = {"is_active": False}
    if target.role == UserRole.worker:
        result = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == target.id))
        worker = result.scalar_one_or_none()
        if worker:
            old_values["worker_status"] = worker.status.value
            worker.status = WorkerStatus.blacklisted
            new_values["worker_status"] = worker.status.value

    await log_audit(
        db,
        actor_user_id=user.id,
        action="persona_blacklisted",
        entity_type="User",
        entity_id=str(user_id),
        old_values=old_values,
        new_values={**new_values, "reason": body.reason.strip()},
    )
    return {"ok": True}


@router.post("/personas/{user_id}/unblacklist")
async def unblacklist_persona(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.admin))],
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role not in (UserRole.client, UserRole.ta):
        raise HTTPException(status_code=400, detail="Only client/ta can be unblacklisted here")

    old_values: dict[str, object] = {"is_active": bool(target.is_active)}
    target.is_active = True
    await log_audit(
        db,
        actor_user_id=user.id,
        action="persona_unblacklisted",
        entity_type="User",
        entity_id=str(user_id),
        old_values=old_values,
        new_values={"is_active": True},
    )
    return {"ok": True}


@router.post("/shifts/{shift_id}/mark-no-shows")
async def admin_mark_no_shows(
    shift_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    shift = await db.get(Shift, shift_id)
    if not shift:
        raise HTTPException(404)
    job = await db.get(JobOrder, shift.job_order_id)
    n = await mark_no_shows_for_shift(db, shift, job, user.id)
    return {"marked": n}


@router.get("/audit-logs")
async def list_audit(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.admin, UserRole.ta))],
    limit: int = 200,
):
    r = await db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))
    rows = r.scalars().all()
    return [
        {
            "id": a.id,
            "actor_user_id": a.actor_user_id,
            "action": a.action,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "old_values": a.old_values,
            "new_values": a.new_values,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]
