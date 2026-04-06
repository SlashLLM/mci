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
from app.services.ta_client_contracts import list_contracted_org_ids_for_ta

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
async def dashboard_kpis(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    org_ids: list[int] | None = None
    if user.role == UserRole.ta:
        org_ids = list(await list_contracted_org_ids_for_ta(db, user.id))
        if not org_ids:
            return {
                "active_workers": 0,
                "open_job_orders": 0,
                "upcoming_shifts": 0,
                "aggregate_fill_rate": 0.0,
                "confirmed_assignments": 0,
                "total_shift_slots": 0,
                "no_show_assignments": 0,
            }

    active_workers = await db.scalar(
        select(func.count()).select_from(WorkerProfile).where(WorkerProfile.status == WorkerStatus.active)
    )
    oj = select(func.count()).select_from(JobOrder).where(
        JobOrder.status.in_([JobOrderStatus.open, JobOrderStatus.partially_filled])
    )
    if org_ids is not None:
        oj = oj.where(JobOrder.client_org_id.in_(org_ids))
    open_jobs = await db.scalar(oj)
    now = datetime.now(timezone.utc)
    up = select(func.count()).select_from(Shift).join(JobOrder, Shift.job_order_id == JobOrder.id).where(
        Shift.starts_at > now
    )
    if org_ids is not None:
        up = up.where(JobOrder.client_org_id.in_(org_ids))
    upcoming = await db.scalar(up)
    ts = select(func.coalesce(func.sum(Shift.workers_required), 0)).join(
        JobOrder, Shift.job_order_id == JobOrder.id
    )
    if org_ids is not None:
        ts = ts.where(JobOrder.client_org_id.in_(org_ids))
    total_slots = await db.scalar(ts)
    fl = (
        select(func.count())
        .select_from(ShiftAssignment)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .join(JobOrder, Shift.job_order_id == JobOrder.id)
        .where(ShiftAssignment.status == AssignmentStatus.confirmed)
    )
    if org_ids is not None:
        fl = fl.where(JobOrder.client_org_id.in_(org_ids))
    filled = await db.scalar(fl)
    fill_rate = float(filled or 0) / max(1, int(total_slots or 0))
    ns = (
        select(func.count())
        .select_from(ShiftAssignment)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .join(JobOrder, Shift.job_order_id == JobOrder.id)
        .where(ShiftAssignment.status == AssignmentStatus.no_show)
    )
    if org_ids is not None:
        ns = ns.where(JobOrder.client_org_id.in_(org_ids))
    no_shows = await db.scalar(ns)
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
    stmt = select(JobOrder)
    if user.role == UserRole.ta:
        org_ids = list(await list_contracted_org_ids_for_ta(db, user.id))
        if not org_ids:
            return {}
        stmt = stmt.where(JobOrder.client_org_id.in_(org_ids))
    r = await db.execute(stmt)
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
