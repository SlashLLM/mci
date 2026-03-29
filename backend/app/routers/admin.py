from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import AuditLog, JobOrder, Shift, User, UserRole
from app.services.audit import log_audit
from app.services.no_show import mark_no_shows_for_shift

router = APIRouter(prefix="/admin", tags=["admin"])


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
