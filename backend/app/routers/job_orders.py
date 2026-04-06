from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import (
    AssignmentStatus,
    ClientOrganization,
    JobOrder,
    JobOrderStatus,
    PayModel,
    Shift,
    ShiftAssignment,
    ShiftOffer,
    ShiftOfferStatus,
    User,
    UserRole,
    PreferredWorker,
    WorkerProfile,
)
from app.schemas.job_orders import (
    JobAssignmentWorkerOut,
    JobDeclinedWorkerOut,
    JobOrderCreate,
    JobOrderDetail,
    JobOrderOut,
    JobRejectedWorkerOut,
    ShiftOut,
)
from app.schemas.workers import WorkerProfileOut
from app.routers.workers import _profile_out
from app.services.audit import log_audit
from app.services.dispatch import confirmed_count, publish_job_order, waitlist_next_rank
from app.services.job_status import refresh_job_order_fill_status
from app.services.ta_client_contracts import (
    get_active_contract_for_org,
    list_contracted_org_ids_for_ta,
    ta_has_active_contract_with_org,
    user_can_vet_shift_assignments,
)

router = APIRouter(prefix="/job-orders", tags=["job-orders"])


async def _can_access_job(db: AsyncSession, user: User, job: JobOrder) -> bool:
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.client:
        return user.client_org_id == job.client_org_id
    if user.role == UserRole.ta:
        return await ta_has_active_contract_with_org(db, user.id, job.client_org_id)
    return False


@router.post("", response_model=JobOrderOut)
async def create_job_order(
    body: JobOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.client, UserRole.admin))],
):
    if user.role == UserRole.client and not user.client_org_id:
        raise HTTPException(400, detail="Client user not linked to organization")
    client_org_id = user.client_org_id
    if user.role in (UserRole.ta, UserRole.admin):
        # TA creates on behalf — require client_org_id in body for MVP use query param
        raise HTTPException(
            400,
            detail="TA must use POST /job-orders/for-client/{client_org_id} or provide client in seed",
        )
    try:
        pay_model = PayModel(body.pay_model)
    except ValueError:
        raise HTTPException(400, detail="Invalid pay_model")

    job = JobOrder(
        client_org_id=client_org_id,
        created_by_user_id=user.id,
        title=body.title,
        job_type=body.job_type,
        location_address=body.location_address,
        location_lat=body.location_lat,
        location_lng=body.location_lng,
        workers_required_total=body.workers_required_total,
        hourly_rate=body.hourly_rate,
        per_shift_rate=body.per_shift_rate,
        pay_model=pay_model,
        required_skills=body.required_skills,
        required_certifications=body.required_certifications,
        uniform_notes=body.uniform_notes,
        special_instructions=body.special_instructions,
        geofence_radius_m=body.geofence_radius_m,
        acceptance_window_minutes=body.acceptance_window_minutes,
        status=JobOrderStatus.draft,
    )
    db.add(job)
    await db.flush()
    for s in body.shifts:
        db.add(
            Shift(
                job_order_id=job.id,
                starts_at=s.starts_at,
                ends_at=s.ends_at,
                workers_required=s.workers_required,
            )
        )
    await db.flush()
    await log_audit(
        db,
        actor_user_id=user.id,
        action="job_order_create",
        entity_type="JobOrder",
        entity_id=str(job.id),
    )
    return await _to_out(db, job)


