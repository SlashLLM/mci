from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssignmentStatus,
    JobOrder,
    JobOrderStatus,
    Shift,
    ShiftAssignment,
    ShiftOffer,
    ShiftOfferStatus,
    User,
)
from app.services.matching import rank_workers_for_shift, select_dispatch_candidates
from app.services.notifications import notify_user


async def publish_job_order(db: AsyncSession, job: JobOrder) -> None:
    job.status = JobOrderStatus.open
    job.published_at = datetime.now(timezone.utc)
    await db.flush()
    for shift in job.shifts:
        await dispatch_shift(db, job, shift)


async def dispatch_shift(db: AsyncSession, job: JobOrder, shift: Shift) -> None:
    ranked = await rank_workers_for_shift(db, job, shift)
    candidates = await select_dispatch_candidates(db, job, shift, ranked)
    expires = datetime.now(timezone.utc) + timedelta(minutes=job.acceptance_window_minutes)
    for worker, score in candidates:
        taken = await db.execute(
            select(ShiftAssignment.id).where(
                ShiftAssignment.shift_id == shift.id,
                ShiftAssignment.worker_id == worker.id,
                ShiftAssignment.status.in_(
                    (
                        AssignmentStatus.confirmed,
                        AssignmentStatus.waitlisted,
                        AssignmentStatus.applied,
                        AssignmentStatus.invited,
                    )
                ),
            )
        )
        if taken.scalar_one_or_none():
            continue
        existing = await db.execute(
            select(ShiftOffer).where(
                ShiftOffer.shift_id == shift.id,
                ShiftOffer.worker_id == worker.id,
                ShiftOffer.status == ShiftOfferStatus.pending,
            )
        )
        if existing.scalar_one_or_none():
            continue
        offer = ShiftOffer(
            shift_id=shift.id,
            worker_id=worker.id,
            match_score=score,
            expires_at=expires,
            status=ShiftOfferStatus.pending,
        )
        db.add(offer)
        await db.flush()
        u = await db.execute(select(User).where(User.id == worker.user_id))
        user = u.scalar_one_or_none()
        if user:
            await notify_user(
                db,
                user.id,
                title="New shift available",
                body=f"{job.title} — shift starting {shift.starts_at.isoformat()}",
                payload={"shift_id": shift.id, "job_order_id": job.id, "offer_id": offer.id},
            )


async def confirmed_count(db: AsyncSession, shift_id: int) -> int:
    r = await db.execute(
        select(func.count())
        .select_from(ShiftAssignment)
        .where(
            ShiftAssignment.shift_id == shift_id,
            ShiftAssignment.status == AssignmentStatus.confirmed,
        )
    )
    return int(r.scalar() or 0)


async def waitlist_next_rank(db: AsyncSession, shift_id: int) -> int:
    r = await db.execute(
        select(func.max(ShiftAssignment.waitlist_rank)).where(
            ShiftAssignment.shift_id == shift_id,
            ShiftAssignment.status == AssignmentStatus.waitlisted,
        )
    )
    m = r.scalar()
    return (m or 0) + 1


async def application_next_rank(db: AsyncSession, shift_id: int) -> int:
    r = await db.execute(
        select(func.max(ShiftAssignment.waitlist_rank)).where(
            ShiftAssignment.shift_id == shift_id,
            ShiftAssignment.status == AssignmentStatus.applied,
        )
    )
    m = r.scalar()
    return (m or 0) + 1
