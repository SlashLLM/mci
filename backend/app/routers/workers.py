import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_roles
from app.auth.file_tokens import create_file_access_token
from app.config import get_settings
from app.db.session import get_db
from app.models import Document, User, UserRole, WorkerProfile, WorkerStatus
from app.schemas.workers import OnboardingCompleteIn, WorkerProfileIn, WorkerProfileOut
from app.services.audit import log_audit
from app.services.crypto_pii import encrypt_value, mask_nric

router = APIRouter(prefix="/workers", tags=["workers"])

_ALLOWED_DOC_CT = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "application/pdf",
    }
)


def _weighted_completeness(wp: WorkerProfile, user: User, doc_types: set[str]) -> int:
    """Weights: Basic 20%, Preferences 20%, Bank 15%, Documents 35%, Optional 10%."""
    s = 0.0
    if wp.full_name and str(wp.full_name).strip():
        s += 5
    if wp.nric_encrypted or wp.nric_masked:
        s += 5
    if user.phone and str(user.phone).strip():
        s += 5
    if user.email and str(user.email).strip():
        s += 5

    if wp.languages:
        s += 5
    if wp.job_type_preferences:
        s += 5
    if wp.availability and isinstance(wp.availability, dict) and len(wp.availability) > 0:
        s += 5
    if wp.skills:
        s += 5

    if wp.bank_encrypted:
        s += 15

    if "nric_copy" in doc_types or "nric" in doc_types:
        s += 10
    if "work_pass" in doc_types or wp.work_pass_not_applicable:
        s += 8
    if "certification" in doc_types or "certifications" in doc_types:
        s += 8.5
    if "training_record" in doc_types or "training" in doc_types:
        s += 8.5

    if wp.certifications:
        s += 4
    if wp.bank_name and str(wp.bank_name).strip():
        s += 2
    if wp.location_lat is not None and wp.location_lng is not None:
        s += 4

    return int(min(100, round(s)))


async def _doc_types_for_worker(db: AsyncSession, worker_profile_id: int) -> set[str]:
    r = await db.execute(select(Document.doc_type).where(Document.worker_id == worker_profile_id))
    return {row[0] for row in r.all()}


async def _recalc_completeness(db: AsyncSession, wp: WorkerProfile, user: User) -> int:
    types = await _doc_types_for_worker(db, wp.id)
    pct = _weighted_completeness(wp, user, types)
    wp.profile_completeness_pct = pct
    return pct


def _profile_out(wp: WorkerProfile, user: User) -> WorkerProfileOut:
    return WorkerProfileOut(
        id=wp.id,
        full_name=wp.full_name,
        nric_masked=wp.nric_masked,
        phone=user.phone,
        email=user.email,
        languages=wp.languages or [],
        job_type_preferences=wp.job_type_preferences or [],
        skills=wp.skills or [],
        certifications=wp.certifications or [],
        availability=wp.availability or {},
        location_lat=wp.location_lat,
        location_lng=wp.location_lng,
        bank_name=wp.bank_name,
        work_pass_not_applicable=bool(wp.work_pass_not_applicable),
        rating_avg=wp.rating_avg,
        tier=wp.tier.value,
        status=wp.status.value,
        profile_completeness_pct=wp.profile_completeness_pct,
        pdpa_consent=bool(wp.pdpa_consent_at),
        terms_accepted=bool(wp.terms_accepted_at),
        onboarding_completed=bool(wp.onboarding_completed_at),
    )


@router.get("/me/profile", response_model=WorkerProfileOut)
async def get_my_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        raise HTTPException(status_code=404, detail="Profile not found")
    await db.refresh(user)
    return _profile_out(wp, user)


@router.put("/me/profile", response_model=WorkerProfileOut)
async def update_my_profile(
    body: WorkerProfileIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        wp = WorkerProfile(user_id=user.id)
        db.add(wp)
        await db.flush()

    old = {"full_name": wp.full_name}
    wp.full_name = body.full_name or wp.full_name
    if body.nric:
        wp.nric_encrypted = encrypt_value(body.nric)
        wp.nric_masked = mask_nric(body.nric)
    if body.bank_account:
        wp.bank_encrypted = encrypt_value(body.bank_account)
    if body.bank_name is not None:
        wp.bank_name = body.bank_name
    if body.email is not None:
        user.email = body.email.strip() or None
    if body.phone is not None:
        pn = body.phone.strip().replace(" ", "")
        if pn and pn != user.phone:
            clash = await db.execute(select(User).where(User.phone == pn, User.id != user.id))
            if clash.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="Phone already in use")
            user.phone = pn[:32]
    if body.work_pass_not_applicable is not None:
        wp.work_pass_not_applicable = body.work_pass_not_applicable
    wp.languages = body.languages
    wp.job_type_preferences = body.job_type_preferences
    wp.skills = body.skills
    wp.certifications = body.certifications
    wp.availability = body.availability
    if body.location_lat is not None:
        wp.location_lat = body.location_lat
    if body.location_lng is not None:
        wp.location_lng = body.location_lng
    await _recalc_completeness(db, wp, user)
    await db.flush()
    await log_audit(
        db,
        actor_user_id=user.id,
        action="worker_profile_update",
        entity_type="WorkerProfile",
        entity_id=str(wp.id),
        old_values=old,
        new_values={"full_name": wp.full_name},
    )
    await db.refresh(user)
    return _profile_out(wp, user)


