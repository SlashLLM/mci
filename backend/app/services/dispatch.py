from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AutomaticDispatchMode,
    AssignmentStatus,
    DispatchTaskStatus,
    JobOrder,
    JobOrderStatus,
    PreferredWorker,
    Shift,
    ShiftAssignment,
    ShiftDispatchTask,
    ShiftOffer,
    ShiftOfferStatus,
    User,
    WorkerProfile,
)
from app.services.matching import rank_workers_for_shift, select_dispatch_candidates
from app.services.notifications import notify_user

logger = logging.getLogger(__name__)


def _dispatch_mode(job: JobOrder) -> AutomaticDispatchMode:
    mode = job.automatic_dispatch_mode
    if isinstance(mode, AutomaticDispatchMode):
        return mode
    return AutomaticDispatchMode(str(mode))


def _display_shift_start(starts_at: datetime) -> str:
    dt = starts_at if starts_at.tzinfo else starts_at.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%d %H:%M UTC")


async def publish_job_order(db: AsyncSession, job: JobOrder) -> None:
    job.status = JobOrderStatus.open
    job.published_at = datetime.now(timezone.utc)
    await db.flush()
    for shift in job.shifts:
        await dispatch_shift(db, job, shift)


async def _existing_notified_worker_ids(db: AsyncSession, shift_id: int) -> set[int]:
    rows = await db.execute(select(ShiftOffer.worker_id).where(ShiftOffer.shift_id == shift_id))
    return set(rows.scalars().all())


async def _create_offers_and_notify(
    db: AsyncSession,
    *,
    job: JobOrder,
    shift: Shift,
    candidates: list[tuple],
) -> int:
    expires = datetime.now(timezone.utc) + timedelta(minutes=job.acceptance_window_minutes)
    sent = 0
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
                body=f"{job.title} — shift starting {_display_shift_start(shift.starts_at)}",
                payload={"shift_id": shift.id, "job_order_id": job.id, "offer_id": offer.id},
            )
            sent += 1
    return sent


async def _schedule_performance_phase_two(db: AsyncSession, *, job: JobOrder, shift: Shift) -> None:
    delay_minutes = int(job.automatic_dispatch_priority_window_minutes or 120)
    run_after = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    dedupe_key = f"shift:{shift.id}:mode:performance_priority:phase:2"
    existing = await db.execute(select(ShiftDispatchTask).where(ShiftDispatchTask.dedupe_key == dedupe_key))
    if existing.scalar_one_or_none():
        return
    db.add(
        ShiftDispatchTask(
            shift_id=shift.id,
            job_order_id=job.id,
            phase="performance_phase_2",
            run_after=run_after,
            status=DispatchTaskStatus.pending,
            dedupe_key=dedupe_key,
        )
    )


async def dispatch_shift(
    db: AsyncSession,
    job: JobOrder,
    shift: Shift,
    *,
    performance_phase: int = 1,
) -> int:
    ranked = await rank_workers_for_shift(db, job, shift)
    already_notified = await _existing_notified_worker_ids(db, shift.id)

    dispatch_mode = AutomaticDispatchMode.fcfs
    if job.automatic_dispatch_enabled:
        dispatch_mode = _dispatch_mode(job)

    # Performance priority phase 2 now only opens marketplace visibility for non-elite workers.
    # It must not create additional offers/notifications.
    if dispatch_mode == AutomaticDispatchMode.performance_priority and performance_phase == 2:
        return 0

    if dispatch_mode == AutomaticDispatchMode.preferred_priority and performance_phase == 1:
        ranked_by_worker_id = {worker.id: score for worker, score in ranked}
        pref_rows = await db.execute(
            select(WorkerProfile)
            .join(PreferredWorker, PreferredWorker.worker_id == WorkerProfile.id)
            .where(PreferredWorker.client_org_id == job.client_org_id)
        )
        preferred_workers = pref_rows.scalars().all()
        preferred_candidates = [
            (worker, float(ranked_by_worker_id.get(worker.id, 0.0)))
            for worker in preferred_workers
            if worker.id not in already_notified
        ]
        sent_preferred = await _create_offers_and_notify(db, job=job, shift=shift, candidates=preferred_candidates)

        already_notified = await _existing_notified_worker_ids(db, shift.id)
        base_candidates = await select_dispatch_candidates(
            db,
            job,
            shift,
            ranked,
            mode=AutomaticDispatchMode.fcfs.value,
            already_notified_worker_ids=already_notified,
        )
        preferred_worker_ids = {worker.id for worker in preferred_workers}
        fallback_fcfs = [(worker, score) for worker, score in base_candidates if worker.id not in preferred_worker_ids]
        sent_fallback = await _create_offers_and_notify(db, job=job, shift=shift, candidates=fallback_fcfs)
        logger.info(
            "preferred_priority_dispatch shift_id=%s preferred_targeted=%s preferred_notified=%s fallback_notified=%s",
            shift.id,
            len(preferred_candidates),
            sent_preferred,
            sent_fallback,
        )
        return sent_preferred + sent_fallback

    candidates = await select_dispatch_candidates(
        db,
        job,
        shift,
        ranked,
        mode=dispatch_mode.value,
        already_notified_worker_ids=already_notified,
        performance_phase=performance_phase,
    )
    sent = await _create_offers_and_notify(db, job=job, shift=shift, candidates=candidates)
    if (
        job.automatic_dispatch_enabled
        and dispatch_mode == AutomaticDispatchMode.performance_priority
        and performance_phase == 1
    ):
        await _schedule_performance_phase_two(db, job=job, shift=shift)
    return sent


async def process_dispatch_tasks_once(db: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    rows = await db.execute(
        select(ShiftDispatchTask)
        .where(
            ShiftDispatchTask.status == DispatchTaskStatus.pending,
            ShiftDispatchTask.run_after <= now,
        )
        .order_by(ShiftDispatchTask.run_after.asc())
        .limit(50)
    )
    tasks = rows.scalars().all()
    processed = 0
    for task in tasks:
        job = await db.get(JobOrder, task.job_order_id)
        shift = await db.get(Shift, task.shift_id)
        if not job or not shift or task.phase != "performance_phase_2":
            task.status = DispatchTaskStatus.cancelled
            task.processed_at = now
            processed += 1
            continue
        await dispatch_shift(db, job, shift, performance_phase=2)
        task.status = DispatchTaskStatus.completed
        task.processed_at = now
        processed += 1
    return processed


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
