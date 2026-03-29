from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import (
    AssignmentStatus,
    AttendanceRecord,
    AttendanceStatus,
    JobOrder,
    PreferredWorker,
    Rating,
    Shift,
    ShiftAssignment,
    User,
    UserRole,
    WorkerProfile,
    WorkerTier,
)
from app.auth.attendance_qr_tokens import create_attendance_qr_token
from app.services.attendance_rules import clock_in_time_is_late, is_late_window_without_clock_in

router = APIRouter(prefix="/client", tags=["client-portal"])


async def _live_worker_row(
    db: AsyncSession,
    shift: Shift,
    assignment: ShiftAssignment,
    now: datetime,
) -> dict:
    ar = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.shift_assignment_id == assignment.id)
    )
    att = ar.scalar_one_or_none()
    wp = await db.get(WorkerProfile, assignment.worker_id)
    has_clock_in = bool(att and att.clock_in_time)
    stored = att.status if att else None
    derived_late = bool(
        att and att.clock_in_time and clock_in_time_is_late(att.clock_in_time, shift.starts_at)
    )
    not_in_late = is_late_window_without_clock_in(now, shift.starts_at, has_clock_in)
    show_late_badge = bool(derived_late or (stored == AttendanceStatus.late) or not_in_late)
    attendance_status: str | None
    if att:
        if derived_late or stored == AttendanceStatus.late:
            attendance_status = AttendanceStatus.late.value
        elif stored:
            attendance_status = stored.value
        else:
            attendance_status = AttendanceStatus.unverified.value
    else:
        attendance_status = None
    return {
        "worker_name": wp.full_name if wp else "",
        "assignment_id": assignment.id,
        "shift_id": shift.id,
        "scheduled_start": shift.starts_at.isoformat(),
        "clock_in": att.clock_in_time.isoformat() if att and att.clock_in_time else None,
        "clock_out": att.clock_out_time.isoformat() if att and att.clock_out_time else None,
        "geofence_ok": att.clock_in_geofence_valid if att else None,
        "photo_in": att.clock_in_photo_url if att else None,
        "attendance_status": attendance_status,
        "show_late_badge": show_late_badge,
        "not_checked_in_late": not_in_late,
    }


@router.post("/preferred-workers/{worker_profile_id}")
async def flag_preferred(
    worker_profile_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    if not user.client_org_id:
        raise HTTPException(400)
    existing = await db.execute(
        select(PreferredWorker).where(
            PreferredWorker.client_org_id == user.client_org_id,
            PreferredWorker.worker_id == worker_profile_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"ok": True}
    db.add(PreferredWorker(client_org_id=user.client_org_id, worker_id=worker_profile_id))
    return {"ok": True}


@router.get("/job-orders/{job_id}/live-attendance")
async def live_attendance(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    job = await db.get(JobOrder, job_id)
    if not job or job.client_org_id != user.client_org_id:
        raise HTTPException(404)
    r = await db.execute(select(Shift).where(Shift.job_order_id == job_id))
    shifts = r.scalars().all()
    now = datetime.now(timezone.utc)
    active = [s for s in shifts if s.starts_at <= now <= s.ends_at]
    if not active:
        active = shifts[-1:] if shifts else []
    out = []
    for s in active:
        r2 = await db.execute(
            select(ShiftAssignment)
            .options(selectinload(ShiftAssignment.shift))
            .where(
                ShiftAssignment.shift_id == s.id,
                ShiftAssignment.status == AssignmentStatus.confirmed,
            )
        )
        for a in r2.scalars().all():
            row = await _live_worker_row(db, s, a, now)
            out.append({k: v for k, v in row.items() if k != "shift_id"})
    return {"shifts": [s.id for s in active], "workers": out}


@router.get("/job-orders/{job_id}/shift-attendance")
async def shift_attendance(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    job = await db.get(JobOrder, job_id)
    if not job or job.client_org_id != user.client_org_id:
        raise HTTPException(404)
    r = await db.execute(select(Shift).where(Shift.job_order_id == job_id))
    shifts = sorted(r.scalars().all(), key=lambda x: x.starts_at)
    now = datetime.now(timezone.utc)
    shift_blocks: list[dict] = []
    for s in shifts:
        r2 = await db.execute(
            select(ShiftAssignment)
            .where(
                ShiftAssignment.shift_id == s.id,
                ShiftAssignment.status == AssignmentStatus.confirmed,
            )
        )
        workers: list[dict] = []
        for a in r2.scalars().all():
            workers.append(await _live_worker_row(db, s, a, now))
        shift_blocks.append(
            {
                "shift_id": s.id,
                "starts_at": s.starts_at.isoformat(),
                "ends_at": s.ends_at.isoformat(),
                "workers": workers,
            }
        )
    return {"job_id": job_id, "shifts": shift_blocks}


@router.get("/job-orders/{job_id}/shifts/{shift_id}/attendance-qr")
async def attendance_qr_tokens(
    job_id: int,
    shift_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    job = await db.get(JobOrder, job_id)
    if not job or job.client_org_id != user.client_org_id:
        raise HTTPException(404)
    shift = await db.get(Shift, shift_id)
    if not shift or shift.job_order_id != job_id:
        raise HTTPException(404)
    return {
        "clock_in_token": create_attendance_qr_token(
            job_id=job_id,
            shift_id=shift_id,
            action="in",
            shift_ends_at=shift.ends_at,
        ),
        "clock_out_token": create_attendance_qr_token(
            job_id=job_id,
            shift_id=shift_id,
            action="out",
            shift_ends_at=shift.ends_at,
        ),
    }


class RatingIn(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: str | None = None


@router.post("/assignments/{assignment_id}/rate")
async def rate_worker(
    assignment_id: int,
    body: RatingIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    a = await db.get(ShiftAssignment, assignment_id)
    if not a:
        raise HTTPException(404)
    shift = await db.get(Shift, a.shift_id)
    job = await db.get(JobOrder, shift.job_order_id)
    if job.client_org_id != user.client_org_id:
        raise HTTPException(403)
    existing = await db.execute(
        select(Rating).where(
            Rating.shift_assignment_id == assignment_id,
            Rating.rated_by_user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, detail="Already rated")
    db.add(
        Rating(
            shift_assignment_id=assignment_id,
            worker_id=a.worker_id,
            rated_by_user_id=user.id,
            stars=body.stars,
            comment=body.comment,
        )
    )
    await db.flush()
    r = await db.execute(select(Rating).where(Rating.worker_id == a.worker_id))
    all_r = r.scalars().all()
    avg = sum(x.stars for x in all_r) / max(1, len(all_r))
    wp = await db.get(WorkerProfile, a.worker_id)
    if wp:
        wp.rating_avg = avg
        wp.points = (wp.points or 0) + 10
        if wp.rating_avg >= 4.5:
            wp.tier = WorkerTier.elite
        elif wp.rating_avg >= 3.5:
            wp.tier = WorkerTier.preferred
        else:
            wp.tier = WorkerTier.standard
    return {"ok": True, "new_avg": avg}