@router.post("/me/pdpa-consent")
async def pdpa_consent(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    from datetime import datetime, timezone

    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        raise HTTPException(404)
    wp.pdpa_consent_at = datetime.now(timezone.utc)
    await _recalc_completeness(db, wp, user)
    await db.flush()
    return {"ok": True}


@router.post("/me/onboarding/complete")
async def onboarding_complete(
    body: OnboardingCompleteIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    from datetime import datetime, timezone

    if not body.terms_accepted:
        raise HTTPException(status_code=400, detail="Terms must be accepted")
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        raise HTTPException(404)
    now = datetime.now(timezone.utc)
    wp.terms_accepted_at = now
    wp.onboarding_completed_at = now
    if not wp.pdpa_consent_at:
        wp.pdpa_consent_at = now
    await _recalc_completeness(db, wp, user)
    await db.flush()
    return {"ok": True, "profile_completeness_pct": wp.profile_completeness_pct}


@router.post("/me/documents")
async def upload_document(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
    doc_type: str,
    file: UploadFile = File(...),
):
    settings = get_settings()
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        raise HTTPException(404)
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large")
    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct not in _ALLOWED_DOC_CT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ct}")

    ext = os.path.splitext(file.filename or "")[1] or ".bin"
    os.makedirs(settings.upload_dir, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.upload_dir, name)
    with open(path, "wb") as f:
        f.write(content)
    rel = f"uploads/{name}"
    db.add(Document(worker_id=wp.id, doc_type=doc_type, file_path=rel))
    out_path = rel

    await db.flush()
    await _recalc_completeness(db, wp, user)
    await db.flush()
    return {"ok": True, "path": out_path}


@router.get("/me/documents")
async def list_my_documents(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        return []
    r2 = await db.execute(select(Document).where(Document.worker_id == wp.id).order_by(Document.id.desc()))
    docs = r2.scalars().all()
    return [
        {
            "id": d.id,
            "doc_type": d.doc_type,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "storage_object_path": d.storage_object_path,
            "storage_bucket": d.storage_bucket,
        }
        for d in docs
    ]


@router.get("/me/documents/{doc_id}/signed-url")
async def document_signed_url(
    doc_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    r = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    wp = r.scalar_one_or_none()
    if not wp:
        raise HTTPException(404)
    doc = await db.get(Document, doc_id)
    if not doc or doc.worker_id != wp.id:
        raise HTTPException(404)
    if doc.storage_object_path and doc.storage_bucket:
        raise HTTPException(
            status_code=410,
            detail="Document was stored in external storage that is no longer available; please re-upload.",
        )
    if not doc.file_path:
        raise HTTPException(404, detail="No file backing")
    token = create_file_access_token(
        subject=doc.file_path,
        extra={"typ": "document", "doc_id": doc_id},
        expires_minutes=15,
    )
    return {"token": token, "url": f"/files/access?token={token}"}


@router.get("/directory", response_model=list[WorkerProfileOut])
async def list_workers_directory(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
    q: str | None = None,
    status_filter: str | None = None,
):
    stmt = select(WorkerProfile)
    if status_filter:
        try:
            stmt = stmt.where(WorkerProfile.status == WorkerStatus(status_filter))
        except ValueError:
            raise HTTPException(400, detail="Invalid status_filter")
    r = await db.execute(stmt)
    rows = r.scalars().all()
    out = []
    for wp in rows:
        if q and q.lower() not in (wp.full_name or "").lower():
            continue
        u = await db.get(User, wp.user_id)
        if not u:
            continue
        out.append(_profile_out(wp, u))
    return out


@router.patch("/{worker_id}/status")
async def update_worker_status(
    worker_id: int,
    new_status: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    wp = await db.get(WorkerProfile, worker_id)
    if not wp:
        raise HTTPException(404)
    try:
        wp.status = WorkerStatus(new_status)
    except ValueError:
        raise HTTPException(400, detail="Invalid status")
    await log_audit(
        db,
        actor_user_id=user.id,
        action="worker_status_change",
        entity_type="WorkerProfile",
        entity_id=str(worker_id),
        new_values={"status": new_status},
    )
    return {"ok": True}
