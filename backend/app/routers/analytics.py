from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import (
    AssignmentStatus,
    JobOrder,
    JobOrderStatus,
    Shift,
    ShiftAssignment,
    User,
    UserRole,
    WorkerProfile,
    WorkerStatus,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
async def dashboard_kpis(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    active_workers = await db.scalar(
        select(func.count()).select_from(WorkerProfile).where(WorkerProfile.status == WorkerStatus.active)
    )
    open_jobs = await db.scalar(
        select(func.count())
        .select_from(JobOrder)
        .where(JobOrder.status.in_([JobOrderStatus.open, JobOrderStatus.partially_filled]))
    )
    now = datetime.now(timezone.utc)
    upcoming = await db.scalar(select(func.count()).select_from(Shift).where(Shift.starts_at > now))
    total_slots = await db.scalar(select(func.coalesce(func.sum(Shift.workers_required), 0)))
    filled = await db.scalar(
        select(func.count())
        .select_from(ShiftAssignment)
        .where(ShiftAssignment.status == AssignmentStatus.confirmed)
    )
    fill_rate = float(filled or 0) / max(1, int(total_slots or 0))
    no_shows = await db.scalar(
        select(func.count())
        .select_from(ShiftAssignment)
        .where(ShiftAssignment.status == AssignmentStatus.no_show)
    )
    return {
        "active_workers": int(active_workers or 0),
        "open_job_orders": int(open_jobs or 0),
        "upcoming_shifts": int(upcoming or 0),
        "aggregate_fill_rate": round(fill_rate, 3),
        "confirmed_assignments": int(filled or 0),
        "total_shift_slots": int(total_slots or 0),
        "no_show_assignments": int(no_shows or 0),
    }


@router.get("/fill-rate-by-job-type")
async def fill_rate_by_job_type(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    r = await db.execute(select(JobOrder))
    jobs = r.scalars().all()
    by_type: dict[str, dict[str, float]] = {}
    for j in jobs:
        slots = await db.scalar(
            select(func.coalesce(func.sum(Shift.workers_required), 0)).where(Shift.job_order_id == j.id)
        )
        filled = await db.scalar(
            select(func.count())
            .select_from(ShiftAssignment)
            .join(Shift, ShiftAssignment.shift_id == Shift.id)
            .where(Shift.job_order_id == j.id, ShiftAssignment.status == AssignmentStatus.confirmed)
        )
        d = by_type.setdefault(j.job_type, {"slots": 0, "filled": 0})
        d["slots"] += int(slots or 0)
        d["filled"] += int(filled or 0)
    out = {}
    for k, v in by_type.items():
        out[k] = round(v["filled"] / max(1, v["slots"]), 3)
    return out
