from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import JobOrder, User, UserRole
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
    r = await db.execute(select(JobOrder))
    jobs = r.scalars().all()
    data = await export_job_orders_csv(db, jobs)
    return Response(content=data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=zoho_job_orders.csv"})


@router.get("/zoho/timesheets.csv")
async def zoho_timesheets(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    data = await export_timesheets_csv(db)
    return Response(content=data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=zoho_timesheets.csv"})


@router.get("/zoho/shifts.csv")
async def zoho_shifts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    data = await export_shifts_schedule_csv(db)
    return Response(content=data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=zoho_shifts.csv"})


@router.get("/zoho/job-orders.xlsx")
async def zoho_job_orders_xlsx(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
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
    data = await export_timesheets_xlsx_bytes(db)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=zoho_timesheets.xlsx"},
    )