@router.post("/for-client/{client_org_id}", response_model=JobOrderOut)
async def create_job_order_for_client(
    client_org_id: int,
    body: JobOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    org = await db.get(ClientOrganization, client_org_id)
    if not org:
        raise HTTPException(404, detail="Client organization not found")
    if user.role == UserRole.ta and not await ta_has_active_contract_with_org(db, user.id, client_org_id):
        raise HTTPException(403, detail="No active contract with this client organization")
    try:
        pay_model = PayModel(body.pay_model)
    except ValueError:
        raise HTTPException(400, detail="Invalid pay_model")
    job = JobOrder(
        client_org_id=client_org_id,
        created_by_user_id=user.id,
        title=body.title,
        job_type=body.job_type,
        location_address=body.location_address,
        location_lat=body.location_lat,
        location_lng=body.location_lng,
        workers_required_total=body.workers_required_total,
        hourly_rate=body.hourly_rate,
        per_shift_rate=body.per_shift_rate,
        pay_model=pay_model,
        required_skills=body.required_skills,
        required_certifications=body.required_certifications,
        uniform_notes=body.uniform_notes,
        special_instructions=body.special_instructions,
        geofence_radius_m=body.geofence_radius_m,
        acceptance_window_minutes=body.acceptance_window_minutes,
        status=JobOrderStatus.draft,
    )
    db.add(job)
    await db.flush()
    for s in body.shifts:
        db.add(
            Shift(
                job_order_id=job.id,
                starts_at=s.starts_at,
                ends_at=s.ends_at,
                workers_required=s.workers_required,
            )
        )
    await db.flush()
    await log_audit(db, actor_user_id=user.id, action="job_order_create", entity_type="JobOrder", entity_id=str(job.id))
    return await _to_out(db, job)


async def _accepted_and_declined_for_job(
    db: AsyncSession, job_id: int
) -> tuple[list[JobAssignmentWorkerOut], list[JobDeclinedWorkerOut]]:
    pref_worker_ids: set[int] = set()
    r_pref = await db.execute(
        select(PreferredWorker.worker_id)
        .join(JobOrder, PreferredWorker.client_org_id == JobOrder.client_org_id)
        .where(JobOrder.id == job_id)
    )
    pref_worker_ids = set(r_pref.scalars().all())

    r = await db.execute(
        select(ShiftAssignment, Shift, WorkerProfile)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .join(WorkerProfile, ShiftAssignment.worker_id == WorkerProfile.id)
        .where(
            Shift.job_order_id == job_id,
            ShiftAssignment.status.in_(
                (AssignmentStatus.confirmed, AssignmentStatus.waitlisted, AssignmentStatus.applied),
            ),
        )
    )
    accepted: list[JobAssignmentWorkerOut] = []
    for a, sh, wp in r.all():
        accepted.append(
            JobAssignmentWorkerOut(
                assignment_id=a.id,
                shift_id=sh.id,
                shift_starts_at=sh.starts_at,
                shift_ends_at=sh.ends_at,
                worker_profile_id=wp.id,
                worker_name=(wp.full_name or "").strip() or "—",
                assignment_status=a.status.value,
                match_score=a.match_score,
                applied_at=a.created_at,
                rating_avg=float(wp.rating_avg or 0.0),
                certifications_count=len(wp.certifications or []),
                worker_skills=list(wp.skills or []),
                worker_certifications=list(wp.certifications or []),
                location_lat=wp.location_lat,
                location_lng=wp.location_lng,
                is_preferred=wp.id in pref_worker_ids,
            )
        )
    accepted.sort(key=lambda x: (x.shift_starts_at, x.worker_name.lower()))

    r_skip = await db.execute(
        select(ShiftAssignment.shift_id, ShiftAssignment.worker_id)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .where(
            Shift.job_order_id == job_id,
            ShiftAssignment.status != AssignmentStatus.rejected,
        )
    )
    skip_declined_for: set[tuple[int, int]] = {(sid, wid) for sid, wid in r_skip.all()}

    r2 = await db.execute(
        select(ShiftOffer, Shift, WorkerProfile)
        .join(Shift, ShiftOffer.shift_id == Shift.id)
        .join(WorkerProfile, ShiftOffer.worker_id == WorkerProfile.id)
        .where(
            Shift.job_order_id == job_id,
            ShiftOffer.status == ShiftOfferStatus.declined,
        )
    )
    declined: list[JobDeclinedWorkerOut] = []
    for o, sh, wp in r2.all():
        if (sh.id, wp.id) in skip_declined_for:
            continue
        declined.append(
            JobDeclinedWorkerOut(
                offer_id=o.id,
                shift_id=sh.id,
                shift_starts_at=sh.starts_at,
                shift_ends_at=sh.ends_at,
                worker_profile_id=wp.id,
                worker_name=(wp.full_name or "").strip() or "—",
            )
        )
    declined.sort(key=lambda x: (x.shift_starts_at, x.worker_name.lower()))
    return accepted, declined


async def _rejected_workers_for_job(db: AsyncSession, job_id: int) -> list[JobRejectedWorkerOut]:
    r = await db.execute(
        select(ShiftAssignment, Shift, WorkerProfile)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .join(WorkerProfile, ShiftAssignment.worker_id == WorkerProfile.id)
        .where(
            Shift.job_order_id == job_id,
            ShiftAssignment.status == AssignmentStatus.rejected,
        )
    )
    out: list[JobRejectedWorkerOut] = []
    for a, sh, wp in r.all():
        out.append(
            JobRejectedWorkerOut(
                assignment_id=a.id,
                shift_id=sh.id,
                shift_starts_at=sh.starts_at,
                shift_ends_at=sh.ends_at,
                worker_profile_id=wp.id,
                worker_name=(wp.full_name or "").strip() or "—",
                assignment_status=a.status.value,
                match_score=a.match_score,
            )
        )
    out.sort(key=lambda x: (x.shift_starts_at, x.worker_name.lower()))
    return out


async def _slot_totals(db: AsyncSession, job_id: int) -> tuple[int, int]:
    total_slots = await db.scalar(
        select(func.coalesce(func.sum(Shift.workers_required), 0)).where(Shift.job_order_id == job_id)
    )
    filled = await db.scalar(
        select(func.count(ShiftAssignment.id))
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .where(
            Shift.job_order_id == job_id,
            ShiftAssignment.status == AssignmentStatus.confirmed,
        )
    )
    return int(total_slots or 0), int(filled or 0)


async def _to_out(db: AsyncSession, job: JobOrder) -> JobOrderOut:
    await refresh_job_order_fill_status(db, job)
    total_slots, filled = await _slot_totals(db, job.id)
    return JobOrderOut(
        id=job.id,
        client_org_id=job.client_org_id,
        title=job.title,
        job_type=job.job_type,
        status=job.status.value,
        location_address=job.location_address,
        location_lat=job.location_lat,
        location_lng=job.location_lng,
        workers_required_total=job.workers_required_total,
        pay_model=job.pay_model.value,
        geofence_radius_m=job.geofence_radius_m,
        filled_slots=filled,
        total_slots=total_slots,
    )


async def _to_detail_out(db: AsyncSession, job: JobOrder, viewer: User) -> JobOrderDetail:
    await refresh_job_order_fill_status(db, job)
    total_slots, filled = await _slot_totals(db, job.id)
    shifts_sorted = sorted(job.shifts, key=lambda s: s.starts_at)
    accepted_workers, declined_workers = await _accepted_and_declined_for_job(db, job.id)
    rejected_workers = await _rejected_workers_for_job(db, job.id)
    contract = await get_active_contract_for_org(db, job.client_org_id)
    has_ta_payroll = contract is not None
    viewer_can_vet = await user_can_vet_shift_assignments(db, viewer, job)
    return JobOrderDetail(
        id=job.id,
        client_org_id=job.client_org_id,
        title=job.title,
        job_type=job.job_type,
        status=job.status.value,
        location_address=job.location_address,
        location_lat=job.location_lat,
        location_lng=job.location_lng,
        workers_required_total=job.workers_required_total,
        pay_model=job.pay_model.value,
        geofence_radius_m=job.geofence_radius_m,
        filled_slots=filled,
        total_slots=total_slots,
        hourly_rate=job.hourly_rate,
        per_shift_rate=job.per_shift_rate,
        required_skills=list(job.required_skills or []),
        required_certifications=list(job.required_certifications or []),
        uniform_notes=job.uniform_notes,
        special_instructions=job.special_instructions,
        acceptance_window_minutes=job.acceptance_window_minutes,
        published_at=job.published_at,
        shifts=[ShiftOut.model_validate(s) for s in shifts_sorted],
        accepted_workers=accepted_workers,
        declined_workers=declined_workers,
        rejected_workers=rejected_workers,
        has_ta_payroll=has_ta_payroll,
        viewer_can_vet_assignments=viewer_can_vet,
    )


async def _assignment_with_access(
    db: AsyncSession,
    assignment_id: int,
    user: User,
) -> tuple[ShiftAssignment, Shift, JobOrder]:
    a = await db.get(ShiftAssignment, assignment_id)
    if not a:
        raise HTTPException(404, detail="Assignment not found")
    shift = await db.get(Shift, a.shift_id)
    if not shift:
        raise HTTPException(404)
    job = await db.get(JobOrder, shift.job_order_id)
    if not job or not await _can_access_job(db, user, job):
        raise HTTPException(404)
    return a, shift, job


@router.post("/assignments/{assignment_id}/promote-from-waitlist")
async def promote_assignment_from_waitlist(
    assignment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.client, UserRole.admin))],
):
    a, shift, job = await _assignment_with_access(db, assignment_id, user)
    if not await user_can_vet_shift_assignments(db, user, job):
        raise HTTPException(403, detail="You cannot vet workers for this job")
    if a.status not in (AssignmentStatus.waitlisted, AssignmentStatus.applied):
        raise HTTPException(400, detail="Only waitlisted workers or pending applications can be accepted")
    cc = await confirmed_count(db, shift.id)
    if cc >= shift.workers_required:
        raise HTTPException(400, detail="Shift is already at required headcount")
    a.status = AssignmentStatus.confirmed
    a.waitlist_rank = None
    a.confirmed_at = datetime.now(timezone.utc)
    await db.flush()
    await refresh_job_order_fill_status(db, job)
    await log_audit(
        db,
        actor_user_id=user.id,
        action="assignment_promote_waitlist",
        entity_type="ShiftAssignment",
        entity_id=str(assignment_id),
    )
    return {"ok": True, "status": a.status.value}


