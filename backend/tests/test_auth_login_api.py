"""HTTP tests for /auth/login, phone OTP, and worker email OTP edge cases."""

import asyncio
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-jwt-tests-only-32b")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("OTP_DEV_MODE", "true")

import bcrypt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.routers import auth as auth_module
from app.db.base import Base
from app.db.session import get_db
from app.models import ClientOrganization, ClientProfile, User, UserRole, WorkerProfile, WorkerStatus
from app.routers import auth as auth_router

get_settings.cache_clear()

_app = FastAPI()
_app.include_router(auth_router.router)


def _hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=4)).decode()


@pytest.fixture(autouse=True)
def _verify_password_uses_bcrypt():
    """Avoid passlib init issues on some Python/bcrypt builds; login still reflects real bcrypt hashes."""
    orig = auth_module.verify_password

    def _v(plain: str, hashed: str | None) -> bool:
        if not hashed:
            return False
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError:
            return False

    auth_module.verify_password = _v
    yield
    auth_module.verify_password = orig


@pytest.fixture
def auth_client():
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
        yield tc, Session
    _app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def test_login_success(auth_client):
    client, Session = auth_client

    async def seed():
        async with Session() as s:
            u = User(
                username="ta_ops",
                role=UserRole.ta,
                locale="en",
                hashed_password=_hash_pw("correct-horse"),
                is_active=True,
            )
            s.add(u)
            await s.commit()
            return u.id

    uid = asyncio.run(seed())
    r = client.post("/auth/login", json={"username": "ta_ops", "password": "correct-horse"})
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == uid
    assert body["role"] == "ta"
    assert body["access_token"]


def test_login_wrong_password(auth_client):
    client, Session = auth_client

    async def seed():
        async with Session() as s:
            s.add(
                User(
                    username="u1",
                    role=UserRole.worker,
                    locale="en",
                    hashed_password=_hash_pw("secret"),
                    is_active=True,
                )
            )
            await s.commit()

    asyncio.run(seed())
    r = client.post("/auth/login", json={"username": "u1", "password": "wrong"})
    assert r.status_code == 401


def test_login_inactive_user(auth_client):
    client, Session = auth_client

    async def seed():
        async with Session() as s:
            s.add(
                User(
                    username="inactive",
                    role=UserRole.worker,
                    locale="en",
                    hashed_password=_hash_pw("x"),
                    is_active=False,
                )
            )
            await s.commit()

    asyncio.run(seed())
    r = client.post("/auth/login", json={"username": "inactive", "password": "x"})
    assert r.status_code == 401


def test_login_whitespace_username_becomes_empty(auth_client):
    client, _Session = auth_client
    r = client.post("/auth/login", json={"username": "   ", "password": "x"})
    assert r.status_code == 401


def test_login_missing_user(auth_client):
    client, _Session = auth_client
    r = client.post("/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


def test_login_user_without_password(auth_client):
    client, Session = auth_client

    async def seed():
        async with Session() as s:
            s.add(User(username="nopw", role=UserRole.worker, locale="en", hashed_password=None, is_active=True))
            await s.commit()

    asyncio.run(seed())
    r = client.post("/auth/login", json={"username": "nopw", "password": "anything"})
    assert r.status_code == 401


def test_phone_otp_verify_rejects_wrong_code_after_request(auth_client):
    client, Session = auth_client

    async def seed():
        async with Session() as s:
            s.add(User(phone="+15550001111", role=UserRole.worker, locale="en", is_active=True))
            await s.commit()

    asyncio.run(seed())
    client.post("/auth/otp/request", json={"phone": "+15550001111"})
    r = client.post("/auth/otp/verify", json={"phone": "+15550001111", "code": "000001"})
    assert r.status_code == 400


def test_phone_otp_verify_unknown_phone(auth_client):
    client, _Session = auth_client
    client.post("/auth/otp/request", json={"phone": "+15550009999"})
    r = client.post("/auth/otp/verify", json={"phone": "+15550009999", "code": "123456"})
    assert r.status_code == 401


def test_worker_email_otp_verify_wrong_code(auth_client):
    client, _Session = auth_client
    client.post("/auth/worker/email-otp/request", json={"email": "new.worker@example.com"})
    r = client.post(
        "/auth/worker/email-otp/verify",
        json={"email": "new.worker@example.com", "code": "000002"},
    )
    assert r.status_code == 400


def test_worker_email_otp_conflict_when_email_is_client(auth_client):
    client, Session = auth_client

    async def seed():
        async with Session() as s:
            org = ClientOrganization(name="Co")
            s.add(org)
            await s.flush()
            u = User(
                email="same@example.com",
                role=UserRole.client,
                locale="en",
                client_org_id=org.id,
                is_active=True,
            )
            s.add(u)
            await s.flush()
            s.add(ClientProfile(user_id=u.id, company_name="Co", contact_email="same@example.com"))
            await s.commit()

    asyncio.run(seed())
    client.post("/auth/worker/email-otp/request", json={"email": "same@example.com"})
    r = client.post(
        "/auth/worker/email-otp/verify",
        json={"email": "same@example.com", "code": "123456"},
    )
    assert r.status_code == 409


def test_worker_email_otp_rejects_inactive_worker_profile(auth_client):
    client, Session = auth_client

    async def seed():
        async with Session() as s:
            u = User(email="inactive.wp@example.com", role=UserRole.worker, locale="en", is_active=True)
            s.add(u)
            await s.flush()
            s.add(WorkerProfile(user_id=u.id, status=WorkerStatus.inactive))
            await s.commit()

    asyncio.run(seed())
    client.post("/auth/worker/email-otp/request", json={"email": "inactive.wp@example.com"})
    r = client.post(
        "/auth/worker/email-otp/verify",
        json={"email": "inactive.wp@example.com", "code": "123456"},
    )
    assert r.status_code == 403


def test_worker_email_login_request_rejects_unknown_email(auth_client):
    client, _Session = auth_client
    r = client.post(
        "/auth/worker/email-otp/request",
        json={"email": "missing.worker@example.com", "login_only": True},
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "User does not exist"


def test_worker_email_login_verify_rejects_unknown_email(auth_client):
    client, _Session = auth_client
    client.post(
        "/auth/worker/email-otp/request",
        json={"email": "missing.worker@example.com"},
    )
    r = client.post(
        "/auth/worker/email-otp/verify",
        json={"email": "missing.worker@example.com", "code": "123456", "login_only": True},
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "User does not exist"


def test_client_email_login_request_rejects_unknown_email(auth_client):
    client, _Session = auth_client
    r = client.post(
        "/auth/client/email-otp/request",
        json={"email": "missing.client@example.com", "login_only": True},
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "User does not exist"


def test_client_email_login_verify_rejects_unknown_email(auth_client):
    client, _Session = auth_client
    client.post(
        "/auth/client/email-otp/request",
        json={"email": "missing.client@example.com"},
    )
    r = client.post(
        "/auth/client/email-otp/verify",
        json={"email": "missing.client@example.com", "code": "123456", "login_only": True},
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "User does not exist"
