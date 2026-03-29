"""Integration-style check: dismissed shifts are omitted from marketplace recommendations."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import (
    ClientOrganization,
    JobOrder,
    JobOrderStatus,
    MarketplaceShiftDismissal,
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
async def test_recommended_shifts_excludes_dismissed_listing(sqlite_session: AsyncSession):
    now = datetime.now(timezone.utc)

    org = ClientOrganization(name="Test Org")
    sqlite_session.add(org)
    await sqlite_session.flush()

    u_client = User(phone="+19990000001", role=UserRole.client, locale="en", client_org_id=org.id)
    u_worker = User(phone="+19990000002", role=UserRole.worker, locale="en")
    sqlite_session.add_all([u_client, u_worker])
    await sqlite_session.flush()

    wp = WorkerProfile(
        user_id=u_worker.id,
        full_name="Test Worker",
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
        title="Dock shift",
        job_type="Warehouse Worker",
        location_address="Somewhere",
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
        starts_at=now + timedelta(hours=2),
        ends_at=now + timedelta(hours=10),
        workers_required=1,
    )
    sqlite_session.add(shift)
    await sqlite_session.flush()
    await sqlite_session.commit()

    ranked_before = await recommended_shifts_for_worker(sqlite_session, wp, limit=50)
    assert len(ranked_before) == 1
    assert ranked_before[0][0].id == shift.id

    sqlite_session.add(MarketplaceShiftDismissal(worker_profile_id=wp.id, shift_id=shift.id))
    await sqlite_session.commit()

    ranked_after = await recommended_shifts_for_worker(sqlite_session, wp, limit=50)
    assert ranked_after == []