@router.post("/assignments/{assignment_id}/reject")
async def reject_assignment(
    assignment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.client, UserRole.admin))],
):
    a, shift, job = await _assignment_with_access(db, assignment_id, user)
    if not await user_can_vet_shift_assignments(db, user, job):
        raise HTTPException(403, detail="You cannot vet workers for this job")
    if a.status == AssignmentStatus.rejected:
        return {"ok": True, "status": a.status.value}
    if a.status not in (AssignmentStatus.confirmed, AssignmentStatus.waitlisted, AssignmentStatus.applied):
        raise HTTPException(400, detail="Can only reject confirmed, waitlisted, or pending applications")
    a.status = AssignmentStatus.rejected
    a.waitlist_rank = None
    a.confirmed_at = None
    await db.flush()
    await refresh_job_order_fill_status(db, job)
    await log_audit(
        db,
        actor_user_id=user.id,
        action="assignment_reject",
        entity_type="ShiftAssignment",
        entity_id=str(assignment_id),
    )
    return {"ok": True, "status": a.status.value}


@router.post("/assignments/{assignment_id}/move-to-waitlist")
async def move_assignment_to_waitlist(
    assignment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.client, UserRole.admin))],
):
    a, shift, job = await _assignment_with_access(db, assignment_id, user)
    if not await user_can_vet_shift_assignments(db, user, job):
        raise HTTPException(403, detail="You cannot vet workers for this job")
    if a.status != AssignmentStatus.confirmed:
        raise HTTPException(400, detail="Only confirmed assignments can be moved to the waitlist")
    rank = await waitlist_next_rank(db, shift.id)
    a.status = AssignmentStatus.waitlisted
    a.waitlist_rank = rank
    a.confirmed_at = None
    await db.flush()
    await refresh_job_order_fill_status(db, job)
    await log_audit(
        db,
        actor_user_id=user.id,
        action="assignment_move_waitlist",
        entity_type="ShiftAssignment",
        entity_id=str(assignment_id),
    )
    return {"ok": True, "status": a.status.value}


