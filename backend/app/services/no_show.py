from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssignmentStatus,
    AttendanceRecord,
    AttendanceStatus,
    JobOrder,
    Shift,
    ShiftAssignment,
    User,
    WorkerProfile,
    WorkerStatus,
)
from app.services.audit import log_audit
from app.services.notifications import notify_user


async def mark_no_shows_for_shift(
    db: AsyncSession,
    shift: Shift,
    job: JobOrder,
    actor_user_id: int | None,
) -> int:
    """Mark confirmed workers without clock-in after grace as no-show."""
    grace = timedelta(minutes=job.no_show_grace_minutes)
    cutoff = shift.starts_at
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    deadline = cutoff + grace
    now = datetime.now(timezone.utc)
    if now < deadline:
        return 0

    r = await db.execute(
        select(ShiftAssignment).where(
            ShiftAssignment.shift_id == shift.id,
            ShiftAssignment.status == AssignmentStatus.confirmed,
        )
    )
    assigns = r.scalars().all()
    count = 0
    for a in assigns:
        ar = await db.execute(
            select(AttendanceRecord).where(AttendanceRecord.shift_assignment_id == a.id)
        )
        att = ar.scalar_one_or_none()
        if att and att.clock_in_time:
            continue
        a.status = AssignmentStatus.no_show
        if not att:
            att = AttendanceRecord(shift_assignment_id=a.id, status=AttendanceStatus.absent)
            db.add(att)
        else:
            att.status = AttendanceStatus.absent
        wp = await db.get(WorkerProfile, a.worker_id)
        if wp:
            wp.no_show_count = (wp.no_show_count or 0) + 1
            if wp.no_show_count >= 3:
                wp.status = WorkerStatus.blacklisted
                await log_audit(
                    db,
                    actor_user_id=actor_user_id,
                    action="auto_blacklist",
                    entity_type="WorkerProfile",
                    entity_id=str(wp.id),
                    new_values={"reason": "no_show_threshold", "count": wp.no_show_count},
                )
            u = await db.get(User, wp.user_id)
            if u:
                await notify_user(
                    db,
                    u.id,
                    title="Marked as no-show",
                    body=f"You were marked absent for shift {shift.id}.",
                )
        count += 1
    return count
