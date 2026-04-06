"""CSV export of TA-verified timesheet lines for payroll (read-only)."""

import csv
import io

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobOrder, TimesheetEntry, TimesheetStatus, WorkerProfile
from app.services.crypto_pii import decrypt_value
from app.services.ta_client_contracts import list_contracted_org_ids_for_ta


def _worker_bank_fields(wp: WorkerProfile) -> tuple[str, str]:
    account = decrypt_value(wp.bank_encrypted) if wp.bank_encrypted else ""
    name = (wp.bank_name or "").strip()
    return account, name


async def export_ta_verified_payroll_line_csv(db: AsyncSession, timesheet_entry_id: int) -> str | None:
    """One payroll CSV row for a single TA-verified (or payment-released) entry; None if not found or wrong status."""
    r = await db.execute(
        select(TimesheetEntry, WorkerProfile, JobOrder)
        .join(WorkerProfile, TimesheetEntry.worker_id == WorkerProfile.id)
        .join(JobOrder, TimesheetEntry.job_order_id == JobOrder.id)
        .where(
            TimesheetEntry.id == timesheet_entry_id,
            TimesheetEntry.status.in_((TimesheetStatus.ta_verified, TimesheetStatus.payment_released)),
        )
    )
    row = r.one_or_none()
    if not row:
        return None
    t, wp, job = row
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "timesheet_entry_id",
            "worker_name",
            "job_order_id",
            "job_title",
            "hours_worked",
            "amount_sgd",
            "bank_account",
            "bank_name",
        ]
    )
    bank, bank_name = _worker_bank_fields(wp)
    w.writerow(
        [
            t.id,
            wp.full_name or "",
            job.id,
            job.title,
            f"{t.actual_hours:.2f}",
            f"{t.gross_pay:.2f}",
            bank,
            bank_name,
        ]
    )
    return buf.getvalue()


async def export_client_payroll_lines_csv(db: AsyncSession, client_org_id: int) -> str:
    """Payroll lines for self-payroll clients after client_payroll_released (includes bank details for payout)."""
    r = await db.execute(
        select(TimesheetEntry, WorkerProfile, JobOrder)
        .join(WorkerProfile, TimesheetEntry.worker_id == WorkerProfile.id)
        .join(JobOrder, TimesheetEntry.job_order_id == JobOrder.id)
        .where(
            TimesheetEntry.status == TimesheetStatus.client_payroll_released,
            JobOrder.client_org_id == client_org_id,
        )
        .order_by(TimesheetEntry.id)
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "timesheet_entry_id",
            "worker_name",
            "job_order_id",
            "job_title",
            "hours_worked",
            "amount_sgd",
            "bank_account",
            "bank_name",
        ]
    )
    for t, wp, job in r.all():
        bank, bank_name = _worker_bank_fields(wp)
        w.writerow(
            [
                t.id,
                wp.full_name or "",
                job.id,
                job.title,
                f"{t.actual_hours:.2f}",
                f"{t.gross_pay:.2f}",
                bank,
                bank_name,
            ]
        )
    return buf.getvalue()


async def export_ta_verified_payroll_lines_csv(db: AsyncSession) -> str:
    r = await db.execute(
        select(TimesheetEntry, WorkerProfile, JobOrder)
        .join(WorkerProfile, TimesheetEntry.worker_id == WorkerProfile.id)
        .join(JobOrder, TimesheetEntry.job_order_id == JobOrder.id)
        .where(TimesheetEntry.status == TimesheetStatus.ta_verified)
        .order_by(TimesheetEntry.id)
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "timesheet_entry_id",
            "worker_name",
            "job_order_id",
            "job_title",
            "hours_worked",
            "amount_sgd",
            "bank_account",
            "bank_name",
        ]
    )
    for t, wp, job in r.all():
        bank, bank_name = _worker_bank_fields(wp)
        w.writerow(
            [
                t.id,
                wp.full_name or "",
                job.id,
                job.title,
                f"{t.actual_hours:.2f}",
                f"{t.gross_pay:.2f}",
                bank,
                bank_name,
            ]
        )
    return buf.getvalue()


async def export_ta_verified_payroll_lines_csv_for_ta(db: AsyncSession, ta_user_id: int) -> str:
    org_ids = list(await list_contracted_org_ids_for_ta(db, ta_user_id))
    if not org_ids:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "timesheet_entry_id",
                "worker_name",
                "job_order_id",
                "job_title",
                "hours_worked",
                "amount_sgd",
                "bank_account",
                "bank_name",
            ]
        )
        return buf.getvalue()
    r = await db.execute(
        select(TimesheetEntry, WorkerProfile, JobOrder)
        .join(WorkerProfile, TimesheetEntry.worker_id == WorkerProfile.id)
        .join(JobOrder, TimesheetEntry.job_order_id == JobOrder.id)
        .where(
            TimesheetEntry.status == TimesheetStatus.ta_verified,
            JobOrder.client_org_id.in_(org_ids),
        )
        .order_by(TimesheetEntry.id)
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "timesheet_entry_id",
            "worker_name",
            "job_order_id",
            "job_title",
            "hours_worked",
            "amount_sgd",
            "bank_account",
            "bank_name",
        ]
    )
    for t, wp, job in r.all():
        bank, bank_name = _worker_bank_fields(wp)
        w.writerow(
            [
                t.id,
                wp.full_name or "",
                job.id,
                job.title,
                f"{t.actual_hours:.2f}",
                f"{t.gross_pay:.2f}",
                bank,
                bank_name,
            ]
        )
    return buf.getvalue()
