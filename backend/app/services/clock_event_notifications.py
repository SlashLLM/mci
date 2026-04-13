"""Notify client org users (and contracted TA) when a worker clocks in or out."""

from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobOrder, Shift, ShiftAssignment, User, UserRole, WorkerProfile
from app.services.notifications import notify_user
from app.services.ta_client_contracts import get_active_contract_for_org


async def notify_stakeholders_of_worker_clock_event(
    db: AsyncSession,
    *,
    job: JobOrder,
    shift: Shift,
    assignment: ShiftAssignment,
    attendance_record_id: int,
    event: Literal["clock_in", "clock_out"],
    clock_time: datetime,
) -> None:
    wp = await db.get(WorkerProfile, assignment.worker_id)
    worker_label = (wp.full_name or "").strip() if wp else ""
    if not worker_label:
        worker_label = f"Worker #{assignment.worker_id}"

    payload_type = "worker_clock_in" if event == "clock_in" else "worker_clock_out"
    title = "Worker clocked in" if event == "clock_in" else "Worker clocked out"
    if event == "clock_in":
        body = f"{worker_label} clocked in for shift {shift.id} ({job.title}) at {clock_time.isoformat()}."
    else:
        body = f"{worker_label} clocked out for shift {shift.id} ({job.title}) at {clock_time.isoformat()}."
    payload = {
        "type": payload_type,
        "job_order_id": job.id,
        "shift_id": shift.id,
        "assignment_id": assignment.id,
        "attendance_record_id": attendance_record_id,
    }

    recipient_ids: set[int] = set()
    r_clients = await db.execute(
        select(User.id).where(
            User.role == UserRole.client,
            User.client_org_id == job.client_org_id,
        )
    )
    recipient_ids.update(r_clients.scalars().all())

    contract = await get_active_contract_for_org(db, job.client_org_id)
    if contract:
        r_ta = await db.execute(
            select(User.id).where(
                User.id == contract.ta_user_id,
                User.role == UserRole.ta,
            )
        )
        ta_id = r_ta.scalar_one_or_none()
        if ta_id is not None:
            recipient_ids.add(ta_id)

    for uid in recipient_ids:
        await notify_user(db, uid, title=title, body=body, payload=payload)
