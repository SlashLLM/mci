from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssignmentStatus,
    JobOrder,
    JobOrderStatus,
    MarketplaceShiftDismissal,
    Shift,
    ShiftAssignment,
    WorkerProfile,
    WorkerShiftRecommendation,
    WorkerStatus,
)
from app.services.geo import haversine_m
from app.services.matching import performance_priority_marketplace_visible

RECOMMENDATION_STALE_AFTER = timedelta(hours=26)


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
    scored = await _compute_recommendation_candidates(db, worker, limit=limit, max_km=max_km)
    return [(item["shift"], item["distance_m"]) for item in scored]


async def _completed_client_org_ids_for_worker(db: AsyncSession, worker_profile_id: int) -> set[int]:
    rows = await db.execute(
        select(JobOrder.client_org_id)
        .join(Shift, Shift.job_order_id == JobOrder.id)
        .join(ShiftAssignment, ShiftAssignment.shift_id == Shift.id)
        .where(
            ShiftAssignment.worker_id == worker_profile_id,
            ShiftAssignment.status == AssignmentStatus.completed,
        )
        .distinct()
    )
    return {row[0] for row in rows.all()}


async def _compute_recommendation_candidates(
    db: AsyncSession,
    worker: WorkerProfile,
    *,
    limit: int,
    max_km: float | None,
) -> list[dict]:
    now = datetime.now(timezone.utc)
    rejected_job_ids = await job_order_ids_rejected_for_worker(db, worker.id)
    completed_client_ids = await _completed_client_org_ids_for_worker(db, worker.id)
    dismissed_rows = await db.execute(
        select(MarketplaceShiftDismissal.shift_id).where(MarketplaceShiftDismissal.worker_profile_id == worker.id)
    )
    dismissed_shift_ids = {row[0] for row in dismissed_rows.all()}
    shift_rows = await db.execute(
        select(Shift, JobOrder)
        .join(JobOrder, Shift.job_order_id == JobOrder.id)
        .where(
            JobOrder.status.in_([JobOrderStatus.open, JobOrderStatus.partially_filled]),
            Shift.starts_at > now,
        )
    )
    prefs = set(worker.job_type_preferences or [])
    skill_tags = {str(s).strip().lower() for s in (worker.skills or []) if str(s).strip()}
    worker_has_loc = worker.location_lat is not None and worker.location_lng is not None
    scored: list[dict] = []

    for shift, job in shift_rows.all():
        if shift.id in dismissed_shift_ids or job.id in rejected_job_ids:
            continue
        if not performance_priority_marketplace_visible(job, worker, now):
            continue

        confirmed_count = await db.scalar(
            select(func.count())
            .select_from(ShiftAssignment)
            .where(
                ShiftAssignment.shift_id == shift.id,
                ShiftAssignment.status == AssignmentStatus.confirmed,
            )
        )
        open_slots = max(0, shift.workers_required - int(confirmed_count or 0))
        if open_slots <= 0:
            continue

        roster_taken = await db.scalar(
            select(func.count())
            .select_from(ShiftAssignment)
            .where(
                ShiftAssignment.shift_id == shift.id,
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
        distance_score = 0.0
        if worker_has_loc:
            distance_m = haversine_m(
                float(worker.location_lat),
                float(worker.location_lng),
                float(job.location_lat),
                float(job.location_lng),
            )
            if max_km is not None and max_km > 0 and distance_m > max_km * 1000:
                continue
            distance_score = max(0.0, 1.0 - min(1.0, distance_m / 30000.0))

        preference_score = 0.35 if job.job_type in prefs else 0.0
        required_skills = {str(s).strip().lower() for s in (job.required_skills or []) if str(s).strip()}
        affinity_score = min(0.4, 0.1 * len(required_skills.intersection(skill_tags)))
        urgency_score = min(1.0, open_slots / max(1, shift.workers_required))
        return_opportunity = job.client_org_id in completed_client_ids
        return_score = 0.6 if return_opportunity else 0.0
        score_total = preference_score + affinity_score + (0.75 * urgency_score) + return_score + (0.25 * distance_score)

        reason_flags: list[str] = []
        if urgency_score >= 0.6:
            reason_flags.append("urgency_boost")
        if return_opportunity:
            reason_flags.append("return_opportunity")
            reason_flags.append("worked_here_before")
        if preference_score > 0:
            reason_flags.append("preference_match")
        if affinity_score > 0:
            reason_flags.append("profile_tag_match")

        scored.append(
            {
                "shift": shift,
                "job": job,
                "distance_m": distance_m,
                "score_total": score_total,
                "urgency_score": urgency_score,
                "return_opportunity": return_opportunity,
                "reason_flags": reason_flags,
                "score_breakdown": {
                    "preference": round(preference_score, 5),
                    "profile_affinity": round(affinity_score, 5),
                    "urgency": round(urgency_score, 5),
                    "return_opportunity": round(return_score, 5),
                    "distance": round(distance_score, 5),
                },
            }
        )

    scored.sort(
        key=lambda item: (
            -item["score_total"],
            item["distance_m"] if item["distance_m"] is not None else 1e12,
            item["shift"].starts_at,
        )
    )
    return scored[:limit]


async def recompute_worker_recommendations(
    db: AsyncSession,
    worker: WorkerProfile,
    *,
    source: str = "manual",
    limit: int = 100,
) -> int:
    candidates = await _compute_recommendation_candidates(db, worker, limit=limit, max_km=None)
    await db.execute(
        delete(WorkerShiftRecommendation).where(WorkerShiftRecommendation.worker_profile_id == worker.id)
    )
    computed_at = datetime.now(timezone.utc)
    for item in candidates:
        db.add(
            WorkerShiftRecommendation(
                worker_profile_id=worker.id,
                shift_id=item["shift"].id,
                score_total=item["score_total"],
                urgency_score=item["urgency_score"],
                return_opportunity=item["return_opportunity"],
                score_breakdown=item["score_breakdown"],
                reason_flags=item["reason_flags"],
                computed_at=computed_at,
                source=source,
            )
        )
    await db.flush()
    return len(candidates)


async def recompute_all_active_worker_recommendations(
    db: AsyncSession,
    *,
    source: str = "daily",
    limit_per_worker: int = 100,
) -> int:
    rows = await db.execute(
        select(WorkerProfile).where(WorkerProfile.status == WorkerStatus.active)
    )
    workers = rows.scalars().all()
    total_rows = 0
    for worker in workers:
        total_rows += await recompute_worker_recommendations(
            db,
            worker,
            source=source,
            limit=limit_per_worker,
        )
    return total_rows


async def get_worker_recommendations(
    db: AsyncSession,
    worker: WorkerProfile,
    *,
    limit: int = 50,
    force_refresh_if_stale: bool = True,
) -> tuple[list[dict], str | None]:
    latest = await db.scalar(
        select(func.max(WorkerShiftRecommendation.computed_at)).where(
            WorkerShiftRecommendation.worker_profile_id == worker.id
        )
    )
    now = datetime.now(timezone.utc)
    needs_refresh = latest is None or (now - latest) > RECOMMENDATION_STALE_AFTER
    if force_refresh_if_stale and needs_refresh:
        await recompute_worker_recommendations(db, worker, source="on_demand", limit=max(limit, 100))
        latest = await db.scalar(
            select(func.max(WorkerShiftRecommendation.computed_at)).where(
                WorkerShiftRecommendation.worker_profile_id == worker.id
            )
        )
    if latest is None:
        return [], None

    rows = await db.execute(
        select(WorkerShiftRecommendation, Shift, JobOrder)
        .join(Shift, Shift.id == WorkerShiftRecommendation.shift_id)
        .join(JobOrder, JobOrder.id == Shift.job_order_id)
        .where(
            WorkerShiftRecommendation.worker_profile_id == worker.id,
            JobOrder.status.in_([JobOrderStatus.open, JobOrderStatus.partially_filled]),
            Shift.starts_at > now,
        )
        .order_by(WorkerShiftRecommendation.score_total.desc(), Shift.starts_at.asc())
        .limit(limit)
    )
    payload: list[dict] = []
    for rec, shift, job in rows.all():
        payload.append(
            {
                "rec": rec,
                "shift": shift,
                "job": job,
            }
        )
    return payload, latest.isoformat()
