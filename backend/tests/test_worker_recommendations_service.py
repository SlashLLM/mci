from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
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
    User,
    UserRole,
    WorkerProfile,
    WorkerShiftRecommendation,
    WorkerStatus,
    WorkerTier,
)
from app.services.recommendations import get_worker_recommendations, recompute_worker_recommendations


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
async def test_recompute_worker_recommendations_marks_return_opportunity(sqlite_session: AsyncSession):
    now = datetime.now(timezone.utc)
    org1 = ClientOrganization(name="Client One")
    org2 = ClientOrganization(name="Client Two")
    sqlite_session.add_all([org1, org2])
    await sqlite_session.flush()

    client_user = User(phone="+19991110001", role=UserRole.client, locale="en", client_org_id=org1.id)
    client_user2 = User(phone="+19991110002", role=UserRole.client, locale="en", client_org_id=org2.id)
    worker_user = User(phone="+19991110003", role=UserRole.worker, locale="en")
    sqlite_session.add_all([client_user, client_user2, worker_user])
    await sqlite_session.flush()

    worker = WorkerProfile(
        user_id=worker_user.id,
        full_name="Rec Worker",
        languages=[],
        job_type_preferences=["Warehouse Worker"],
        skills=["Forklift"],
        certifications=[],
        availability={},
        location_lat=1.0,
        location_lng=103.0,
        tier=WorkerTier.standard,
        status=WorkerStatus.active,
    )
    sqlite_session.add(worker)
    await sqlite_session.flush()

    old_job = JobOrder(
        client_org_id=org1.id,
        created_by_user_id=client_user.id,
        title="Completed baseline",
        job_type="Warehouse Worker",
        location_address="SG",
        location_lat=1.0,
        location_lng=103.0,
        workers_required_total=1,
        pay_model=PayModel.hourly,
        hourly_rate=12.0,
        status=JobOrderStatus.completed,
    )
    sqlite_session.add(old_job)
    await sqlite_session.flush()
    old_shift = Shift(
        job_order_id=old_job.id,
        starts_at=now - timedelta(days=2),
        ends_at=now - timedelta(days=2, hours=-8),
        workers_required=1,
    )
    sqlite_session.add(old_shift)
    await sqlite_session.flush()
    sqlite_session.add(
        ShiftAssignment(
            shift_id=old_shift.id,
            worker_id=worker.id,
            status=AssignmentStatus.completed,
        )
    )

    returning_job = JobOrder(
        client_org_id=org1.id,
        created_by_user_id=client_user.id,
        title="Return Site Shift",
        job_type="Warehouse Worker",
        location_address="SG",
        location_lat=1.0,
        location_lng=103.0,
        workers_required_total=2,
        pay_model=PayModel.hourly,
        hourly_rate=20.0,
        status=JobOrderStatus.open,
    )
    fresh_job = JobOrder(
        client_org_id=org2.id,
        created_by_user_id=client_user2.id,
        title="New Client Shift",
        job_type="Warehouse Worker",
        location_address="SG",
        location_lat=1.2,
        location_lng=103.2,
        workers_required_total=2,
        pay_model=PayModel.hourly,
        hourly_rate=20.0,
        status=JobOrderStatus.open,
    )
    sqlite_session.add_all([returning_job, fresh_job])
    await sqlite_session.flush()

    shift_return = Shift(
        job_order_id=returning_job.id,
        starts_at=now + timedelta(hours=8),
        ends_at=now + timedelta(hours=16),
        workers_required=2,
    )
    shift_new = Shift(
        job_order_id=fresh_job.id,
        starts_at=now + timedelta(hours=10),
        ends_at=now + timedelta(hours=18),
        workers_required=2,
    )
    sqlite_session.add_all([shift_return, shift_new])
    await sqlite_session.commit()

    created = await recompute_worker_recommendations(sqlite_session, worker, source="test")
    assert created >= 2

    rows = (
        await sqlite_session.execute(
            select(WorkerShiftRecommendation).where(WorkerShiftRecommendation.worker_profile_id == worker.id)
        )
    ).scalars().all()
    assert len(rows) >= 2
    row_by_shift = {r.shift_id: r for r in rows}
    assert row_by_shift[shift_return.id].return_opportunity is True
    assert "return_opportunity" in (row_by_shift[shift_return.id].reason_flags or [])
    assert row_by_shift[shift_new.id].return_opportunity is False


@pytest.mark.asyncio
async def test_get_worker_recommendations_has_freshness(sqlite_session: AsyncSession):
    now = datetime.now(timezone.utc)
    org = ClientOrganization(name="Client")
    sqlite_session.add(org)
    await sqlite_session.flush()

    client_user = User(phone="+19991110011", role=UserRole.client, locale="en", client_org_id=org.id)
    worker_user = User(phone="+19991110012", role=UserRole.worker, locale="en")
    sqlite_session.add_all([client_user, worker_user])
    await sqlite_session.flush()

    worker = WorkerProfile(
        user_id=worker_user.id,
        full_name="Fresh Worker",
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
    sqlite_session.add(worker)
    await sqlite_session.flush()

    job = JobOrder(
        client_org_id=org.id,
        created_by_user_id=client_user.id,
        title="Fresh Shift",
        job_type="Warehouse Worker",
        location_address="SG",
        location_lat=1.0,
        location_lng=103.0,
        workers_required_total=1,
        pay_model=PayModel.hourly,
        hourly_rate=19.0,
        status=JobOrderStatus.open,
    )
    sqlite_session.add(job)
    await sqlite_session.flush()
    sqlite_session.add(
        Shift(
            job_order_id=job.id,
            starts_at=now + timedelta(hours=4),
            ends_at=now + timedelta(hours=12),
            workers_required=1,
        )
    )
    await sqlite_session.commit()

    rows, freshness = await get_worker_recommendations(sqlite_session, worker, limit=10)
    assert freshness is not None
    assert len(rows) == 1