@router.get("", response_model=list[JobOrderOut])
async def list_job_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.client, UserRole.admin))],
):
    stmt = select(JobOrder).options(selectinload(JobOrder.shifts))
    if user.role == UserRole.client:
        stmt = stmt.where(JobOrder.client_org_id == user.client_org_id)
    elif user.role == UserRole.ta:
        org_ids = await list_contracted_org_ids_for_ta(db, user.id)
        if not org_ids:
            return []
        stmt = stmt.where(JobOrder.client_org_id.in_(org_ids))
    r = await db.execute(stmt.order_by(JobOrder.id.desc()))
    jobs = r.scalars().unique().all()
    out = []
    for j in jobs:
        if await _can_access_job(db, user, j):
            out.append(await _to_out(db, j))
    return out


@router.get("/{job_id}/worker-profiles/{worker_profile_id}", response_model=WorkerProfileOut)
async def get_job_worker_profile(
    job_id: int,
    worker_profile_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.client, UserRole.admin))],
):
    job = await db.get(JobOrder, job_id)
    if not job or not await _can_access_job(db, user, job):
        raise HTTPException(404)
    linked_sa = await db.execute(
        select(ShiftAssignment.id)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .where(Shift.job_order_id == job_id, ShiftAssignment.worker_id == worker_profile_id)
        .limit(1)
    )
    if not linked_sa.scalar_one_or_none():
        linked_of = await db.execute(
            select(ShiftOffer.id)
            .join(Shift, ShiftOffer.shift_id == Shift.id)
            .where(Shift.job_order_id == job_id, ShiftOffer.worker_id == worker_profile_id)
            .limit(1)
        )
        if not linked_of.scalar_one_or_none():
            raise HTTPException(404, detail="Worker is not associated with this job")
    wp = await db.get(WorkerProfile, worker_profile_id)
    if not wp:
        raise HTTPException(404)
    u = await db.get(User, wp.user_id)
    if not u:
        raise HTTPException(404)
    return _profile_out(wp, u)


