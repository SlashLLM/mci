"""ZOHO-compatible CSV / Excel columns (MVP template — adjust to MCI import file)."""

import csv
import io
from io import BytesIO
from typing import Iterable, Optional, Sequence

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobOrder, Shift, TimesheetEntry, WorkerProfile


async def export_job_orders_csv(db: AsyncSession, jobs: Iterable[JobOrder]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "Deal_Name",
            "Job_Type",
            "Client_Org_Id",
            "Location",
            "Lat",
            "Lng",
            "Status",
            "Workers_Required_Total",
            "Pay_Model",
            "Hourly_Rate",
            "Per_Shift_Rate",
        ]
    )
    for j in jobs:
        w.writerow(
            [
                j.title,
                j.job_type,
                j.client_org_id,
                j.location_address,
                j.location_lat,
                j.location_lng,
                j.status.value,
                j.workers_required_total,
                j.pay_model.value,
                j.hourly_rate or "",
                j.per_shift_rate or "",
            ]
        )
    return buf.getvalue()


async def export_timesheets_csv(
    db: AsyncSession, client_org_ids: Optional[Sequence[int]] = None
) -> str:
    if client_org_ids is not None and len(list(client_org_ids)) == 0:
        rows = []
    elif client_org_ids is not None:
        stmt = (
            select(TimesheetEntry)
            .join(JobOrder, TimesheetEntry.job_order_id == JobOrder.id)
            .where(JobOrder.client_org_id.in_(list(client_org_ids)))
        )
        r = await db.execute(stmt)
        rows = r.scalars().all()
    else:
        r = await db.execute(select(TimesheetEntry))
        rows = r.scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "Timesheet_Id",
            "Job_Order_Id",
            "Shift_Id",
            "Worker_Id",
            "Worker_Name",
            "Scheduled_Hrs",
            "Actual_Hrs",
            "OT_Hrs",
            "Gross_Pay",
            "Status",
        ]
    )
    for t in rows:
        wp = await db.get(WorkerProfile, t.worker_id)
        w.writerow(
            [
                t.id,
                t.job_order_id,
                t.shift_id,
                t.worker_id,
                (wp.full_name if wp else ""),
                t.scheduled_hours,
                t.actual_hours,
                t.overtime_hours,
                t.gross_pay,
                t.status.value,
            ]
        )
    return buf.getvalue()


async def export_shifts_schedule_csv(
    db: AsyncSession, client_org_ids: Optional[Sequence[int]] = None
) -> str:
    if client_org_ids is not None and len(list(client_org_ids)) == 0:
        shifts = []
    elif client_org_ids is not None:
        stmt = (
            select(Shift)
            .join(JobOrder, Shift.job_order_id == JobOrder.id)
            .where(JobOrder.client_org_id.in_(list(client_org_ids)))
        )
        r = await db.execute(stmt)
        shifts = r.scalars().all()
    else:
        r = await db.execute(select(Shift))
        shifts = r.scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Shift_Id", "Job_Order_Id", "Starts_At", "Ends_At", "Workers_Required"])
    for s in shifts:
        w.writerow([s.id, s.job_order_id, s.starts_at.isoformat(), s.ends_at.isoformat(), s.workers_required])
    return buf.getvalue()


def export_job_orders_xlsx_bytes(jobs: Iterable[JobOrder]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "JobOrders"
    headers = [
        "Deal_Name",
        "Job_Type",
        "Client_Org_Id",
        "Location",
        "Lat",
        "Lng",
        "Status",
        "Workers_Required_Total",
        "Pay_Model",
        "Hourly_Rate",
        "Per_Shift_Rate",
    ]
    ws.append(headers)
    for j in jobs:
        ws.append(
            [
                j.title,
                j.job_type,
                j.client_org_id,
                j.location_address,
                j.location_lat,
                j.location_lng,
                j.status.value,
                j.workers_required_total,
                j.pay_model.value,
                j.hourly_rate or "",
                j.per_shift_rate or "",
            ]
        )
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def export_timesheets_xlsx_bytes(
    db: AsyncSession, client_org_ids: Optional[Sequence[int]] = None
) -> bytes:
    if client_org_ids is not None and len(list(client_org_ids)) == 0:
        rows = []
    elif client_org_ids is not None:
        stmt = (
            select(TimesheetEntry)
            .join(JobOrder, TimesheetEntry.job_order_id == JobOrder.id)
            .where(JobOrder.client_org_id.in_(list(client_org_ids)))
        )
        r = await db.execute(stmt)
        rows = r.scalars().all()
    else:
        r = await db.execute(select(TimesheetEntry))
        rows = r.scalars().all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Timesheets"
    ws.append(
        [
            "Timesheet_Id",
            "Job_Order_Id",
            "Shift_Id",
            "Worker_Id",
            "Worker_Name",
            "Scheduled_Hrs",
            "Actual_Hrs",
            "OT_Hrs",
            "Gross_Pay",
            "Status",
        ]
    )
    for t in rows:
        wp = await db.get(WorkerProfile, t.worker_id)
        ws.append(
            [
                t.id,
                t.job_order_id,
                t.shift_id,
                t.worker_id,
                (wp.full_name if wp else ""),
                t.scheduled_hours,
                t.actual_hours,
                t.overtime_hours,
                t.gross_pay,
                t.status.value,
            ]
        )
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
