from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import (
    AssignmentStatus,
    ClientOrganization,
    JobOrder,
    Shift,
    ShiftAssignment,
    User,
    UserRole,
    WorkerProfile,
    WorkerReportStatus,
    WorkerShiftReport,
)
from app.services.notifications import notify_user
from app.services.ta_client_contracts import get_active_contract_for_org

router = APIRouter(prefix="/worker-reports", tags=["worker-reports"])


class WorkerReportCreateIn(BaseModel):
    shift_assignment_id: int
    reason: str = Field(min_length=1, max_length=1500)


class WorkerReportStatusUpdateIn(BaseModel):
    status: WorkerReportStatus


@router.post("")
async def create_worker_report(
    body: WorkerReportCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.worker))],
):
    result = await db.execute(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    worker_profile = result.scalar_one_or_none()
    if not worker_profile:
        raise HTTPException(status_code=404, detail="Worker profile not found")

    assignment = await db.get(ShiftAssignment, body.shift_assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.worker_id != worker_profile.id:
        raise HTTPException(status_code=403, detail="Assignment does not belong to current worker")
    if assignment.status != AssignmentStatus.confirmed:
        raise HTTPException(status_code=403, detail="Only confirmed assignments can be reported")

    dup = await db.execute(
        select(WorkerShiftReport).where(
            WorkerShiftReport.shift_assignment_id == assignment.id,
            WorkerShiftReport.worker_user_id == user.id,
        )
    )
    existing = dup.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Report already submitted for this assignment")

    report = WorkerShiftReport(
        shift_assignment_id=assignment.id,
        worker_user_id=user.id,
        reason=body.reason.strip(),
        status=WorkerReportStatus.open,
    )
    db.add(report)
    await db.flush()
    return {"ok": True, "report_id": report.id, "status": report.status.value}


@router.get("/admin")
async def list_reports_for_admin(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.admin))],
    status_filter: WorkerReportStatus | None = None,
):
    stmt = select(WorkerShiftReport).order_by(WorkerShiftReport.id.desc())
    if status_filter is not None:
        stmt = stmt.where(WorkerShiftReport.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()

    out: list[dict] = []
    for report in rows:
        assignment = await db.get(ShiftAssignment, report.shift_assignment_id)
        if not assignment:
            continue
        shift = await db.get(Shift, assignment.shift_id)
        if not shift:
            continue
        job = await db.get(JobOrder, shift.job_order_id)
        if not job:
            continue

        worker_profile = await db.get(WorkerProfile, assignment.worker_id)
        worker_user = await db.get(User, report.worker_user_id)
        client_org = await db.get(ClientOrganization, job.client_org_id)
        contract = await get_active_contract_for_org(db, job.client_org_id)
        ta_user = await db.get(User, contract.ta_user_id) if contract else None

        worker_name = ""
        if worker_profile and worker_profile.full_name:
            worker_name = worker_profile.full_name.strip()
        if not worker_name and worker_user and worker_user.display_name:
            worker_name = worker_user.display_name.strip()

        out.append(
            {
                "id": report.id,
                "status": report.status.value,
                "reason": report.reason,
                "created_at": report.created_at.isoformat() if isinstance(report.created_at, datetime) else None,
                "updated_at": report.updated_at.isoformat() if isinstance(report.updated_at, datetime) else None,
                "shift_assignment_id": report.shift_assignment_id,
                "job_order_id": job.id,
                "job_order_name": job.title,
                "shift_id": shift.id,
                "shift_starts_at": shift.starts_at.isoformat() if isinstance(shift.starts_at, datetime) else None,
                "shift_ends_at": shift.ends_at.isoformat() if isinstance(shift.ends_at, datetime) else None,
                "worker_user_id": report.worker_user_id,
                "worker_name": worker_name or None,
                "worker_email": worker_user.email if worker_user else None,
                "client_org_id": client_org.id if client_org else None,
                "client_org_name": client_org.name if client_org else None,
                "contracted_ta_user_id": ta_user.id if ta_user else None,
                "contracted_ta_name": ((ta_user.display_name or "").strip() or ta_user.username) if ta_user else None,
            }
        )
    return out


@router.patch("/admin/{report_id}/status")
async def update_report_status(
    report_id: int,
    body: WorkerReportStatusUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_roles(UserRole.admin))],
):
    report = await db.get(WorkerShiftReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    previous_status = report.status
    report.status = body.status

    assignment = await db.get(ShiftAssignment, report.shift_assignment_id)
    shift = await db.get(Shift, assignment.shift_id) if assignment else None
    job = await db.get(JobOrder, shift.job_order_id) if shift else None
    await notify_user(
        db,
        report.worker_user_id,
        title="Report status updated",
        body=f"Your report for {job.title if job else 'a shift'} changed from {previous_status.value} to {report.status.value}.",
        payload={
            "type": "worker_report_status_updated",
            "report_id": report.id,
            "from_status": previous_status.value,
            "to_status": report.status.value,
            "job_order_id": job.id if job else None,
            "shift_id": shift.id if shift else None,
            "shift_assignment_id": report.shift_assignment_id,
        },
    )
    await db.flush()
    return {"ok": True, "id": report.id, "status": report.status.value}
