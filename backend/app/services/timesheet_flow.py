from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssignmentStatus,
    AttendanceRecord,
    AttendanceStatus,
    JobOrder,
    Shift,
    ShiftAssignment,
    TimesheetEntry,
    TimesheetStatus,
)
from app.services.payroll_calc import compute_timesheet_pay


async def ensure_timesheet_for_assignment(
    db: AsyncSession,
    assignment: ShiftAssignment,
    attendance: AttendanceRecord | None,
) -> TimesheetEntry | None:
    if assignment.status not in (AssignmentStatus.completed, AssignmentStatus.confirmed):
        return None
    r = await db.execute(
        select(TimesheetEntry).where(TimesheetEntry.shift_assignment_id == assignment.id)
    )
    existing = r.scalar_one_or_none()
    if existing:
        return existing

    shift = assignment.shift
    job = shift.job_order

    sched_h = (shift.ends_at - shift.starts_at).total_seconds() / 3600.0
    actual_h = attendance.total_hours if attendance and attendance.total_hours else 0.0
    if actual_h <= 0 and attendance and attendance.clock_in_time and attendance.clock_out_time:
        actual_h = (attendance.clock_out_time - attendance.clock_in_time).total_seconds() / 3600.0

    overtime_h = max(0.0, actual_h - sched_h) if sched_h > 0 else 0.0
    gross, ot = compute_timesheet_pay(job, sched_h, actual_h, overtime_h)

    entry = TimesheetEntry(
        job_order_id=job.id,
        shift_id=shift.id,
        worker_id=assignment.worker_id,
        shift_assignment_id=assignment.id,
        attendance_record_id=attendance.id if attendance else None,
        scheduled_hours=round(sched_h, 2),
        actual_hours=round(actual_h, 2),
        overtime_hours=round(ot, 2),
        hourly_rate_snapshot=float(job.hourly_rate or 0),
        per_shift_rate_snapshot=job.per_shift_rate,
        gross_pay=gross,
        status=TimesheetStatus.pending,
    )
    db.add(entry)
    await db.flush()
    return entry


async def mark_assignment_completed_if_clocked(
    db: AsyncSession,
    assignment: ShiftAssignment,
    attendance: AttendanceRecord,
) -> None:
    if attendance.clock_out_time and attendance.status in (
        AttendanceStatus.present,
        AttendanceStatus.late,
        AttendanceStatus.unverified,
    ):
        assignment.status = AssignmentStatus.completed
        await ensure_timesheet_for_assignment(db, assignment, attendance)


def _hours_from_attendance(attendance: AttendanceRecord, shift: Shift) -> tuple[float, float, float]:
    sched_h = (shift.ends_at - shift.starts_at).total_seconds() / 3600.0
    actual_h = float(attendance.total_hours or 0.0)
    if actual_h <= 0 and attendance.clock_in_time and attendance.clock_out_time:
        actual_h = (attendance.clock_out_time - attendance.clock_in_time).total_seconds() / 3600.0
    overtime_h = max(0.0, actual_h - sched_h) if sched_h > 0 else 0.0
    return sched_h, actual_h, overtime_h


async def get_clock_out_pay_summary(
    db: AsyncSession,
    assignment: ShiftAssignment,
    attendance: AttendanceRecord,
    shift: Shift,
    job: JobOrder,
) -> dict:
    """Pay figures for API responses after clock-out; matches timesheet math when a row exists."""
    sched_h, actual_h, overtime_h = _hours_from_attendance(attendance, shift)
    gross_computed, ot_used = compute_timesheet_pay(job, sched_h, actual_h, overtime_h)

    r = await db.execute(
        select(TimesheetEntry).where(TimesheetEntry.shift_assignment_id == assignment.id)
    )
    ts = r.scalar_one_or_none()
    timesheet_created = ts is not None
    gross_pay = float(ts.gross_pay) if ts else gross_computed
    pay_pending_review = attendance.status == AttendanceStatus.flagged or not timesheet_created

    return {
        "total_hours": round(actual_h, 2),
        "actual_hours": round(actual_h, 2),
        "scheduled_hours": round(sched_h, 2),
        "overtime_hours": round(ot_used, 2),
        "gross_pay": gross_pay,
        "timesheet_created": timesheet_created,
        "pay_pending_review": pay_pending_review,
    }
