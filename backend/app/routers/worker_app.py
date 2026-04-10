from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import require_roles
from app.config import get_settings
from app.db.session import get_db
from app.models import (
    AssignmentStatus,
    AttendanceRecord,
    JobOrder,
    JobOrderStatus,
    MarketplaceShiftDismissal,
    Shift,
    ShiftAssignment,
    ShiftOffer,
    ShiftOfferStatus,
    User,
    UserRole,
    WorkerProfile,
    WorkerStatus,
)
from app.services.attendance_rules import (
    clock_in_earliest_utc,
    is_clock_in_too_early,
    is_late_window_without_clock_in,
    is_past_clock_in_grace_deadline,
    is_past_shift_end,
    late_threshold_utc,
)
from app.services.dispatch import application_next_rank, confirmed_count, waitlist_next_rank
from app.services.job_status import refresh_job_order_fill_status
from app.services.notifications import notify_user
from app.services.recommendations import job_order_ids_rejected_for_worker, recommended_shifts_for_worker
from app.services.ta_client_contracts import get_active_contract_for_org
from app.services.worker_ratings import POINTS_PENALTY_LATE_CANCEL, adjust_worker_points

router = APIRouter(prefix="/worker", tags=["worker-app"])


async def _notify_ta_users_of_overlap(
    db: AsyncSession,
    *,
    worker_profile_id: int,
    new_assignment_id: int,
    shift_id: int,
    starts_at: datetime,
    ends_at: datetime,
) -> None:
    current_shift = await db.get(Shift, shift_id)
    if not current_shift:
        return
    current_job = await db.get(JobOrder, current_shift.job_order_id)
    if not current_job:
        return

    r = await db.execute(
        select(ShiftAssignment)
        .options(selectinload(ShiftAssignment.shift))
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .where(
            ShiftAssignment.worker_id == worker_profile_id,
            ShiftAssignment.status == AssignmentStatus.confirmed,
            ShiftAssignment.id != new_assignment_id,
            Shift.starts_at < ends_at,
            Shift.ends_at > starts_at,
        )
        .order_by(Shift.starts_at.asc())
    )
    overlaps = r.scalars().all()
    if not overlaps:
        return
    worker = await db.get(WorkerProfile, worker_profile_id)
    worker_name = (worker.full_name or "").strip() if worker else ""
    label = worker_name or f"Worker #{worker_profile_id}"
    contract = await get_active_contract_for_org(db, current_job.client_org_id)
    if contract:
        recipient_rows = await db.execute(
            select(User.id).where(
                User.id == contract.ta_user_id,
                User.role == UserRole.ta,
            )
        )
    else:
        recipient_rows = await db.execute(
            select(User.id).where(
                User.role == UserRole.client,
                User.client_org_id == current_job.client_org_id,
            )
        )

    for recipient_user_id in recipient_rows.scalars().all():
        await notify_user(
            db,
            recipient_user_id,
            title="Shift overlap conflict",
            body=f"{label} has overlapping confirmed shifts. New shift #{shift_id} overlaps with {len(overlaps)} existing assignment(s).",
            payload={
                "type": "overlap_conflict",
                "worker_profile_id": worker_profile_id,
                "new_assignment_id": new_assignment_id,
                "new_shift_id": shift_id,
                "overlap_assignment_ids": [a.id for a in overlaps],
            },
        )


async def _auto_notify_next_waitlisted_worker(db: AsyncSession, shift_id: int, cancelled_assignment_id: int) -> None:
    r = await db.execute(
        select(ShiftAssignment)
        .where(
            ShiftAssignment.shift_id == shift_id,
            ShiftAssignment.status == AssignmentStatus.waitlisted,
        )
        .order_by(ShiftAssignment.waitlist_rank.asc().nulls_last(), ShiftAssignment.created_at.asc())
    )
    next_waitlisted = r.scalars().first()
    if not next_waitlisted:
        return
    wp = await db.get(WorkerProfile, next_waitlisted.worker_id)
    if not wp:
        return
    user = await db.get(User, wp.user_id)
    if not user:
        return
    await notify_user(
        db,
        user.id,
        title="Shift opening available",
        body="A spot has opened up in a shift where you are waitlisted. Please review your roster status.",
        payload={
            "type": "waitlist_opening",
            "shift_id": shift_id,
            "waitlist_assignment_id": next_waitlisted.id,
            "cancelled_assignment_id": cancelled_assignment_id,
        },
    )


