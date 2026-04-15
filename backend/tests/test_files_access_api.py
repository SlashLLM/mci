"""HTTP tests for /files/access signed URL redemption and path hardening."""

import os
import tempfile

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-jwt-tests-only-32b")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.file_tokens import create_file_access_token
from app.config import get_settings
from app.routers import files as files_router

get_settings.cache_clear()

_app = FastAPI()
_app.include_router(files_router.router)


@pytest.fixture
def files_client():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["UPLOAD_DIR"] = tmp
        get_settings.cache_clear()
        sub = os.path.join(tmp, "docs")
        os.makedirs(sub, exist_ok=True)
        p = os.path.join(sub, "hello.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("ok")
        with TestClient(_app) as client:
            yield client, "uploads/docs/hello.txt"
        get_settings.cache_clear()


def test_files_access_happy_path(files_client):
    client, rel = files_client
    token = create_file_access_token(subject=rel, extra={})
    r = client.get("/files/access", params={"token": token})
    assert r.status_code == 200
    assert b"ok" in r.content


def test_files_access_invalid_jwt(files_client):
    client, _rel = files_client
    r = client.get("/files/access", params={"token": "not-a.jwt.token"})
    assert r.status_code == 401


def test_files_access_path_traversal_subject_rejected(files_client):
    client, _rel = files_client
    token = create_file_access_token(subject="uploads/../../etc/passwd", extra={})
    r = client.get("/files/access", params={"token": token})
    assert r.status_code == 400


def test_files_access_missing_file(files_client):
    client, _rel = files_client
    token = create_file_access_token(subject="uploads/docs/ghost.txt", extra={})
    r = client.get("/files/access", params={"token": token})
    assert r.status_code == 404
