import asyncio
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-jwt-tests-only-32b")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("OTP_DEV_MODE", "true")

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.routers import auth as auth_router
from app.routers import client_portal as client_router

get_settings.cache_clear()

_app = FastAPI()
_app.include_router(auth_router.router)
_app.include_router(client_router.router)


@pytest.fixture
def client():
    async def init():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return engine

    engine = asyncio.run(init())
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    _app.dependency_overrides[get_db] = override_get_db
    with TestClient(_app) as tc:
        yield tc
    _app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def _auth_headers(client: TestClient) -> dict[str, str]:
    client.post("/auth/client/email-otp/request", json={"email": "org.owner@example.com"})
    r = client.post("/auth/client/email-otp/verify", json={"email": "org.owner@example.com", "code": "123456"})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_client_profile_update_and_complete_onboarding(client: TestClient):
    headers = _auth_headers(client)
    r0 = client.get("/client/me/profile", headers=headers)
    assert r0.status_code == 200
    assert r0.json()["onboarding_completed"] is False

    r1 = client.put(
        "/client/me/profile",
        headers=headers,
        json={
            "company_name": "Acme Logistics",
            "contact_name": "Alice Tan",
            "contact_email": "ops@acme.example",
            "contact_phone": "+6588889999",
            "address_line": "1 Raffles Place",
            "location_lat": 1.283,
            "location_lng": 103.851,
            "billing_notes": "Net 30",
        },
    )
    assert r1.status_code == 200
    assert r1.json()["company_name"] == "Acme Logistics"

    r2 = client.post("/client/me/pdpa-consent", headers=headers)
    assert r2.status_code == 200

    r3 = client.post("/client/me/onboarding/complete", headers=headers, json={"terms_accepted": True})
    assert r3.status_code == 200
    assert r3.json()["ok"] is True

    r4 = client.get("/client/me/profile", headers=headers)
    assert r4.status_code == 200
    assert r4.json()["onboarding_completed"] is True