async def _decline_pending_offers_for_shift_worker(
    db: AsyncSession, shift_id: int, worker_profile_id: int
) -> None:
    r = await db.execute(
        select(ShiftOffer).where(
            ShiftOffer.shift_id == shift_id,
            ShiftOffer.worker_id == worker_profile_id,
            ShiftOffer.status == ShiftOfferStatus.pending,
        )
    )
    for o in r.scalars().all():
        o.status = ShiftOfferStatus.declined


_HISTORY_STATUSES_ALL: tuple[AssignmentStatus, ...] = (
    AssignmentStatus.confirmed,
    AssignmentStatus.completed,
    AssignmentStatus.invited,
    AssignmentStatus.waitlisted,
    AssignmentStatus.applied,
    AssignmentStatus.rejected,
)


def _effective_assignment_status(
    assignment: ShiftAssignment,
    *,
    now: datetime | None = None,
) -> AssignmentStatus:
    current_time = now or datetime.now(timezone.utc)
    if assignment.status in (AssignmentStatus.applied, AssignmentStatus.waitlisted) and is_past_clock_in_grace_deadline(
        current_time, assignment.shift.starts_at
    ):
        return AssignmentStatus.rejected
    return assignment.status


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _history_statuses_for_query(bucket: str) -> tuple[AssignmentStatus, ...]:
    b = (bucket or "all").strip().lower()
    if b == "all":
        return _HISTORY_STATUSES_ALL
    if b == "accepted":
        return (AssignmentStatus.confirmed, AssignmentStatus.completed, AssignmentStatus.invited)
    if b == "waitlisted":
        return (AssignmentStatus.waitlisted,)
    if b == "pending":
        return (AssignmentStatus.applied,)
    if b == "rejected":
        return (AssignmentStatus.rejected,)
    raise HTTPException(400, detail="status must be all, accepted, waitlisted, pending, or rejected")


def _history_bucket_for_status(st: AssignmentStatus) -> str:
    if st in (AssignmentStatus.confirmed, AssignmentStatus.completed, AssignmentStatus.invited):
        return "accepted"
    if st == AssignmentStatus.waitlisted:
        return "waitlisted"
    if st == AssignmentStatus.applied:
        return "pending"
    if st == AssignmentStatus.rejected:
        return "rejected"
    return st.value


def _history_bucket_matches_query(bucket: str, query: str) -> bool:
    normalized_query = (query or "all").strip().lower()
    if normalized_query == "all":
        return True
    return bucket == normalized_query