@router.get("/{job_id}", response_model=JobOrderDetail)
async def get_job_order(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.client, UserRole.admin))],
):
    r = await db.execute(
        select(JobOrder).options(selectinload(JobOrder.shifts)).where(JobOrder.id == job_id)
    )
    job = r.scalar_one_or_none()
    if not job or not await _can_access_job(db, user, job):
        raise HTTPException(404)
    return await _to_detail_out(db, job, user)


@router.post("/{job_id}/publish")
async def publish_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.client, UserRole.admin))],
):
    r = await db.execute(
        select(JobOrder).options(selectinload(JobOrder.shifts)).where(JobOrder.id == job_id)
    )
    job = r.scalar_one_or_none()
    if not job or not await _can_access_job(db, user, job):
        raise HTTPException(404)
    if job.status != JobOrderStatus.draft:
        raise HTTPException(400, detail="Only draft job orders can be published")
    if not job.shifts:
        raise HTTPException(400, detail="Add at least one shift before publishing")
    await publish_job_order(db, job)
    await refresh_job_order_fill_status(db, job)
    await log_audit(db, actor_user_id=user.id, action="job_order_publish", entity_type="JobOrder", entity_id=str(job_id))
    return {"ok": True, "status": job.status.value}


@router.post("/{job_id}/cancel")
async def cancel_job_order(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.client, UserRole.admin))],
):
    job = await db.get(JobOrder, job_id)
    if not job or not await _can_access_job(db, user, job):
        raise HTTPException(404)
    if job.status == JobOrderStatus.cancelled:
        return {"ok": True, "status": job.status.value}
    if job.status == JobOrderStatus.completed:
        raise HTTPException(400, detail="Cannot cancel a completed job")
    if user.role == UserRole.client:
        if job.status not in (JobOrderStatus.draft, JobOrderStatus.open):
            raise HTTPException(400, detail="You can only cancel draft or open job orders")
    job.status = JobOrderStatus.cancelled
    await log_audit(
        db,
        actor_user_id=user.id,
        action="job_order_cancel",
        entity_type="JobOrder",
        entity_id=str(job_id),
    )
    return {"ok": True, "status": job.status.value}


@router.post("/{job_id}/complete")
async def complete_job_order(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    job = await db.get(JobOrder, job_id)
    if not job or not await _can_access_job(db, user, job):
        raise HTTPException(404)
    if job.status in (JobOrderStatus.draft, JobOrderStatus.cancelled):
        raise HTTPException(400, detail="Cannot complete draft or cancelled job")
    if job.status == JobOrderStatus.completed:
        return {"ok": True, "status": job.status.value}
    job.status = JobOrderStatus.completed
    await log_audit(
        db,
        actor_user_id=user.id,
        action="job_order_complete",
        entity_type="JobOrder",
        entity_id=str(job_id),
    )
    return {"ok": True, "status": job.status.value}
