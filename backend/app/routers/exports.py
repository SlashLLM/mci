from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import JobOrder, TimesheetEntry, User, UserRole
from app.services.payroll_export import (
    export_client_payroll_lines_csv,
    export_ta_verified_payroll_line_csv,
    export_ta_verified_payroll_lines_csv,
    export_ta_verified_payroll_lines_csv_for_ta,
)
from app.services.ta_client_contracts import list_contracted_org_ids_for_ta, ta_has_active_contract_with_org
from app.services.zoho_export import (
    export_job_orders_csv,
    export_job_orders_xlsx_bytes,
    export_shifts_schedule_csv,
    export_timesheets_csv,
    export_timesheets_xlsx_bytes,
)

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/zoho/job-orders.csv")
async def zoho_job_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    if user.role == UserRole.ta:
        org_ids = list(await list_contracted_org_ids_for_ta(db, user.id))
        if not org_ids:
            jobs = []
        else:
            r = await db.execute(select(JobOrder).where(JobOrder.client_org_id.in_(org_ids)))
            jobs = r.scalars().all()
    else:
        r = await db.execute(select(JobOrder))
        jobs = r.scalars().all()
    data = await export_job_orders_csv(db, jobs)
    return Response(content=data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=zoho_job_orders.csv"})


@router.get("/payroll/ta-verified-lines.csv")
async def payroll_ta_verified_lines(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    if user.role == UserRole.admin:
        data = await export_ta_verified_payroll_lines_csv(db)
    else:
        data = await export_ta_verified_payroll_lines_csv_for_ta(db, user.id)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=ta_verified_payroll_lines.csv"},
    )


@router.get("/payroll/ta-verified-lines/{timesheet_entry_id}.csv")
async def payroll_ta_verified_single_line(
    timesheet_entry_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    if user.role == UserRole.ta:
        t = await db.get(TimesheetEntry, timesheet_entry_id)
        if not t:
            raise HTTPException(404)
        job = await db.get(JobOrder, t.job_order_id)
        if not job or not await ta_has_active_contract_with_org(db, user.id, job.client_org_id):
            raise HTTPException(404)
    data = await export_ta_verified_payroll_line_csv(db, timesheet_entry_id)
    if data is None:
        raise HTTPException(404, detail="Timesheet line not found or not ready for payroll export")
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=ta_payroll_timesheet_{timesheet_entry_id}.csv",
        },
    )


@router.get("/payroll/client-lines.csv")
async def payroll_client_lines(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    if not user.client_org_id:
        raise HTTPException(400, detail="No client organization")
    data = await export_client_payroll_lines_csv(db, user.client_org_id)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=client_payroll_lines.csv"},
    )


@router.get("/zoho/timesheets.csv")
async def zoho_timesheets(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    org_ids = None
    if user.role == UserRole.ta:
        org_ids = list(await list_contracted_org_ids_for_ta(db, user.id))
    data = await export_timesheets_csv(db, org_ids)
    return Response(content=data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=zoho_timesheets.csv"})


@router.get("/zoho/shifts.csv")
async def zoho_shifts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    org_ids = None
    if user.role == UserRole.ta:
        org_ids = list(await list_contracted_org_ids_for_ta(db, user.id))
    data = await export_shifts_schedule_csv(db, org_ids)
    return Response(content=data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=zoho_shifts.csv"})


@router.get("/zoho/job-orders.xlsx")
async def zoho_job_orders_xlsx(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    if user.role == UserRole.ta:
        org_ids = list(await list_contracted_org_ids_for_ta(db, user.id))
        if not org_ids:
            jobs = []
        else:
            r = await db.execute(select(JobOrder).where(JobOrder.client_org_id.in_(org_ids)))
            jobs = r.scalars().all()
    else:
        r = await db.execute(select(JobOrder))
        jobs = r.scalars().all()
    data = export_job_orders_xlsx_bytes(jobs)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=zoho_job_orders.xlsx"},
    )


@router.get("/zoho/timesheets.xlsx")
async def zoho_timesheets_xlsx(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    org_ids = None
    if user.role == UserRole.ta:
        org_ids = list(await list_contracted_org_ids_for_ta(db, user.id))
    data = await export_timesheets_xlsx_bytes(db, org_ids)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=zoho_timesheets.xlsx"},
    )
