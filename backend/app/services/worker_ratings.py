"""Client ratings for shift assignments: upsert + worker aggregate tier."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rating, WorkerProfile, WorkerTier


async def refresh_worker_rating_tier(db: AsyncSession, worker_id: int) -> float:
    r = await db.execute(select(Rating).where(Rating.worker_id == worker_id))
    all_r = r.scalars().all()
    avg = sum(x.stars for x in all_r) / max(1, len(all_r))
    wp = await db.get(WorkerProfile, worker_id)
    if wp:
        wp.rating_avg = avg
        if wp.rating_avg >= 4.5:
            wp.tier = WorkerTier.elite
        elif wp.rating_avg >= 3.5:
            wp.tier = WorkerTier.preferred
        else:
            wp.tier = WorkerTier.standard
    return avg


async def upsert_client_rating_for_assignment(
    db: AsyncSession,
    *,
    shift_assignment_id: int,
    worker_id: int,
    rated_by_user_id: int,
    stars: int,
    comment: str | None = None,
) -> float:
    r = await db.execute(
        select(Rating).where(
            Rating.shift_assignment_id == shift_assignment_id,
            Rating.rated_by_user_id == rated_by_user_id,
        )
    )
    existing = r.scalar_one_or_none()
    if existing:
        existing.stars = stars
        if comment is not None:
            existing.comment = comment
    else:
        db.add(
            Rating(
                shift_assignment_id=shift_assignment_id,
                worker_id=worker_id,
                rated_by_user_id=rated_by_user_id,
                stars=stars,
                comment=comment,
            )
        )
        wp = await db.get(WorkerProfile, worker_id)
        if wp:
            wp.points = (wp.points or 0) + 10
    await db.flush()
    avg = await refresh_worker_rating_tier(db, worker_id)
    await db.flush()
    return avg
