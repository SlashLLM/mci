from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    AssignmentStatus,
    AttendanceRecord,
    AttendanceStatus,
    ShiftAssignment,
    User,
    WorkerProfile,
    WorkerStatus,
)
from app.services.audit import log_audit
from app.services.email_outbound import send_support_email
from app.services.notifications import notify_user


async def record_absence_strike_if_eligible(
    db: AsyncSession,
    assignment: ShiftAssignment,
    attendance: AttendanceRecord,
    wp: WorkerProfile | None,
    *,
    actor_user_id: int | None,
) -> None:
    """One strike per shift assignment when worker is absent without clock-in (idempotent)."""
    if attendance.absence_strike_recorded_at is not None:
        return
    if attendance.clock_in_time:
        return
    if attendance.status != AttendanceStatus.absent:
        return
    if assignment.status not in (AssignmentStatus.confirmed, AssignmentStatus.no_show):
        return
    if not wp:
        return

    now = datetime.now(timezone.utc)
    attendance.absence_strike_recorded_at = now
    wp.no_show_count = (wp.no_show_count or 0) + 1

    settings = get_settings()
    support_hint = (
        f" Please contact support at {settings.support_email}."
        if settings.support_email
        else " Please contact support."
    )

    if wp.no_show_count >= 3:
        wp.status = WorkerStatus.blacklisted
        await log_audit(
            db,
            actor_user_id=actor_user_id,
            action="auto_blacklist",
            entity_type="WorkerProfile",
            entity_id=str(wp.id),
            new_values={"reason": "absence_strike_threshold", "count": wp.no_show_count},
        )
        u = await db.get(User, wp.user_id)
        if u:
            await notify_user(
                db,
                u.id,
                title="Account restricted",
                body=f"Your account has been restricted after repeated absences.{support_hint}",
            )
        send_support_email(
            subject=f"[MCI] Worker blacklisted after absences (profile {wp.id})",
            body=(
                f"Worker profile id: {wp.id}\n"
                f"Name: {wp.full_name}\n"
                f"Absence strikes (no_show_count): {wp.no_show_count}\n"
                f"Assignment id: {assignment.id}\n"
            ),
        )

    await db.flush()
