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
    UserRole,
    WorkerProfile,
    WorkerStatus,
)
from app.services.absence_strikes import record_absence_strike_if_eligible
from app.services.notifications import notify_user
from app.services.ta_client_contracts import get_active_contract_for_org


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
    client_ids_r = await db.execute(
        select(User.id).where(
            User.role == UserRole.client,
            User.client_org_id == job.client_org_id,
        )
    )
    stakeholder_ids: set[int] = set(client_ids_r.scalars().all())
    contract = await get_active_contract_for_org(db, job.client_org_id)
    if contract:
        ta_id_r = await db.execute(
            select(User.id).where(
                User.id == contract.ta_user_id,
                User.role == UserRole.ta,
            )
        )
        ta_id = ta_id_r.scalar_one_or_none()
        if ta_id is not None:
            stakeholder_ids.add(ta_id)
    count = 0
    for a in assigns:
        ar = await db.execute(
            select(AttendanceRecord).where(AttendanceRecord.shift_assignment_id == a.id)
        )
        att = ar.scalar_one_or_none()
        if att and att.clock_in_time:
            continue
        if not att:
            att = AttendanceRecord(shift_assignment_id=a.id, status=AttendanceStatus.absent)
            db.add(att)
            await db.flush()
        else:
            att.status = AttendanceStatus.absent
        wp = await db.get(WorkerProfile, a.worker_id)
        await record_absence_strike_if_eligible(db, a, att, wp, actor_user_id=actor_user_id)
        a.status = AssignmentStatus.no_show
        if wp and wp.status != WorkerStatus.blacklisted:
            u = await db.get(User, wp.user_id)
            if u:
                await notify_user(
                    db,
                    u.id,
                    title="Marked as no-show",
                    body=f"You were marked absent for shift {shift.id}.",
                )
        worker_label = (wp.full_name or "").strip() if wp else ""
        if not worker_label:
            worker_label = f"Worker #{a.worker_id}"
        payload = {
            "type": "worker_no_show",
            "job_order_id": job.id,
            "shift_id": shift.id,
            "assignment_id": a.id,
            "worker_id": a.worker_id,
        }
        for uid in stakeholder_ids:
            await notify_user(
                db,
                uid,
                title="Worker marked no-show",
                body=f"{worker_label} was marked no-show for shift {shift.id} ({job.title}).",
                payload=payload,
            )
        count += 1
    return count
