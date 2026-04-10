"""TA worker management updates and blacklist enforcement endpoints."""

import asyncio
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-jwt-tests-only-32b")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.jwt import create_access_token
from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.models import (
    ClientOrganization,
    JobOrder,
    JobOrderStatus,
    PayModel,
    Shift,
    ShiftOffer,
    ShiftOfferStatus,
    User,
    UserRole,
    WorkerProfile,
    WorkerStatus,
    WorkerTier,
)
from app.routers import worker_app as worker_app_router
from app.routers import workers as workers_router

get_settings.cache_clear()

_app = FastAPI()
_app.include_router(workers_router.router)
_app.include_router(worker_app_router.router)


@pytest.fixture
def worker_management_setup():
    async def init():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        now = datetime.now(timezone.utc)
        async with Session() as s:
            org = ClientOrganization(name="Org")
            s.add(org)
            await s.flush()
            ta_user = User(phone="+18880001001", role=UserRole.ta, locale="en")
            worker_user = User(phone="+18880001002", role=UserRole.worker, locale="en")
            s.add_all([ta_user, worker_user])
            await s.flush()
            wp = WorkerProfile(
                user_id=worker_user.id,
                full_name="Managed Worker",
                languages=["en"],
                job_type_preferences=["Warehouse Worker"],
                skills=["forklift"],
                certifications=[],
                availability={},
                tier=WorkerTier.standard,
                status=WorkerStatus.active,
            )
            s.add(wp)
            await s.flush()
            job = JobOrder(
                client_org_id=org.id,
                created_by_user_id=ta_user.id,
                title="Open Shift",
                job_type="Warehouse Worker",
                location_address="SG",
                location_lat=1.0,
                location_lng=103.0,
                workers_required_total=1,
                pay_model=PayModel.hourly,
                hourly_rate=20.0,
                status=JobOrderStatus.open,
            )
            s.add(job)
            await s.flush()
            shift = Shift(
                job_order_id=job.id,
                starts_at=now + timedelta(hours=2),
                ends_at=now + timedelta(hours=10),
                workers_required=1,
            )
            s.add(shift)
            await s.flush()
            offer = ShiftOffer(
                shift_id=shift.id,
                worker_id=wp.id,
                status=ShiftOfferStatus.pending,
                match_score=0.8,
            )
            s.add(offer)
            await s.commit()
            return engine, Session, ta_user.id, worker_user.id, wp.id, shift.id, offer.id

    engine, Session, ta_user_id, worker_user_id, worker_profile_id, shift_id, offer_id = asyncio.run(init())

    async def override_get_db():
        async with Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    _app.dependency_overrides[get_db] = override_get_db
    ta_token = create_access_token(str(ta_user_id), {})
    worker_token = create_access_token(str(worker_user_id), {})
    try:
        with TestClient(_app) as client:
            yield client, ta_token, worker_token, worker_profile_id, shift_id, offer_id
    finally:
        _app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_ta_can_update_worker_management(worker_management_setup):
    client, ta_token, _worker_token, worker_profile_id, _shift_id, _offer_id = worker_management_setup
    r = client.patch(
        f"/workers/{worker_profile_id}/management",
        headers={"Authorization": f"Bearer {ta_token}"},
        json={
            "status": "inactive",
            "internal_notes": "No-show follow-up required",
            "follow_up_required": True,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "inactive"
    assert data["internal_notes"] == "No-show follow-up required"
    assert data["follow_up_required"] is True


def test_directory_includes_follow_up_and_filter(worker_management_setup):
    client, ta_token, _worker_token, worker_profile_id, _shift_id, _offer_id = worker_management_setup
    up = client.patch(
        f"/workers/{worker_profile_id}/management",
        headers={"Authorization": f"Bearer {ta_token}"},
        json={"follow_up_required": True},
    )
    assert up.status_code == 200, up.text
    r = client.get("/workers/directory", headers={"Authorization": f"Bearer {ta_token}"})
    assert r.status_code == 200, r.text
    rows = r.json()
    w = next(x for x in rows if x["id"] == worker_profile_id)
    assert w.get("follow_up_required") is True

    req_only = client.get(
        "/workers/directory?follow_up_filter=required",
        headers={"Authorization": f"Bearer {ta_token}"},
    )
    assert req_only.status_code == 200
    assert any(x["id"] == worker_profile_id for x in req_only.json())

    not_req = client.get(
        "/workers/directory?follow_up_filter=not_required",
        headers={"Authorization": f"Bearer {ta_token}"},
    )
    assert not_req.status_code == 200
    assert all(not x.get("follow_up_required") for x in not_req.json())
    assert not any(x["id"] == worker_profile_id for x in not_req.json())


def test_blacklisted_worker_sees_empty_marketplace_and_offers(worker_management_setup):
    client, ta_token, worker_token, worker_profile_id, _shift_id, _offer_id = worker_management_setup
    bl = client.patch(
        f"/workers/{worker_profile_id}/management",
        headers={"Authorization": f"Bearer {ta_token}"},
        json={"status": "blacklisted"},
    )
    assert bl.status_code == 200, bl.text
    m = client.get("/worker/marketplace/shifts", headers={"Authorization": f"Bearer {worker_token}"})
    assert m.status_code == 200, m.text
    assert m.json() == []
    o = client.get("/worker/offers", headers={"Authorization": f"Bearer {worker_token}"})
    assert o.status_code == 200, o.text
    assert o.json() == []


def test_blacklisted_worker_cannot_apply_or_accept_offer(worker_management_setup):
    client, ta_token, worker_token, worker_profile_id, shift_id, offer_id = worker_management_setup

    blacklist = client.patch(
        f"/workers/{worker_profile_id}/management",
        headers={"Authorization": f"Bearer {ta_token}"},
        json={"status": "blacklisted"},
    )
    assert blacklist.status_code == 200, blacklist.text

    apply_res = client.post(
        f"/worker/marketplace/shifts/{shift_id}/apply",
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert apply_res.status_code == 403, apply_res.text
    assert "blacklisted" in apply_res.text.lower()

    accept_res = client.post(
        f"/worker/offers/{offer_id}/accept",
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert accept_res.status_code == 403, accept_res.text
    assert "blacklisted" in accept_res.text.lower()
