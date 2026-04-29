"""Performance priority: marketplace listing respects Elite-only window after publish."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import (
    AutomaticDispatchMode,
    ClientOrganization,
    JobOrder,
    JobOrderStatus,
    PayModel,
    Shift,
    User,
    UserRole,
    WorkerProfile,
    WorkerStatus,
    WorkerTier,
)
from app.services.recommendations import recommended_shifts_for_worker


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
async def test_performance_priority_marketplace_elite_window(sqlite_session: AsyncSession):
    now = datetime.now(timezone.utc)
    org = ClientOrganization(name="Org")
    sqlite_session.add(org)
    await sqlite_session.flush()

    u_client = User(phone="+18880000001", role=UserRole.client, locale="en", client_org_id=org.id)
    u_std = User(phone="+18880000002", role=UserRole.worker, locale="en")
    u_elite = User(phone="+18880000003", role=UserRole.worker, locale="en")
    sqlite_session.add_all([u_client, u_std, u_elite])
    await sqlite_session.flush()

    wp_std = WorkerProfile(
        user_id=u_std.id,
        full_name="Standard",
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
    wp_elite = WorkerProfile(
        user_id=u_elite.id,
        full_name="Elite",
        languages=[],
        job_type_preferences=["Warehouse Worker"],
        skills=[],
        certifications=[],
        availability={},
        location_lat=1.0,
        location_lng=103.0,
        tier=WorkerTier.elite,
        status=WorkerStatus.active,
    )
    sqlite_session.add_all([wp_std, wp_elite])
    await sqlite_session.flush()

    job = JobOrder(
        client_org_id=org.id,
        created_by_user_id=u_client.id,
        title="Perf job",
        job_type="Warehouse Worker",
        location_address="Somewhere",
        location_lat=1.0,
        location_lng=103.0,
        workers_required_total=1,
        pay_model=PayModel.hourly,
        hourly_rate=15.0,
        status=JobOrderStatus.open,
        automatic_dispatch_enabled=True,
        automatic_dispatch_mode=AutomaticDispatchMode.performance_priority,
        automatic_dispatch_priority_window_minutes=120,
        published_at=now - timedelta(minutes=30),
    )
    sqlite_session.add(job)
    await sqlite_session.flush()

    shift = Shift(
        job_order_id=job.id,
        starts_at=now + timedelta(hours=4),
        ends_at=now + timedelta(hours=12),
        workers_required=1,
    )
    sqlite_session.add(shift)
    await sqlite_session.commit()

    std_list = await recommended_shifts_for_worker(sqlite_session, wp_std, limit=50)
    assert std_list == []

    elite_list = await recommended_shifts_for_worker(sqlite_session, wp_elite, limit=50)
    assert len(elite_list) == 1
    assert elite_list[0][0].id == shift.id

    job.published_at = now - timedelta(hours=3)
    await sqlite_session.commit()

    std_list_after = await recommended_shifts_for_worker(sqlite_session, wp_std, limit=50)
    assert len(std_list_after) == 1
    assert std_list_after[0][0].id == shift.id