@router.get("/offers")
async def my_offers(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        return []
    if wp.status == WorkerStatus.blacklisted:
        return []
    rejected_jobs = await job_order_ids_rejected_for_worker(db, wp.id)
    r2 = await db.execute(
        select(ShiftOffer)
        .options(selectinload(ShiftOffer.shift).selectinload(Shift.job_order))
        .where(ShiftOffer.worker_id == wp.id, ShiftOffer.status == ShiftOfferStatus.pending)
    )
    offers = r2.scalars().all()
    return [
        {
            "id": o.id,
            "match_score": o.match_score,
            "expires_at": o.expires_at.isoformat() if o.expires_at else None,
            "shift": {
                "id": o.shift.id,
                "starts_at": o.shift.starts_at.isoformat(),
                "ends_at": o.shift.ends_at.isoformat(),
                "job_title": o.shift.job_order.title,
                "job_id": o.shift.job_order_id,
            },
        }
        for o in offers
        if o.shift.job_order_id not in rejected_jobs
    ]


@router.post("/offers/{offer_id}/accept")
async def accept_offer(
    offer_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        raise HTTPException(404)
    if wp.status == WorkerStatus.blacklisted:
        raise HTTPException(403, detail="Blacklisted workers cannot accept offers")
    offer = await db.get(ShiftOffer, offer_id)
    if not offer or offer.worker_id != wp.id or offer.status != ShiftOfferStatus.pending:
        raise HTTPException(400, detail="Invalid offer")
    if offer.expires_at and offer.expires_at < datetime.now(timezone.utc):
        offer.status = ShiftOfferStatus.expired
        raise HTTPException(400, detail="Offer expired")

    shift = await db.get(Shift, offer.shift_id)
    job = await db.get(JobOrder, shift.job_order_id)
    prev_sa = await db.execute(
        select(ShiftAssignment).where(
            ShiftAssignment.shift_id == shift.id,
            ShiftAssignment.worker_id == wp.id,
        )
    )
    prev_row = prev_sa.scalar_one_or_none()
    if prev_row:
        if prev_row.status == AssignmentStatus.confirmed:
            raise HTTPException(400, detail="Already confirmed for this shift")
        if prev_row.status == AssignmentStatus.waitlisted:
            raise HTTPException(400, detail="Already on roster for this shift")
        if prev_row.status == AssignmentStatus.applied:
            await db.delete(prev_row)
            await db.flush()
        else:
            raise HTTPException(400, detail="Cannot accept offer while this assignment exists")

    cc = await confirmed_count(db, shift.id)
    offer.status = ShiftOfferStatus.accepted

    if cc < shift.workers_required:
        sa = ShiftAssignment(
            shift_id=shift.id,
            worker_id=wp.id,
            status=AssignmentStatus.confirmed,
            match_score=offer.match_score,
            confirmed_at=datetime.now(timezone.utc),
        )
        db.add(sa)
    else:
        rank = await waitlist_next_rank(db, shift.id)
        sa = ShiftAssignment(
            shift_id=shift.id,
            worker_id=wp.id,
            status=AssignmentStatus.waitlisted,
            waitlist_rank=rank,
            match_score=offer.match_score,
        )
        db.add(sa)
    await db.flush()
    if sa.status == AssignmentStatus.confirmed:
        await _notify_ta_users_of_overlap(
            db,
            worker_profile_id=wp.id,
            new_assignment_id=sa.id,
            shift_id=shift.id,
            starts_at=shift.starts_at,
            ends_at=shift.ends_at,
        )
    await refresh_job_order_fill_status(db, job)
    await notify_user(db, user.id, title="Shift update", body=f"Status: {sa.status.value} for shift {shift.id}")
    return {"assignment_status": sa.status.value}


@router.post("/offers/{offer_id}/decline")
async def decline_offer(
    offer_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        raise HTTPException(404)
    offer = await db.get(ShiftOffer, offer_id)
    if not offer or offer.worker_id != wp.id:
        raise HTTPException(400)
    offer.status = ShiftOfferStatus.declined
    return {"ok": True}


@router.get("/marketplace/shifts")
async def marketplace_shifts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
    max_km: float | None = Query(None, ge=0, description="Optional max distance from worker home (km)"),
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        return []
    if wp.status == WorkerStatus.blacklisted:
        return []
    ranked = await recommended_shifts_for_worker(db, wp, limit=50, max_km=max_km)
    shift_ids = [s.id for s, _ in ranked]
    pending_by_shift: dict[int, int] = {}
    applied_shift_ids: set[int] = set()
    if shift_ids:
        off_r = await db.execute(
            select(ShiftOffer).where(
                ShiftOffer.worker_id == wp.id,
                ShiftOffer.shift_id.in_(shift_ids),
                ShiftOffer.status == ShiftOfferStatus.pending,
            )
        )
        for o in off_r.scalars().all():
            pending_by_shift.setdefault(o.shift_id, o.id)
        app_r = await db.execute(
            select(ShiftAssignment.shift_id).where(
                ShiftAssignment.worker_id == wp.id,
                ShiftAssignment.shift_id.in_(shift_ids),
                ShiftAssignment.status == AssignmentStatus.applied,
            )
        )
        applied_shift_ids = {row[0] for row in app_r.all()}

    out = []
    for s, distance_m in ranked:
        job = await db.get(JobOrder, s.job_order_id)
        if not job:
            continue
        out.append(
            {
                "shift_id": s.id,
                "job_id": job.id,
                "title": job.title,
                "job_type": job.job_type,
                "starts_at": s.starts_at.isoformat(),
                "ends_at": s.ends_at.isoformat(),
                "location_address": job.location_address,
                "location_lat": job.location_lat,
                "location_lng": job.location_lng,
                "hourly_rate": job.hourly_rate,
                "per_shift_rate": job.per_shift_rate,
                "distance_m": distance_m,
                "pending_offer_id": pending_by_shift.get(s.id),
                "my_application_status": "applied" if s.id in applied_shift_ids else None,
            }
        )
    return out


@router.post("/marketplace/shifts/{shift_id}/dismiss")
async def dismiss_marketplace_shift(
    shift_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        raise HTTPException(404)
    shift = await db.get(Shift, shift_id)
    if not shift:
        raise HTTPException(404)
    job = await db.get(JobOrder, shift.job_order_id)
    if not job or job.status not in (JobOrderStatus.open, JobOrderStatus.partially_filled):
        raise HTTPException(400, detail="Shift not available in marketplace")
    now = datetime.now(timezone.utc)
    if shift.starts_at <= now:
        raise HTTPException(400, detail="Shift has already started")
    ex = await db.execute(
        select(MarketplaceShiftDismissal).where(
            MarketplaceShiftDismissal.worker_profile_id == wp.id,
            MarketplaceShiftDismissal.shift_id == shift_id,
        )
    )
    if ex.scalar_one_or_none():
        return {"ok": True}
    db.add(MarketplaceShiftDismissal(worker_profile_id=wp.id, shift_id=shift_id))
    await db.flush()
    return {"ok": True}


@router.post("/marketplace/shifts/{shift_id}/apply")
async def apply_marketplace_shift(
    shift_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        raise HTTPException(404)
    if wp.status == WorkerStatus.blacklisted:
        raise HTTPException(403, detail="Blacklisted workers cannot apply to shifts")
    shift = await db.get(Shift, shift_id)
    if not shift:
        raise HTTPException(404)
    job = await db.get(JobOrder, shift.job_order_id)
    if not job or job.status not in (JobOrderStatus.open, JobOrderStatus.partially_filled):
        raise HTTPException(400, detail="Shift not available in marketplace")
    now = datetime.now(timezone.utc)
    if shift.starts_at <= now:
        raise HTTPException(400, detail="Shift has already started")

    ex_a = await db.execute(
        select(ShiftAssignment).where(
            ShiftAssignment.shift_id == shift_id,
            ShiftAssignment.worker_id == wp.id,
        )
    )
    existing = ex_a.scalar_one_or_none()
    if existing:
        if existing.status == AssignmentStatus.applied:
            return {"ok": True, "assignment_status": existing.status.value, "assignment_id": existing.id}
        if existing.status == AssignmentStatus.confirmed:
            raise HTTPException(400, detail="You are already confirmed for this shift")
        if existing.status == AssignmentStatus.waitlisted:
            raise HTTPException(400, detail="You are already on the roster for this shift")
        if existing.status == AssignmentStatus.rejected:
            existing.status = AssignmentStatus.applied
            existing.waitlist_rank = await application_next_rank(db, shift_id)
            existing.match_score = 0.0
            existing.confirmed_at = None
            await _decline_pending_offers_for_shift_worker(db, shift_id, wp.id)
            await db.flush()
            await refresh_job_order_fill_status(db, job)
            return {"ok": True, "assignment_status": existing.status.value, "assignment_id": existing.id}
        raise HTTPException(400, detail="Cannot apply for this shift")

    rank = await application_next_rank(db, shift_id)
    sa = ShiftAssignment(
        shift_id=shift_id,
        worker_id=wp.id,
        status=AssignmentStatus.applied,
        waitlist_rank=rank,
        match_score=0.0,
    )
    db.add(sa)
    await _decline_pending_offers_for_shift_worker(db, shift_id, wp.id)
    await db.flush()
    await refresh_job_order_fill_status(db, job)
    await notify_user(
        db,
        user.id,
        title="Application sent",
        body=f"Your application for “{job.title}” is pending employer approval.",
    )
    return {"ok": True, "assignment_status": sa.status.value, "assignment_id": sa.id}


@router.post("/marketplace/shifts/{shift_id}/withdraw-application")
async def withdraw_marketplace_application(
    shift_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        raise HTTPException(404)
    ex = await db.execute(
        select(ShiftAssignment).where(
            ShiftAssignment.shift_id == shift_id,
            ShiftAssignment.worker_id == wp.id,
            ShiftAssignment.status == AssignmentStatus.applied,
        )
    )
    a = ex.scalar_one_or_none()
    if not a:
        raise HTTPException(404, detail="No pending application for this shift")
    shift = await db.get(Shift, shift_id)
    job = await db.get(JobOrder, shift.job_order_id) if shift else None
    await db.delete(a)
    await db.flush()
    if job:
        await refresh_job_order_fill_status(db, job)
    return {"ok": True}


@router.get("/clock/context")
async def worker_clock_context(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
    assignment_id: int | None = Query(
        None, description="Optional assignment to target (confirmed or completed after clock-out)",
    ),
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        return {"assignment": None}

    now = datetime.now(timezone.utc)

    if assignment_id is not None:
        r_sel = await db.execute(
            select(ShiftAssignment)
            .options(selectinload(ShiftAssignment.shift).selectinload(Shift.job_order))
            .where(
                ShiftAssignment.id == assignment_id,
                ShiftAssignment.worker_id == wp.id,
                ShiftAssignment.status.in_((AssignmentStatus.confirmed, AssignmentStatus.completed)),
            )
        )
        a = r_sel.scalar_one_or_none()
        if not a:
            raise HTTPException(404, detail="Assignment not found")
    else:
        r2 = await db.execute(
            select(ShiftAssignment)
            .options(selectinload(ShiftAssignment.shift).selectinload(Shift.job_order))
            .join(Shift, ShiftAssignment.shift_id == Shift.id)
            .where(
                ShiftAssignment.worker_id == wp.id,
                ShiftAssignment.status == AssignmentStatus.confirmed,
                Shift.ends_at > now,
            )
            .order_by(Shift.starts_at.asc())
        )
        a = r2.scalars().first()
        if not a:
            return {"assignment": None}

    shift = a.shift
    job = shift.job_order
    ar = await db.execute(select(AttendanceRecord).where(AttendanceRecord.shift_assignment_id == a.id))
    rec = ar.scalar_one_or_none()
    has_in = bool(rec and rec.clock_in_time)
    has_out = bool(rec and rec.clock_out_time)

    can_clock_in_now = (
        not has_in
        and not has_out
        and not is_past_shift_end(now, shift.ends_at)
        and not is_clock_in_too_early(now, shift.starts_at)
        and not is_past_clock_in_grace_deadline(now, shift.starts_at)
    )

    return {
        "assignment": {
            "assignment_id": a.id,
            "shift_id": shift.id,
            "job_title": job.title,
            "job_site_lat": job.location_lat,
            "job_site_lng": job.location_lng,
            "geofence_radius_m": job.geofence_radius_m,
            "starts_at": shift.starts_at.isoformat(),
            "ends_at": shift.ends_at.isoformat(),
            "clock_in_allowed_not_before": clock_in_earliest_utc(shift.starts_at).isoformat(),
            "clock_in_grace_ends_at": late_threshold_utc(shift.starts_at).isoformat(),
            "already_clocked_in": has_in,
            "already_clocked_out": has_out,
            "is_late_window": is_late_window_without_clock_in(now, shift.starts_at, has_in),
            "can_clock_in_now": can_clock_in_now,
        }
    }


@router.get("/my-shifts")
async def my_shifts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        return []
    now = datetime.now(timezone.utc)
    r2 = await db.execute(
        select(ShiftAssignment)
        .options(selectinload(ShiftAssignment.shift).selectinload(Shift.job_order))
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .where(
            ShiftAssignment.worker_id == wp.id,
            ShiftAssignment.status.in_(
                (AssignmentStatus.confirmed, AssignmentStatus.waitlisted, AssignmentStatus.applied),
            ),
            Shift.ends_at > now,
        )
        .order_by(Shift.starts_at.asc())
    )
    rows = r2.scalars().all()
    return [
        {
            "assignment_id": a.id,
            "status": a.status.value,
            "shift": {
                "id": a.shift.id,
                "starts_at": a.shift.starts_at.isoformat(),
                "ends_at": a.shift.ends_at.isoformat(),
                "job_title": a.shift.job_order.title,
            },
        }
        for a in rows
    ]


@router.get("/schedule")
async def worker_schedule(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        return {"confirmed": [], "pending_applications": [], "past_shifts": []}
    now = datetime.now(timezone.utc)
    r2 = await db.execute(
        select(ShiftAssignment)
        .options(selectinload(ShiftAssignment.shift).selectinload(Shift.job_order))
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .where(
            ShiftAssignment.worker_id == wp.id,
            ShiftAssignment.status.in_(
                (
                    AssignmentStatus.confirmed,
                    AssignmentStatus.waitlisted,
                    AssignmentStatus.applied,
                    AssignmentStatus.completed,
                    AssignmentStatus.cancelled,
                    AssignmentStatus.rejected,
                )
            ),
        )
        .order_by(Shift.starts_at.asc())
    )
    rows = r2.scalars().all()

    def _item(a: ShiftAssignment) -> dict:
        job = a.shift.job_order
        effective_status = _effective_assignment_status(a, now=now)
        return {
            "assignment_id": a.id,
            "status": effective_status.value,
            "shift": {
                "id": a.shift.id,
                "starts_at": a.shift.starts_at.isoformat(),
                "ends_at": a.shift.ends_at.isoformat(),
                "job_title": job.title if job else "",
                "job_id": a.shift.job_order_id,
            },
        }

    confirmed = [
        _item(a)
        for a in rows
        if _effective_assignment_status(a, now=now) == AssignmentStatus.confirmed and _as_utc(a.shift.ends_at) >= now
    ]
    pending = [
        _item(a)
        for a in rows
        if _effective_assignment_status(a, now=now) in (AssignmentStatus.applied, AssignmentStatus.waitlisted)
    ]
    past = [
        _item(a)
        for a in rows
        if _as_utc(a.shift.ends_at) < now
        or _effective_assignment_status(a, now=now)
        in (AssignmentStatus.completed, AssignmentStatus.cancelled, AssignmentStatus.rejected)
    ]
    return {
        "confirmed": confirmed,
        "pending_applications": pending,
        "past_shifts": sorted(past, key=lambda x: x["shift"]["starts_at"], reverse=True),
    }


@router.get("/history")
async def worker_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
    status: str = Query("all", description="all | accepted | waitlisted | pending | rejected"),
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        return []
    _history_statuses_for_query(status)
    statuses = _HISTORY_STATUSES_ALL
    now = datetime.now(timezone.utc)
    r2 = await db.execute(
        select(ShiftAssignment)
        .options(selectinload(ShiftAssignment.shift).selectinload(Shift.job_order))
        .where(
            ShiftAssignment.worker_id == wp.id,
            ShiftAssignment.status.in_(statuses),
        )
    )
    rows = list(r2.scalars().all())
    rows.sort(key=lambda a: a.shift.starts_at, reverse=True)
    out = []
    for a in rows:
        effective_status = _effective_assignment_status(a, now=now)
        history_bucket = _history_bucket_for_status(effective_status)
        if not _history_bucket_matches_query(history_bucket, status):
            continue
        job = a.shift.job_order
        out.append(
            {
                "assignment_id": a.id,
                "status": effective_status.value,
                "history_bucket": history_bucket,
                "waitlist_rank": a.waitlist_rank,
                "job_id": job.id,
                "job_title": job.title,
                "job_type": job.job_type,
                "location_address": job.location_address,
                "shift": {
                    "id": a.shift.id,
                    "starts_at": a.shift.starts_at.isoformat(),
                    "ends_at": a.shift.ends_at.isoformat(),
                },
            }
        )
    return out


@router.post("/assignments/{assignment_id}/cancel")
async def cancel_assignment(
    assignment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        raise HTTPException(404)
    a = await db.get(ShiftAssignment, assignment_id)
    if not a or a.worker_id != wp.id:
        raise HTTPException(404)
    shift = await db.get(Shift, a.shift_id)
    if not shift:
        raise HTTPException(404, detail="Shift not found")
    settings = get_settings()
    threshold_hours = max(0, int(getattr(settings, "shift_attendance_change_cutoff_hours", 4)))
    start = shift.starts_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    seconds_until_start = (start - datetime.now(timezone.utc)).total_seconds()
    is_late_cancellation = seconds_until_start < threshold_hours * 3600
    if is_late_cancellation:
        wp.late_cancel_count = (wp.late_cancel_count or 0) + 1
        await adjust_worker_points(db, wp.id, POINTS_PENALTY_LATE_CANCEL)
    a.status = AssignmentStatus.cancelled
    job = await db.get(JobOrder, shift.job_order_id)
    if is_late_cancellation:
        ta_rows = await db.execute(select(User).where(User.role == UserRole.ta))
        for ta_user in ta_rows.scalars().all():
            await notify_user(
                db,
                ta_user.id,
                title="Late cancellation alert",
                body=f"Worker #{wp.id} cancelled assignment #{assignment_id} within {threshold_hours}h of shift start.",
                payload={
                    "type": "late_cancellation",
                    "worker_profile_id": wp.id,
                    "assignment_id": assignment_id,
                    "shift_id": shift.id,
                    "threshold_hours": threshold_hours,
                },
            )
        await _auto_notify_next_waitlisted_worker(db, shift.id, assignment_id)
    await refresh_job_order_fill_status(db, job)
    return {"ok": True, "late_cancellation": is_late_cancellation, "threshold_hours": threshold_hours}
