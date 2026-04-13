"""Declined offers must not list workers who later have a non-rejected assignment on the same shift."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
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
    WorkerProfile,
    WorkerStatus,
    WorkerTier,
)
from app.routers.job_orders import _accepted_and_declined_for_job


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
async def test_declined_hidden_when_worker_has_confirmed_assignment(sqlite_session: AsyncSession):
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
        full_name="Alice",
        languages=[],
        job_type_preferences=["Warehouse Worker"],
        skills=[],
        certifications=[],
        availability={},
        location_lat=1.0,
        location_lng=103.0,
        tier=WorkerTier.standard,
        status=WorkerStatus.active,
    )
    sqlite_session.add(wp)
    await sqlite_session.flush()
    job = JobOrder(
        client_org_id=org.id,
        created_by_user_id=u_client.id,
        title="Job",
        job_type="Warehouse Worker",
        location_address="A",
        location_lat=1.0,
        location_lng=103.0,
        workers_required_total=1,
        pay_model=PayModel.hourly,
        hourly_rate=15.0,
        status=JobOrderStatus.open,
    )
    sqlite_session.add(job)
    await sqlite_session.flush()
    shift = Shift(
        job_order_id=job.id,
        starts_at=now + timedelta(hours=1),
        ends_at=now + timedelta(hours=5),
        workers_required=1,
    )
    sqlite_session.add(shift)
    await sqlite_session.flush()
    sqlite_session.add(
        ShiftOffer(shift_id=shift.id, worker_id=wp.id, status=ShiftOfferStatus.declined, match_score=0.0)
    )
    sqlite_session.add(
        ShiftAssignment(
            shift_id=shift.id,
            worker_id=wp.id,
            status=AssignmentStatus.confirmed,
            match_score=1.0,
        )
    )
    await sqlite_session.commit()

    accepted, declined = await _accepted_and_declined_for_job(sqlite_session, job)
    assert len(accepted) == 1
    assert accepted[0].worker_profile_id == wp.id
    assert declined == []


@pytest.mark.asyncio
async def test_declined_shown_when_no_assignment(sqlite_session: AsyncSession):
    now = datetime.now(timezone.utc)
    org = ClientOrganization(name="Org")
    sqlite_session.add(org)
    await sqlite_session.flush()
    u_client = User(phone="+19990000003", role=UserRole.client, locale="en", client_org_id=org.id)
    u_worker = User(phone="+19990000004", role=UserRole.worker, locale="en")
    sqlite_session.add_all([u_client, u_worker])
    await sqlite_session.flush()
    wp = WorkerProfile(
        user_id=u_worker.id,
        full_name="Bob",
        languages=[],
        job_type_preferences=["Warehouse Worker"],
        skills=[],
        certifications=[],
        availability={},
        location_lat=1.0,
        location_lng=103.0,
        tier=WorkerTier.standard,
        status=WorkerStatus.active,
    )
    sqlite_session.add(wp)
    await sqlite_session.flush()
    job = JobOrder(
        client_org_id=org.id,
        created_by_user_id=u_client.id,
        title="Job2",
        job_type="Warehouse Worker",
        location_address="A",
        location_lat=1.0,
        location_lng=103.0,
        workers_required_total=1,
        pay_model=PayModel.hourly,
        hourly_rate=15.0,
        status=JobOrderStatus.open,
    )
    sqlite_session.add(job)
    await sqlite_session.flush()
    shift = Shift(
        job_order_id=job.id,
        starts_at=now + timedelta(hours=1),
        ends_at=now + timedelta(hours=5),
        workers_required=1,
    )
    sqlite_session.add(shift)
    await sqlite_session.flush()
    sqlite_session.add(
        ShiftOffer(shift_id=shift.id, worker_id=wp.id, status=ShiftOfferStatus.declined, match_score=0.0)
    )
    await sqlite_session.commit()

    accepted, declined = await _accepted_and_declined_for_job(sqlite_session, job)
    assert accepted == []
    assert len(declined) == 1
    assert declined[0].worker_profile_id == wp.id
