from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import (
    ClientProfile,
    AssignmentStatus,
    AttendanceRecord,
    AttendanceStatus,
    ClientOrganization,
    JobOrder,
    PreferredWorker,
    Shift,
    ShiftAssignment,
    User,
    UserRole,
    WorkerProfile,
)
from app.schemas.client_profile import ClientOnboardingCompleteIn, ClientProfileIn, ClientProfileOut
from app.auth.attendance_qr_tokens import create_attendance_qr_token
from app.services.absence_strikes import record_absence_strike_if_eligible
from app.services.attendance_rules import (
    is_grace_period_late_punch,
    is_late_window_without_clock_in,
    is_past_clock_in_grace_deadline,
)
from app.services.notifications import notify_user
from app.services.ta_client_contracts import get_active_contract_for_org
from app.services.worker_ratings import upsert_client_rating_for_assignment

router = APIRouter(prefix="/client", tags=["client-portal"])


def _client_profile_flags(cp: ClientProfile) -> dict[str, bool]:
    return {
        "company_name": bool(cp.company_name and cp.company_name.strip()),
        "contact_name": bool(cp.contact_name and cp.contact_name.strip()),
        "contact_email": bool(cp.contact_email and cp.contact_email.strip()),
        "contact_phone": bool(cp.contact_phone and cp.contact_phone.strip()),
        "address": bool(cp.address_line and cp.address_line.strip()),
        "location": cp.location_lat is not None and cp.location_lng is not None,
        "billing": bool(cp.billing_notes and cp.billing_notes.strip()),
        "pdpa_consent": bool(cp.pdpa_consent_at),
        "terms_accepted": bool(cp.terms_accepted_at),
    }


def _client_profile_completeness(cp: ClientProfile) -> int:
    f = _client_profile_flags(cp)
    s = 0
    if f["company_name"]:
        s += 20
    if f["contact_name"]:
        s += 20
    if f["contact_email"]:
        s += 15
    if f["contact_phone"]:
        s += 15
    if f["address"]:
        s += 10
    if f["location"]:
        s += 5
    if f["billing"]:
        s += 5
    if f["pdpa_consent"]:
        s += 5
    if f["terms_accepted"]:
        s += 5
    return min(100, s)


def _client_profile_out(cp: ClientProfile) -> ClientProfileOut:
    return ClientProfileOut(
        id=cp.id,
        company_name=cp.company_name,
        contact_name=cp.contact_name,
        contact_email=cp.contact_email,
        contact_phone=cp.contact_phone,
        address_line=cp.address_line,
        location_lat=cp.location_lat,
        location_lng=cp.location_lng,
        billing_notes=cp.billing_notes,
        profile_completeness_pct=cp.profile_completeness_pct,
        pdpa_consent=bool(cp.pdpa_consent_at),
        terms_accepted=bool(cp.terms_accepted_at),
        onboarding_completed=bool(cp.onboarding_completed_at),
    )


async def _ensure_client_profile(db: AsyncSession, user: User) -> ClientProfile:
    r = await db.execute(select(ClientProfile).where(ClientProfile.user_id == user.id))
    cp = r.scalar_one_or_none()
    if cp:
        return cp
    company_name = ""
    if user.client_org_id:
        org = await db.get(ClientOrganization, user.client_org_id)
        if org and org.name:
            company_name = str(org.name)
    cp = ClientProfile(
        user_id=user.id,
        company_name=company_name,
        contact_email=user.email,
    )
    db.add(cp)
    await db.flush()
    return cp


async def _sync_client_org_name_from_profile(db: AsyncSession, user: User, cp: ClientProfile) -> None:
    """Keep ClientOrganization.name aligned with profile company name for TA/worker-facing labels."""
    if not user.client_org_id:
        return
    desired = (cp.company_name or "").strip()
    if not desired:
        return
    org = await db.get(ClientOrganization, user.client_org_id)
    if not org or org.name == desired:
        return
    org.name = desired


@router.get("/me/profile", response_model=ClientProfileOut)
async def get_my_client_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    cp = await _ensure_client_profile(db, user)
    cp.profile_completeness_pct = _client_profile_completeness(cp)
    await _sync_client_org_name_from_profile(db, user, cp)
    await db.flush()
    return _client_profile_out(cp)


