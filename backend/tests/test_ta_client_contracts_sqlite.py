"""TA–client contract helpers and job access (SQLite)."""

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import (
    ClientOrganization,
    JobOrder,
    JobOrderStatus,
    PayModel,
    TaClientContract,
    TaClientContractStatus,
    User,
    UserRole,
)
from app.services.ta_client_contracts import (
    list_contracted_org_ids_for_ta,
    ta_has_active_contract_with_org,
)


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
async def test_ta_access_requires_active_contract(sqlite_session: AsyncSession):
    org = ClientOrganization(name="O1")
    sqlite_session.add(org)
    await sqlite_session.flush()
    ta = User(phone="+1001", role=UserRole.ta)
    sqlite_session.add(ta)
    await sqlite_session.flush()
    assert not await ta_has_active_contract_with_org(sqlite_session, ta.id, org.id)
    c = TaClientContract(
        client_org_id=org.id,
        ta_user_id=ta.id,
        status=TaClientContractStatus.active,
        requested_by_user_id=ta.id,
    )
    sqlite_session.add(c)
    await sqlite_session.flush()
    assert await ta_has_active_contract_with_org(sqlite_session, ta.id, org.id)
    ids = await list_contracted_org_ids_for_ta(sqlite_session, ta.id)
    assert org.id in ids


@pytest.mark.asyncio
async def test_pending_contract_not_in_contracted_org_ids(sqlite_session: AsyncSession):
    org = ClientOrganization(name="O2")
    sqlite_session.add(org)
    await sqlite_session.flush()
    ta = User(phone="+1002", role=UserRole.ta)
    sqlite_session.add(ta)
    await sqlite_session.flush()
    sqlite_session.add(
        TaClientContract(
            client_org_id=org.id,
            ta_user_id=ta.id,
            status=TaClientContractStatus.pending_ta,
            requested_by_user_id=ta.id,
        )
    )
    await sqlite_session.flush()
    ids = await list_contracted_org_ids_for_ta(sqlite_session, ta.id)
    assert org.id not in ids


@pytest.mark.asyncio
async def test_client_payroll_export_empty_without_released_status(sqlite_session: AsyncSession):
    from app.models import Shift, ShiftAssignment, AssignmentStatus, TimesheetEntry, TimesheetStatus, WorkerProfile
    from app.services.payroll_export import export_client_payroll_lines_csv

    org = ClientOrganization(name="O3")
    sqlite_session.add(org)
    await sqlite_session.flush()
    u_client = User(phone="+1003", role=UserRole.client, client_org_id=org.id)
    u_worker = User(phone="+1004", role=UserRole.worker)
    sqlite_session.add_all([u_client, u_worker])
    await sqlite_session.flush()
    wp = WorkerProfile(user_id=u_worker.id, full_name="W")
    sqlite_session.add(wp)
    await sqlite_session.flush()
    job = JobOrder(
        client_org_id=org.id,
        created_by_user_id=u_client.id,
        title="J",
        job_type="Warehouse Worker",
        location_address="x",
        location_lat=1.0,
        location_lng=103.0,
        pay_model=PayModel.hourly,
        status=JobOrderStatus.completed,
    )
    sqlite_session.add(job)
    await sqlite_session.flush()
    sh = Shift(job_order_id=job.id, starts_at=datetime.now(timezone.utc), ends_at=datetime.now(timezone.utc))
    sqlite_session.add(sh)
    await sqlite_session.flush()
    sa = ShiftAssignment(shift_id=sh.id, worker_id=wp.id, status=AssignmentStatus.completed)
    sqlite_session.add(sa)
    await sqlite_session.flush()
    te = TimesheetEntry(
        job_order_id=job.id,
        shift_id=sh.id,
        worker_id=wp.id,
        shift_assignment_id=sa.id,
        gross_pay=10.0,
        status=TimesheetStatus.employer_endorsed,
    )
    sqlite_session.add(te)
    await sqlite_session.commit()
    csv_text = await export_client_payroll_lines_csv(sqlite_session, org.id)
    lines = csv_text.strip().splitlines()
    assert len(lines) == 1
    assert "timesheet_entry_id" in lines[0]
    assert "bank_account" in lines[0]
    assert "bank_name" in lines[0]


@pytest.mark.asyncio
async def test_client_payroll_export_includes_bank_when_released(sqlite_session: AsyncSession):
    from app.models import Shift, ShiftAssignment, AssignmentStatus, TimesheetEntry, TimesheetStatus, WorkerProfile
    from app.services.payroll_export import export_client_payroll_lines_csv

    org = ClientOrganization(name="O4")
    sqlite_session.add(org)
    await sqlite_session.flush()
    u_client = User(phone="+1005", role=UserRole.client, client_org_id=org.id)
    u_worker = User(phone="+1006", role=UserRole.worker)
    sqlite_session.add_all([u_client, u_worker])
    await sqlite_session.flush()
    wp = WorkerProfile(
        user_id=u_worker.id,
        full_name="Pay Worker",
        bank_encrypted="999888777",
        bank_name="DBS",
    )
    sqlite_session.add(wp)
    await sqlite_session.flush()
    job = JobOrder(
        client_org_id=org.id,
        created_by_user_id=u_client.id,
        title="Pay job",
        job_type="Warehouse Worker",
        location_address="x",
        location_lat=1.0,
        location_lng=103.0,
        pay_model=PayModel.hourly,
        status=JobOrderStatus.completed,
    )
    sqlite_session.add(job)
    await sqlite_session.flush()
    sh = Shift(job_order_id=job.id, starts_at=datetime.now(timezone.utc), ends_at=datetime.now(timezone.utc))
    sqlite_session.add(sh)
    await sqlite_session.flush()
    sa = ShiftAssignment(shift_id=sh.id, worker_id=wp.id, status=AssignmentStatus.completed)
    sqlite_session.add(sa)
    await sqlite_session.flush()
    te = TimesheetEntry(
        job_order_id=job.id,
        shift_id=sh.id,
        worker_id=wp.id,
        shift_assignment_id=sa.id,
        actual_hours=8.0,
        gross_pay=120.0,
        status=TimesheetStatus.client_payroll_released,
    )
    sqlite_session.add(te)
    await sqlite_session.commit()
    csv_text = await export_client_payroll_lines_csv(sqlite_session, org.id)
    lines = csv_text.strip().splitlines()
    assert len(lines) == 2
    assert "bank_account" in lines[0] and "bank_name" in lines[0]
    assert "999888777" in lines[1] and "DBS" in lines[1] and "Pay Worker" in lines[1]
