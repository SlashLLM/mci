"""Unit tests for rule-based matching score (PRD §9 soft ranking)."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import JobOrder, JobOrderStatus, JobTypeWeight, PayModel, WorkerProfile, WorkerStatus, WorkerTier
from app.services.matching import get_effective_weights_for_job, has_required_compliance, score_worker


def _weights() -> JobTypeWeight:
    return JobTypeWeight(
        job_type="test",
        weight_proximity=0.3,
        weight_rating=0.25,
        weight_job_type=0.2,
        weight_completion=0.15,
        weight_tier=0.1,
    )


def _job() -> JobOrder:
    return JobOrder(
        id=1,
        client_org_id=1,
        created_by_user_id=1,
        title="J",
        job_type="Warehouse Worker",
        location_address="x",
        location_lat=1.35,
        location_lng=103.82,
        workers_required_total=1,
        pay_model=PayModel.hourly,
        hourly_rate=10.0,
        status=JobOrderStatus.open,
    )


def test_score_worker_weights_sum_to_bounded():
    job = _job()
    w = _weights()
    worker = WorkerProfile(
        user_id=1,
        full_name="A",
        location_lat=1.35,
        location_lng=103.82,
        rating_avg=5.0,
        job_type_preferences=["Warehouse Worker"],
        completion_rate=1.0,
        tier=WorkerTier.elite,
        status=WorkerStatus.active,
    )
    s = score_worker(worker, job, w, is_preferred=False)
    assert 0.0 <= s <= 1.0 + 1e-6


def test_preferred_boost_increases_score():
    job = _job()
    w = _weights()
    worker = WorkerProfile(
        user_id=1,
        full_name="A",
        location_lat=1.35,
        location_lng=103.82,
        rating_avg=3.0,
        job_type_preferences=[],
        completion_rate=0.5,
        tier=WorkerTier.standard,
        status=WorkerStatus.active,
    )
    base = score_worker(worker, job, w, is_preferred=False)
    boosted = score_worker(worker, job, w, is_preferred=True)
    assert boosted >= base


def test_probation_tier_scores_below_standard():
    job = _job()
    w = _weights()
    common = dict(
        user_id=1,
        full_name="A",
        location_lat=1.35,
        location_lng=103.82,
        rating_avg=3.0,
        job_type_preferences=["Warehouse Worker"],
        completion_rate=1.0,
        status=WorkerStatus.active,
    )
    probation = WorkerProfile(**common, tier=WorkerTier.probation)
    standard = WorkerProfile(**common, tier=WorkerTier.standard)
    assert score_worker(probation, job, w, is_preferred=False) < score_worker(standard, job, w, is_preferred=False)


def test_compliance_required_certs():
    w = WorkerProfile(user_id=1, full_name="B", certifications=["food_hygiene"], status=WorkerStatus.active)
    assert has_required_compliance(w, ["food_hygiene"]) is True
    assert has_required_compliance(w, ["height_work"]) is False


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
async def test_job_order_override_weights_take_precedence(sqlite_session: AsyncSession):
    sqlite_session.add(
        JobTypeWeight(
            job_type="Warehouse Worker",
            weight_proximity=0.05,
            weight_rating=0.55,
            weight_job_type=0.1,
            weight_completion=0.2,
            weight_tier=0.1,
        )
    )
    await sqlite_session.flush()
    job = _job()
    job.match_weight_overrides = {
        "weight_proximity": 0.6,
        "weight_rating": 0.1,
        "weight_job_type": 0.1,
        "weight_completion": 0.1,
        "weight_tier": 0.1,
    }
    weights = await get_effective_weights_for_job(sqlite_session, job)
    assert weights.weight_proximity == pytest.approx(0.6)
    assert weights.weight_rating == pytest.approx(0.1)
