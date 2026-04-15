"""HTTP tests for /admin PDPA deactivate, mark no-shows, and audit log listing."""

import asyncio
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-jwt-tests-only-32b")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.jwt import create_access_token
from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.models import (
    AssignmentStatus,
    AuditLog,
    ClientOrganization,
    JobOrder,
    JobOrderStatus,
    PayModel,
    Shift,
    ShiftAssignment,
    User,
    UserRole,
    WorkerProfile,
    WorkerTier,
)
from app.routers import admin as admin_router

get_settings.cache_clear()

_app = FastAPI()
_app.include_router(admin_router.router)


@pytest.fixture
def admin_setup():
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
            admin = User(phone="+16660001001", role=UserRole.admin, locale="en", is_active=True)
            ta = User(phone="+16660001002", role=UserRole.ta, locale="en", is_active=True)
            worker = User(phone="+16660001003", role=UserRole.worker, locale="en", is_active=True)
            s.add_all([admin, ta, worker])
            await s.flush()
            wp = WorkerProfile(
                user_id=worker.id,
                full_name="NS Worker",
                languages=["en"],
                job_type_preferences=["Warehouse Worker"],
                skills=[],
                certifications=[],
                availability={},
                tier=WorkerTier.standard,
            )
            s.add(wp)
            await s.flush()
            job = JobOrder(
                client_org_id=org.id,
                created_by_user_id=ta.id,
                title="Past shift",
                job_type="Warehouse Worker",
                location_address="SG",
                location_lat=1.0,
                location_lng=103.0,
                workers_required_total=1,
                pay_model=PayModel.hourly,
                hourly_rate=15.0,
                status=JobOrderStatus.open,
                no_show_grace_minutes=15,
            )
            s.add(job)
            await s.flush()
            shift = Shift(
                job_order_id=job.id,
                starts_at=now - timedelta(hours=3),
                ends_at=now - timedelta(hours=2),
                workers_required=1,
            )
            s.add(shift)
            await s.flush()
            asn = ShiftAssignment(shift_id=shift.id, worker_id=wp.id, status=AssignmentStatus.confirmed)
            s.add(asn)
            s.add(
                AuditLog(
                    actor_user_id=admin.id,
                    action="test_action",
                    entity_type="User",
                    entity_id=str(worker.id),
                )
            )
            await s.commit()
            return engine, Session, admin.id, ta.id, worker.id, shift.id

    engine, Session, admin_id, ta_id, worker_id, shift_id = asyncio.run(init())

    async def override_get_db():
        async with Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    _app.dependency_overrides[get_db] = override_get_db
    tokens = {
        "admin": create_access_token(str(admin_id), {}),
        "ta": create_access_token(str(ta_id), {}),
        "worker": create_access_token(str(worker_id), {}),
    }
    try:
        with TestClient(_app) as client:
            yield client, Session, tokens, worker_id, shift_id
    finally:
        _app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_pdpa_deactivate_admin_only(admin_setup):
    client, _Session, tokens, worker_id, _shift_id = admin_setup
    r = client.post(
        f"/admin/pdpa/user/{worker_id}/deactivate",
        headers={"Authorization": f"Bearer {tokens['worker']}"},
    )
    assert r.status_code == 403

    r2 = client.post(
        f"/admin/pdpa/user/{worker_id}/deactivate",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    assert r2.status_code == 200
    assert r2.json()["ok"] is True


def test_pdpa_deactivate_unknown_user(admin_setup):
    client, _Session, tokens, _worker_id, _shift_id = admin_setup
    r = client.post(
        "/admin/pdpa/user/999999/deactivate",
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    assert r.status_code == 404


def test_mark_no_shows_ta_and_admin_allowed(admin_setup):
    client, Session, tokens, _worker_id, shift_id = admin_setup
    r = client.post(
        f"/admin/shifts/{shift_id}/mark-no-shows",
        headers={"Authorization": f"Bearer {tokens['ta']}"},
    )
    assert r.status_code == 200
    assert r.json()["marked"] >= 1

    async def check_assignment():
        async with Session() as s:
            r2 = await s.execute(select(ShiftAssignment).where(ShiftAssignment.shift_id == shift_id))
            a = r2.scalar_one()
            assert a.status == AssignmentStatus.no_show

    asyncio.run(check_assignment())


def test_audit_logs_admin_and_ta_not_worker(admin_setup):
    client, _Session, tokens, _worker_id, _shift_id = admin_setup
    rw = client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {tokens['worker']}"})
    assert rw.status_code == 403

    ra = client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {tokens['admin']}"})
    assert ra.status_code == 200
    assert isinstance(ra.json(), list)
    assert any(x.get("action") == "test_action" for x in ra.json())

    rt = client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {tokens['ta']}"})
    assert rt.status_code == 200
