from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import (
    AttendanceRecord,
    JobOrder,
    Shift,
    TimesheetEntry,
    TimesheetStatus,
    User,
    UserRole,
    WorkerProfile,
)
from app.services.audit import log_audit

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


class DisputeBody(BaseModel):
    note: str


def _timesheet_row(
    t: TimesheetEntry,
    wp: WorkerProfile,
    sh: Shift,
    att: AttendanceRecord | None,
    job: JobOrder,
) -> dict:
    return {
        "id": t.id,
        "job_order_id": t.job_order_id,
        "job_title": job.title,
        "shift_id": t.shift_id,
        "worker_id": t.worker_id,
        "scheduled_hours": t.scheduled_hours,
        "actual_hours": t.actual_hours,
        "overtime_hours": t.overtime_hours,
        "gross_pay": t.gross_pay,
        "status": t.status.value,
        "dispute_flag": t.dispute_flag,
        "dispute_note": t.dispute_note,
        "worker_name": wp.full_name or "",
        "shift_starts_at": sh.starts_at.isoformat(),
        "shift_ends_at": sh.ends_at.isoformat(),
        "clock_in_at": att.clock_in_time.isoformat() if att and att.clock_in_time else None,
        "clock_out_at": att.clock_out_time.isoformat() if att and att.clock_out_time else None,
    }


@router.get("")
async def list_timesheets(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.client, UserRole.admin, UserRole.worker))],
):
    base = (
        select(TimesheetEntry, WorkerProfile, Shift, AttendanceRecord, JobOrder)
        .join(WorkerProfile, TimesheetEntry.worker_id == WorkerProfile.id)
        .join(Shift, TimesheetEntry.shift_id == Shift.id)
        .join(JobOrder, TimesheetEntry.job_order_id == JobOrder.id)
        .outerjoin(AttendanceRecord, TimesheetEntry.attendance_record_id == AttendanceRecord.id)
    )

    if user.role == UserRole.worker:
        r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
        wp = r.scalar_one_or_none()
        if not wp:
            return []
        r2 = await db.execute(
            base.where(TimesheetEntry.worker_id == wp.id).order_by(TimesheetEntry.id.desc())
        )
    elif user.role == UserRole.client:
        r2 = await db.execute(
            base.where(JobOrder.client_org_id == user.client_org_id).order_by(TimesheetEntry.id.desc())
        )
    else:
        r2 = await db.execute(base.order_by(TimesheetEntry.id.desc()))

    return [_timesheet_row(t, wp, sh, att, job) for t, wp, sh, att, job in r2.all()]


@router.post("/{entry_id}/employer-endorse")
async def employer_endorse(
    entry_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    t = await db.get(TimesheetEntry, entry_id)
    if not t:
        raise HTTPException(404)
    job = await db.get(JobOrder, t.job_order_id)
    if job.client_org_id != user.client_org_id:
        raise HTTPException(403)
    t.status = TimesheetStatus.employer_endorsed
    t.employer_endorsed_at = datetime.now(timezone.utc)
    t.employer_endorsed_by_user_id = user.id
    await log_audit(
        db,
        actor_user_id=user.id,
        action="timesheet_employer_endorse",
        entity_type="TimesheetEntry",
        entity_id=str(entry_id),
    )
    return {"ok": True}


@router.post("/{entry_id}/dispute")
async def dispute_timesheet(
    entry_id: int,
    body: DisputeBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client, UserRole.ta, UserRole.admin))],
):
    t = await db.get(TimesheetEntry, entry_id)
    if not t:
        raise HTTPException(404)
    if user.role == UserRole.client:
        job = await db.get(JobOrder, t.job_order_id)
        if job.client_org_id != user.client_org_id:
            raise HTTPException(403)
    t.dispute_flag = True
    t.dispute_note = body.note
    await log_audit(
        db,
        actor_user_id=user.id,
        action="timesheet_dispute",
        entity_type="TimesheetEntry",
        entity_id=str(entry_id),
        new_values={"note": body.note},
    )
    return {"ok": True}


@router.post("/{entry_id}/ta-verify")
async def ta_verify(
    entry_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    t = await db.get(TimesheetEntry, entry_id)
    if not t:
        raise HTTPException(404)
    t.status = TimesheetStatus.ta_verified
    t.ta_verified_at = datetime.now(timezone.utc)
    t.ta_verified_by_user_id = user.id
    await log_audit(
        db,
        actor_user_id=user.id,
        action="timesheet_ta_verify",
        entity_type="TimesheetEntry",
        entity_id=str(entry_id),
    )
    return {"ok": True}


@router.post("/bulk-ta-verify")
async def bulk_ta_verify(
    entry_ids: list[int],
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    for eid in entry_ids:
        t = await db.get(TimesheetEntry, eid)
        if t:
            t.status = TimesheetStatus.ta_verified
            t.ta_verified_at = datetime.now(timezone.utc)
            t.ta_verified_by_user_id = user.id
    return {"ok": True, "count": len(entry_ids)}
