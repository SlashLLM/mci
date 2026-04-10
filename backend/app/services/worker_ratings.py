"""Client ratings plus points-based worker tier management."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rating, WorkerProfile, WorkerTier

POINTS_PER_COMPLETED_SHIFT = 10
POINTS_PENALTY_LATE_CANCEL = -5
POINTS_PENALTY_NO_SHOW = -15
PREFERRED_TIER_MIN_POINTS = 50
ELITE_TIER_MIN_POINTS = 150


def tier_from_points(points: int) -> WorkerTier:
    if points < 0:
        return WorkerTier.probation
    if points >= ELITE_TIER_MIN_POINTS:
        return WorkerTier.elite
    if points >= PREFERRED_TIER_MIN_POINTS:
        return WorkerTier.preferred
    return WorkerTier.standard


async def refresh_worker_reputation(db: AsyncSession, worker_id: int) -> float:
    r = await db.execute(select(Rating).where(Rating.worker_id == worker_id))
    all_r = r.scalars().all()
    avg = sum(x.stars for x in all_r) / max(1, len(all_r))
    wp = await db.get(WorkerProfile, worker_id)
    if wp:
        wp.rating_avg = avg
        wp.points = int(wp.points or 0)
        wp.tier = tier_from_points(wp.points)
    return avg


async def adjust_worker_points(db: AsyncSession, worker_id: int, delta: int) -> int | None:
    wp = await db.get(WorkerProfile, worker_id)
    if not wp:
        return None
    wp.points = int(wp.points or 0) + delta
    wp.tier = tier_from_points(wp.points)
    await db.flush()
    return wp.points


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
    await db.flush()
    avg = await refresh_worker_reputation(db, worker_id)
    await db.flush()
    return avg
