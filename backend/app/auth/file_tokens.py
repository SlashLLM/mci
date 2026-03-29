"""Short-lived JWTs for signed file download URLs."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt

from app.config import get_settings

ALGORITHM = "HS256"
FILE_AUD = "mci-file"


def create_file_access_token(
    *,
    subject: str,
    extra: dict[str, Any],
    expires_minutes: int = 15,
) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode = {"sub": subject, "exp": expire, "aud": FILE_AUD, **extra}
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_file_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM], audience=FILE_AUD)
