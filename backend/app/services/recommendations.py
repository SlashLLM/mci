from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssignmentStatus,
    JobOrder,
    JobOrderStatus,
    MarketplaceShiftDismissal,
    Shift,
    ShiftAssignment,
    WorkerProfile,
)
from app.services.geo import haversine_m


async def job_order_ids_rejected_for_worker(db: AsyncSession, worker_profile_id: int) -> set[int]:
    """Job orders where this worker has any rejected shift assignment."""
    rej = await db.execute(
        select(Shift.job_order_id)
        .join(ShiftAssignment, ShiftAssignment.shift_id == Shift.id)
        .where(
            ShiftAssignment.worker_id == worker_profile_id,
            ShiftAssignment.status == AssignmentStatus.rejected,
        )
        .distinct()
    )
    return {row[0] for row in rej.all()}


async def recommended_shifts_for_worker(
    db: AsyncSession,
    worker: WorkerProfile,
    limit: int = 20,
    max_km: float | None = None,
) -> list[tuple[Shift, float | None]]:
    """Surface published open shifts; rank by distance (when worker has coords) then job-type and urgency.

    Omits entire job orders where this worker has a rejected assignment (any shift on that job).
    """
    now = datetime.now(timezone.utc)
    rejected_job_ids = await job_order_ids_rejected_for_worker(db, worker.id)

    dismissed_rows = await db.execute(
        select(MarketplaceShiftDismissal.shift_id).where(MarketplaceShiftDismissal.worker_profile_id == worker.id)
    )
    dismissed_shift_ids = {row[0] for row in dismissed_rows.all()}

    r = await db.execute(
        select(Shift)
        .join(JobOrder, Shift.job_order_id == JobOrder.id)
        .where(
            JobOrder.status.in_([JobOrderStatus.open, JobOrderStatus.partially_filled]),
            Shift.starts_at > now,
        )
    )
    shifts = list(r.scalars().all())
    prefs = set(worker.job_type_preferences or [])
    worker_has_loc = worker.location_lat is not None and worker.location_lng is not None

    scored: list[tuple[Shift, float, float | None]] = []
    for s in shifts:
        if s.id in dismissed_shift_ids:
            continue
        job = await db.get(JobOrder, s.job_order_id)
        if not job:
            continue
        if job.id in rejected_job_ids:
            continue
        fc = await db.scalar(
            select(func.count())
            .select_from(ShiftAssignment)
            .where(
                ShiftAssignment.shift_id == s.id,
                ShiftAssignment.status == AssignmentStatus.confirmed,
            )
        )
        open_slots = max(0, s.workers_required - int(fc or 0))
        if open_slots <= 0:
            continue

        # Hide shift if already on roster (not applied — workers stay listed to view/withdraw).
        roster_taken = await db.scalar(
            select(func.count())
            .select_from(ShiftAssignment)
            .where(
                ShiftAssignment.shift_id == s.id,
                ShiftAssignment.worker_id == worker.id,
                ShiftAssignment.status.in_(
                    (
                        AssignmentStatus.confirmed,
                        AssignmentStatus.waitlisted,
                        AssignmentStatus.invited,
                    )
                ),
            )
        )
        if int(roster_taken or 0) > 0:
            continue

        distance_m: float | None = None
        if worker_has_loc:
            distance_m = haversine_m(
                float(worker.location_lat),
                float(worker.location_lng),
                float(job.location_lat),
                float(job.location_lng),
            )
            if max_km is not None and max_km > 0 and distance_m > max_km * 1000:
                continue

        type_bonus = 0.3 if job.job_type in prefs else 0.0
        urgency = min(1.0, open_slots / max(1, s.workers_required))
        secondary = type_bonus + urgency
        scored.append((s, secondary, distance_m))

    if worker_has_loc:
        scored.sort(key=lambda x: ((x[2] if x[2] is not None else 1e12), -x[1]))
    else:
        scored.sort(key=lambda x: -x[1])

    out: list[tuple[Shift, float | None]] = []
    for s, _sec, dm in scored[:limit]:
        out.append((s, dm))
    return out
