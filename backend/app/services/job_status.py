from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssignmentStatus, JobOrder, JobOrderStatus, Shift, ShiftAssignment


async def refresh_job_order_fill_status(db: AsyncSession, job: JobOrder) -> None:
    """Update open / partially_filled / fully_filled from confirmed assignments.

    Does not run for draft, cancelled, completed, or unpublished jobs — avoids
    overwriting draft before TA publish (see job_orders._to_out + session commit).
    """
    if job.status in (
        JobOrderStatus.draft,
        JobOrderStatus.cancelled,
        JobOrderStatus.completed,
    ):
        return
    if job.published_at is None:
        return

    total_needed = await db.scalar(
        select(func.coalesce(func.sum(Shift.workers_required), 0)).where(Shift.job_order_id == job.id)
    )
    total_filled = await db.scalar(
        select(func.count(ShiftAssignment.id))
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .where(
            Shift.job_order_id == job.id,
            ShiftAssignment.status == AssignmentStatus.confirmed,
        )
    )
    tn = int(total_needed or 0)
    tf = int(total_filled or 0)
    if tn == 0:
        return
    if tf == 0:
        job.status = JobOrderStatus.open
    elif tf < tn:
        job.status = JobOrderStatus.partially_filled
    else:
        job.status = JobOrderStatus.fully_filled