@router.put("/me/profile", response_model=ClientProfileOut)
async def update_my_client_profile(
    body: ClientProfileIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    cp = await _ensure_client_profile(db, user)
    # Always take submitted company name (onboarding + profile page send full payload).
    cp.company_name = (body.company_name or "").strip()
    cp.contact_name = body.contact_name or cp.contact_name
    cp.contact_email = (body.contact_email.strip().lower() if body.contact_email else None) or cp.contact_email
    cp.contact_phone = (body.contact_phone.strip() if body.contact_phone else None) or cp.contact_phone
    if body.address_line is not None:
        cp.address_line = body.address_line.strip() or None
    if body.billing_notes is not None:
        cp.billing_notes = body.billing_notes.strip() or None
    if body.location_lat is not None:
        cp.location_lat = body.location_lat
    if body.location_lng is not None:
        cp.location_lng = body.location_lng
    cp.profile_completeness_pct = _client_profile_completeness(cp)
    await _sync_client_org_name_from_profile(db, user, cp)
    await db.flush()
    return _client_profile_out(cp)


@router.post("/me/pdpa-consent")
async def client_pdpa_consent(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    cp = await _ensure_client_profile(db, user)
    cp.pdpa_consent_at = datetime.now(timezone.utc)
    cp.profile_completeness_pct = _client_profile_completeness(cp)
    await db.flush()
    return {"ok": True}


@router.post("/me/onboarding/complete")
async def client_onboarding_complete(
    body: ClientOnboardingCompleteIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    if not body.terms_accepted:
        raise HTTPException(status_code=400, detail="Terms must be accepted")
    cp = await _ensure_client_profile(db, user)
    now = datetime.now(timezone.utc)
    cp.terms_accepted_at = now
    if not cp.pdpa_consent_at:
        cp.pdpa_consent_at = now
    cp.onboarding_completed_at = now
    cp.profile_completeness_pct = _client_profile_completeness(cp)
    await _sync_client_org_name_from_profile(db, user, cp)
    await db.flush()
    return {"ok": True, "profile_completeness_pct": cp.profile_completeness_pct}


async def _live_worker_row(
    db: AsyncSession,
    shift: Shift,
    assignment: ShiftAssignment,
    now: datetime,
) -> dict:
    ar = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.shift_assignment_id == assignment.id)
    )
    att = ar.scalar_one_or_none()
    wp = await db.get(WorkerProfile, assignment.worker_id)
    has_clock_in = bool(att and att.clock_in_time)
    if not has_clock_in and is_past_clock_in_grace_deadline(now, shift.starts_at):
        if not att:
            att = AttendanceRecord(
                shift_assignment_id=assignment.id,
                status=AttendanceStatus.absent,
            )
            db.add(att)
            await db.flush()
        else:
            att.status = AttendanceStatus.absent
        if assignment.status == AssignmentStatus.confirmed and wp:
            await record_absence_strike_if_eligible(db, assignment, att, wp, actor_user_id=None)
        if att.absent_after_grace_ta_notified_at is None:
            job = await db.get(JobOrder, shift.job_order_id)
            notify_uid: int | None = None
            if job:
                contract = await get_active_contract_for_org(db, job.client_org_id)
                if contract:
                    notify_uid = contract.ta_user_id
                else:
                    creator = await db.get(User, job.created_by_user_id)
                    if (
                        creator
                        and creator.role == UserRole.client
                        and creator.client_org_id == job.client_org_id
                    ):
                        notify_uid = creator.id
            if notify_uid is not None:
                await notify_user(
                    db,
                    notify_uid,
                    title="Worker absent after grace period",
                    body=f"Worker {wp.full_name if wp and wp.full_name else assignment.worker_id} missed clock-in for shift {shift.id} (job {shift.job_order_id}).",
                    payload={"shift_id": shift.id, "job_id": shift.job_order_id, "assignment_id": assignment.id},
                )
            att.absent_after_grace_ta_notified_at = now
    stored = att.status if att else None
    derived_late = bool(att and att.clock_in_time and is_grace_period_late_punch(att.clock_in_time, shift.starts_at))
    not_in_late = is_late_window_without_clock_in(now, shift.starts_at, has_clock_in)
    show_late_badge = bool(derived_late or (stored == AttendanceStatus.late))
    show_absent_badge = bool(not has_clock_in and stored == AttendanceStatus.absent)
    attendance_status: str | None
    if att:
        if show_absent_badge:
            attendance_status = AttendanceStatus.absent.value
        elif derived_late or stored == AttendanceStatus.late:
            attendance_status = AttendanceStatus.late.value
        elif stored:
            attendance_status = stored.value
        else:
            attendance_status = AttendanceStatus.unverified.value
    else:
        attendance_status = None
    return {
        "worker_name": wp.full_name if wp else "",
        "assignment_id": assignment.id,
        "shift_id": shift.id,
        "scheduled_start": shift.starts_at.isoformat(),
        "clock_in": att.clock_in_time.isoformat() if att and att.clock_in_time else None,
        "clock_out": att.clock_out_time.isoformat() if att and att.clock_out_time else None,
        "geofence_ok": att.clock_in_geofence_valid if att else None,
        "photo_in": att.clock_in_photo_url if att else None,
        "attendance_status": attendance_status,
        "show_late_badge": show_late_badge,
        "not_checked_in_late": bool(not_in_late and not show_absent_badge),
        "show_absent_badge": show_absent_badge,
    }


@router.post("/preferred-workers/{worker_profile_id}")
async def flag_preferred(
    worker_profile_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    if not user.client_org_id:
        raise HTTPException(400)
    existing = await db.execute(
        select(PreferredWorker).where(
            PreferredWorker.client_org_id == user.client_org_id,
            PreferredWorker.worker_id == worker_profile_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"ok": True}
    db.add(PreferredWorker(client_org_id=user.client_org_id, worker_id=worker_profile_id))
    return {"ok": True}


@router.delete("/preferred-workers/{worker_profile_id}")
async def remove_preferred(
    worker_profile_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    if not user.client_org_id:
        raise HTTPException(400)
    r = await db.execute(
        select(PreferredWorker).where(
            PreferredWorker.client_org_id == user.client_org_id,
            PreferredWorker.worker_id == worker_profile_id,
        )
    )
    row = r.scalar_one_or_none()
    if row:
        await db.delete(row)
    return {"ok": True}


@router.get("/job-orders/{job_id}/live-attendance")
async def live_attendance(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    job = await db.get(JobOrder, job_id)
    if not job or job.client_org_id != user.client_org_id:
        raise HTTPException(404)
    r = await db.execute(select(Shift).where(Shift.job_order_id == job_id))
    shifts = r.scalars().all()
    now = datetime.now(timezone.utc)
    active = [s for s in shifts if s.starts_at <= now <= s.ends_at]
    if not active:
        active = shifts[-1:] if shifts else []
    out = []
    for s in active:
        r2 = await db.execute(
            select(ShiftAssignment)
            .options(selectinload(ShiftAssignment.shift))
            .where(
                ShiftAssignment.shift_id == s.id,
                ShiftAssignment.status == AssignmentStatus.confirmed,
            )
        )
        for a in r2.scalars().all():
            row = await _live_worker_row(db, s, a, now)
            out.append({k: v for k, v in row.items() if k != "shift_id"})
    return {"shifts": [s.id for s in active], "workers": out}


@router.get("/job-orders/{job_id}/shift-attendance")
async def shift_attendance(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    job = await db.get(JobOrder, job_id)
    if not job or job.client_org_id != user.client_org_id:
        raise HTTPException(404)
    r = await db.execute(select(Shift).where(Shift.job_order_id == job_id))
    shifts = sorted(r.scalars().all(), key=lambda x: x.starts_at)
    now = datetime.now(timezone.utc)
    shift_blocks: list[dict] = []
    for s in shifts:
        r2 = await db.execute(
            select(ShiftAssignment)
            .where(
                ShiftAssignment.shift_id == s.id,
                ShiftAssignment.status == AssignmentStatus.confirmed,
            )
        )
        workers: list[dict] = []
        for a in r2.scalars().all():
            workers.append(await _live_worker_row(db, s, a, now))
        shift_blocks.append(
            {
                "shift_id": s.id,
                "starts_at": s.starts_at.isoformat(),
                "ends_at": s.ends_at.isoformat(),
                "workers": workers,
            }
        )
    return {"job_id": job_id, "shifts": shift_blocks}


@router.get("/job-orders/{job_id}/shifts/{shift_id}/attendance-qr")
async def attendance_qr_tokens(
    job_id: int,
    shift_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    job = await db.get(JobOrder, job_id)
    if not job or job.client_org_id != user.client_org_id:
        raise HTTPException(404)
    shift = await db.get(Shift, shift_id)
    if not shift or shift.job_order_id != job_id:
        raise HTTPException(404)
    return {
        "clock_in_token": create_attendance_qr_token(
            job_id=job_id,
            shift_id=shift_id,
            action="in",
            shift_ends_at=shift.ends_at,
        ),
        "clock_out_token": create_attendance_qr_token(
            job_id=job_id,
            shift_id=shift_id,
            action="out",
            shift_ends_at=shift.ends_at,
        ),
    }


class RatingIn(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: str | None = None


@router.post("/assignments/{assignment_id}/rate")
async def rate_worker(
    assignment_id: int,
    body: RatingIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    a = await db.get(ShiftAssignment, assignment_id)
    if not a:
        raise HTTPException(404)
    shift = await db.get(Shift, a.shift_id)
    job = await db.get(JobOrder, shift.job_order_id)
    if job.client_org_id != user.client_org_id:
        raise HTTPException(403)
    avg = await upsert_client_rating_for_assignment(
        db,
        shift_assignment_id=assignment_id,
        worker_id=a.worker_id,
        rated_by_user_id=user.id,
        stars=body.stars,
        comment=body.comment,
    )
    return {"ok": True, "new_avg": avg}
