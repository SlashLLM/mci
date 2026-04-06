"""Rule-based matching: eligibility + weighted score (PRD §9)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssignmentStatus,
    JobOrder,
    JobTypeWeight,
    PreferredWorker,
    Shift,
    ShiftAssignment,
    WorkerProfile,
    WorkerStatus,
    WorkerTier,
)
from app.services.geo import haversine_m


async def get_weights_for_job_type(db: AsyncSession, job_type: str) -> JobTypeWeight:
    result = await db.execute(select(JobTypeWeight).where(JobTypeWeight.job_type == job_type))
    w = result.scalar_one_or_none()
    if w:
        return w
    result = await db.execute(select(JobTypeWeight).where(JobTypeWeight.job_type == "_default"))
    d = result.scalar_one_or_none()
    if d:
        return d
    # synthetic default
    return JobTypeWeight(
        job_type=job_type,
        weight_proximity=0.3,
        weight_rating=0.25,
        weight_job_type=0.2,
        weight_completion=0.15,
        weight_tier=0.1,
    )


def tier_score(tier: WorkerTier) -> float:
    return {WorkerTier.elite: 1.0, WorkerTier.preferred: 0.7, WorkerTier.standard: 0.4}[tier]


async def worker_has_overlap(
    db: AsyncSession,
    worker_id: int,
    starts_at: datetime,
    ends_at: datetime,
    exclude_shift_id: Optional[int] = None,
) -> bool:
    q = (
        select(ShiftAssignment.id)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .where(
            ShiftAssignment.worker_id == worker_id,
            ShiftAssignment.status == AssignmentStatus.confirmed,
            Shift.starts_at < ends_at,
            Shift.ends_at > starts_at,
        )
    )
    if exclude_shift_id is not None:
        q = q.where(Shift.id != exclude_shift_id)
    r = await db.execute(q.limit(1))
    return r.scalar_one_or_none() is not None


def has_required_compliance(worker: WorkerProfile, required_certs: list) -> bool:
    if not required_certs:
        return True
    certs = set(worker.certifications or [])
    return all(c in certs for c in required_certs)


def availability_covers_shift(worker: WorkerProfile, starts_at: datetime) -> bool:
    """Simple availability: if empty dict, treat as always available."""
    av = worker.availability or {}
    if not av:
        return True
    # optional keys: weekdays list [0-6], hours {start,end} — MVP: if 'always' True
    if av.get("always") is True:
        return True
    wd = starts_at.weekday()
    days = av.get("weekdays")
    if days is not None and wd not in days:
        return False
    return True


async def list_eligible_workers(
    db: AsyncSession,
    job: JobOrder,
    shift: Shift,
) -> list[WorkerProfile]:
    result = await db.execute(select(WorkerProfile).where(WorkerProfile.status == WorkerStatus.active))
    workers = list(result.scalars().all())
    eligible: list[WorkerProfile] = []
    for w in workers:
        if not has_required_compliance(w, job.required_certifications or []):
            continue
        if not availability_covers_shift(w, shift.starts_at):
            continue
        if await worker_has_overlap(db, w.id, shift.starts_at, shift.ends_at, shift.id):
            continue
        eligible.append(w)
    return eligible


def score_worker(
    worker: WorkerProfile,
    job: JobOrder,
    weights: JobTypeWeight,
    is_preferred: bool,
) -> float:
    # proximity 0..1 (closer better), cap at 50km -> 0
    prox = 0.0
    if worker.location_lat is not None and worker.location_lng is not None:
        d = haversine_m(worker.location_lat, worker.location_lng, job.location_lat, job.location_lng)
        prox = max(0.0, 1.0 - min(d, 50000) / 50000)
    rating = min(1.0, (worker.rating_avg or 0) / 5.0)
    jt = 1.0 if job.job_type in (worker.job_type_preferences or []) else 0.3
    completion = float(worker.completion_rate or 0.0)
    completion = min(1.0, max(0.0, completion))
    tier = tier_score(worker.tier)
    if is_preferred:
        tier = min(1.0, tier + 0.2)
    return (
        weights.weight_proximity * prox
        + weights.weight_rating * rating
        + weights.weight_job_type * jt
        + weights.weight_completion * completion
        + weights.weight_tier * tier
    )


async def rank_workers_for_shift(
    db: AsyncSession,
    job: JobOrder,
    shift: Shift,
) -> list[tuple[WorkerProfile, float]]:
    weights = await get_weights_for_job_type(db, job.job_type)
    eligible = await list_eligible_workers(db, job, shift)
    pref_ids: set[int] = set()
    if job.client_org_id:
        r = await db.execute(
            select(PreferredWorker.worker_id).where(PreferredWorker.client_org_id == job.client_org_id)
        )
        pref_ids = set(r.scalars().all())
    scored: list[tuple[WorkerProfile, float]] = []
    for w in eligible:
        is_pref = w.id in pref_ids
        scored.append((w, score_worker(w, job, weights, is_pref)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


async def select_dispatch_candidates(
    db: AsyncSession,
    job: JobOrder,
    shift: Shift,
    ranked: list[tuple[WorkerProfile, float]],
) -> list[tuple[WorkerProfile, float]]:
    """Return workers to notify using a single default strategy."""
    if not ranked:
        return []
    need = min(len(ranked), max(shift.workers_required * 5, shift.workers_required + 10))
    return ranked[:need]
