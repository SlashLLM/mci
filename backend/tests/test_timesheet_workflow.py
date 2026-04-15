"""Timesheet payroll export and client rating upsert (sqlite)."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import (
    AssignmentStatus,
    AttendanceRecord,
    AttendanceStatus,
    ClientOrganization,
    JobOrder,
    JobOrderStatus,
    PayModel,
    Shift,
    ShiftAssignment,
    TimesheetEntry,
    TimesheetStatus,
    User,
    UserRole,
    WorkerProfile,
    WorkerStatus,
    WorkerTier,
)
from app.services.payroll_export import export_ta_verified_payroll_line_csv, export_ta_verified_payroll_lines_csv
from app.services.timesheet_flow import get_clock_out_pay_summary, mark_assignment_completed_if_clocked
from app.services.worker_ratings import upsert_client_rating_for_assignment
from sqlalchemy import select


@pytest_asyncio.fixture
async def sqlite_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_export_ta_verified_payroll_csv_includes_verified_only(sqlite_session: AsyncSession):
    now = datetime.now(timezone.utc)
    org = ClientOrganization(name="Org")
    sqlite_session.add(org)
    await sqlite_session.flush()
    u_client = User(phone="+19990000001", role=UserRole.client, locale="en", client_org_id=org.id)
    u_worker = User(phone="+19990000002", role=UserRole.worker, locale="en")
    sqlite_session.add_all([u_client, u_worker])
    await sqlite_session.flush()
    wp = WorkerProfile(
        user_id=u_worker.id,
        full_name="Jane Worker",
        bank_encrypted="111222333",
        bank_name="OCBC",
        languages=[],
        job_type_preferences=[],
        skills=[],
        certifications=[],
        availability={},
        tier=WorkerTier.standard,
        status=WorkerStatus.active,
    )
    sqlite_session.add(wp)
    await sqlite_session.flush()
    job = JobOrder(
        client_org_id=org.id,
        created_by_user_id=u_client.id,
        title="Night shift",
        job_type="Warehouse Worker",
        location_address="SG",
        location_lat=1.0,
        location_lng=103.0,
        workers_required_total=1,
        pay_model=PayModel.hourly,
        hourly_rate=20.0,
        status=JobOrderStatus.open,
    )
    sqlite_session.add(job)
    await sqlite_session.flush()
    shift = Shift(job_order_id=job.id, starts_at=now, ends_at=now + timedelta(hours=8), workers_required=1)
    sqlite_session.add(shift)
    await sqlite_session.flush()
    sa = ShiftAssignment(shift_id=shift.id, worker_id=wp.id, status=AssignmentStatus.confirmed)
    sqlite_session.add(sa)
    await sqlite_session.flush()

    verified = TimesheetEntry(
        job_order_id=job.id,
        shift_id=shift.id,
        worker_id=wp.id,
        shift_assignment_id=sa.id,
        scheduled_hours=8.0,
        actual_hours=7.5,
        overtime_hours=0.0,
        hourly_rate_snapshot=20.0,
        gross_pay=150.0,
        status=TimesheetStatus.ta_verified,
    )
    sqlite_session.add(verified)
    await sqlite_session.commit()

    csv_text = await export_ta_verified_payroll_lines_csv(sqlite_session)
    lines = csv_text.strip().splitlines()
    assert len(lines) == 2
    assert "timesheet_entry_id" in lines[0]
    assert "bank_account" in lines[0]
    assert "bank_name" in lines[0]
    assert "Jane Worker" in lines[1]
    assert "Night shift" in lines[1]
    assert "150.00" in lines[1] or "150" in lines[1]
    assert "111222333" in lines[1]
    assert "OCBC" in lines[1]

    single = await export_ta_verified_payroll_line_csv(sqlite_session, verified.id)
    assert single is not None
    single_lines = single.strip().splitlines()
    assert len(single_lines) == 2
    assert single_lines[0] == lines[0]
    assert "Jane Worker" in single_lines[1]

    assert await export_ta_verified_payroll_line_csv(sqlite_session, 99999) is None


@pytest.mark.asyncio
async def test_upsert_client_rating_does_not_change_points(sqlite_session: AsyncSession):
    org = ClientOrganization(name="O")
    sqlite_session.add(org)
    await sqlite_session.flush()
    u_client = User(phone="+18880000001", role=UserRole.client, locale="en", client_org_id=org.id)
    u_worker = User(phone="+18880000002", role=UserRole.worker, locale="en")
    sqlite_session.add_all([u_client, u_worker])
    await sqlite_session.flush()
    wp = WorkerProfile(
        user_id=u_worker.id,
        full_name="W",
        languages=[],
        job_type_preferences=[],
        skills=[],
        certifications=[],
        availability={},
        tier=WorkerTier.standard,
        status=WorkerStatus.active,
        points=0,
    )
    sqlite_session.add(wp)
    await sqlite_session.flush()
    now = datetime.now(timezone.utc)
    job = JobOrder(
        client_org_id=org.id,
        created_by_user_id=u_client.id,
        title="J",
        job_type="Warehouse Worker",
        location_address="SG",
        location_lat=1.0,
        location_lng=103.0,
        workers_required_total=1,
        pay_model=PayModel.hourly,
        hourly_rate=10.0,
        status=JobOrderStatus.open,
    )
    sqlite_session.add(job)
    await sqlite_session.flush()
    shift = Shift(job_order_id=job.id, starts_at=now, ends_at=now + timedelta(hours=4), workers_required=1)
    sqlite_session.add(shift)
    await sqlite_session.flush()
    sa = ShiftAssignment(shift_id=shift.id, worker_id=wp.id, status=AssignmentStatus.confirmed)
    sqlite_session.add(sa)
    await sqlite_session.flush()

    await upsert_client_rating_for_assignment(
        sqlite_session,
        shift_assignment_id=sa.id,
        worker_id=wp.id,
        rated_by_user_id=u_client.id,
        stars=4,
    )
    await sqlite_session.refresh(wp)
    assert wp.points == 0
    assert wp.rating_avg == 4.0

    await upsert_client_rating_for_assignment(
        sqlite_session,
        shift_assignment_id=sa.id,
        worker_id=wp.id,
        rated_by_user_id=u_client.id,
        stars=5,
    )
    await sqlite_session.refresh(wp)
    assert wp.points == 0
    assert wp.rating_avg == 5.0


@pytest.mark.asyncio
async def test_completed_shift_awards_points_once(sqlite_session: AsyncSession):
    now = datetime.now(timezone.utc)
    org = ClientOrganization(name="Ops")
    sqlite_session.add(org)
    await sqlite_session.flush()
    u_client = User(phone="+18880000011", role=UserRole.client, locale="en", client_org_id=org.id)
    u_worker = User(phone="+18880000012", role=UserRole.worker, locale="en")
    sqlite_session.add_all([u_client, u_worker])
    await sqlite_session.flush()
    wp = WorkerProfile(
        user_id=u_worker.id,
        full_name="Worker",
        languages=[],
        job_type_preferences=[],
        skills=[],
        certifications=[],
        availability={},
        tier=WorkerTier.standard,
        status=WorkerStatus.active,
        points=0,
    )
    sqlite_session.add(wp)
    await sqlite_session.flush()
    job = JobOrder(
        client_org_id=org.id,
        created_by_user_id=u_client.id,
        title="Day shift",
        job_type="Warehouse Worker",
        location_address="SG",
        location_lat=1.0,
        location_lng=103.0,
        workers_required_total=1,
        pay_model=PayModel.hourly,
        hourly_rate=12.0,
        status=JobOrderStatus.open,
    )
    sqlite_session.add(job)
    await sqlite_session.flush()
    shift = Shift(job_order_id=job.id, starts_at=now - timedelta(hours=8), ends_at=now - timedelta(hours=1), workers_required=1)
    sqlite_session.add(shift)
    await sqlite_session.flush()
    sa = ShiftAssignment(shift_id=shift.id, worker_id=wp.id, status=AssignmentStatus.confirmed)
    sqlite_session.add(sa)
    await sqlite_session.flush()
    attendance = AttendanceRecord(
        shift_assignment_id=sa.id,
        status=AttendanceStatus.present,
        clock_in_time=now - timedelta(hours=8),
        clock_out_time=now - timedelta(hours=1),
        total_hours=7.0,
    )
    sqlite_session.add(attendance)
    await sqlite_session.flush()

    await mark_assignment_completed_if_clocked(sqlite_session, sa, attendance)
    await sqlite_session.refresh(wp)
    assert wp.points == 10


@pytest.mark.asyncio
async def test_hourly_short_shift_timesheet_uses_scheduled_pay(sqlite_session: AsyncSession):
    now = datetime.now(timezone.utc)
    org = ClientOrganization(name="Ops2")
    sqlite_session.add(org)
    await sqlite_session.flush()
    u_client = User(phone="+18880000021", role=UserRole.client, locale="en", client_org_id=org.id)
    u_worker = User(phone="+18880000022", role=UserRole.worker, locale="en")
    sqlite_session.add_all([u_client, u_worker])
    await sqlite_session.flush()
    wp = WorkerProfile(
        user_id=u_worker.id,
        full_name="Worker2",
        languages=[],
        job_type_preferences=[],
        skills=[],
        certifications=[],
        availability={},
        tier=WorkerTier.standard,
        status=WorkerStatus.active,
        points=0,
    )
    sqlite_session.add(wp)
    await sqlite_session.flush()
    job = JobOrder(
        client_org_id=org.id,
        created_by_user_id=u_client.id,
        title="Short shift",
        job_type="Warehouse Worker",
        location_address="SG",
        location_lat=1.0,
        location_lng=103.0,
        workers_required_total=1,
        pay_model=PayModel.hourly,
        hourly_rate=12.0,
        status=JobOrderStatus.open,
    )
    sqlite_session.add(job)
    await sqlite_session.flush()
    shift = Shift(
        job_order_id=job.id,
        starts_at=now - timedelta(hours=8),
        ends_at=now,
        workers_required=1,
    )
    sqlite_session.add(shift)
    await sqlite_session.flush()
    sa = ShiftAssignment(shift_id=shift.id, worker_id=wp.id, status=AssignmentStatus.confirmed)
    sqlite_session.add(sa)
    await sqlite_session.flush()
    attendance = AttendanceRecord(
        shift_assignment_id=sa.id,
        status=AttendanceStatus.present,
        clock_in_time=now - timedelta(hours=6),
        clock_out_time=now,
        total_hours=6.0,
    )
    sqlite_session.add(attendance)
    await sqlite_session.flush()

    summary = await get_clock_out_pay_summary(sqlite_session, sa, attendance, shift, job)
    assert summary["gross_pay"] == 96.0
    assert summary["actual_hours"] == 8.0
    assert summary["timesheet_created"] is False

    await mark_assignment_completed_if_clocked(sqlite_session, sa, attendance)
    await sqlite_session.flush()

    r = await sqlite_session.execute(select(TimesheetEntry).where(TimesheetEntry.shift_assignment_id == sa.id))
    ts = r.scalar_one()
    assert ts.scheduled_hours == 8.0
    assert ts.actual_hours == 8.0
    assert ts.gross_pay == 96.0
    assert wp.tier == WorkerTier.standard

    await mark_assignment_completed_if_clocked(sqlite_session, sa, attendance)
    await sqlite_session.refresh(wp)
    assert wp.points == 10
