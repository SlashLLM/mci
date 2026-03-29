"""Encrypt sensitive fields at rest when FERNET_KEY is set."""

from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _fernet() -> Optional[Fernet]:
    key = get_settings().fernet_key.strip()
    if not key:
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_value(plain: str) -> str:
    f = _fernet()
    if not f:
        return plain
    return f.encrypt(plain.encode()).decode()


def decrypt_value(token: str) -> str:
    f = _fernet()
    if not f:
        return token
    try:
        return f.decrypt(token.encode()).decode()
    except InvalidToken:
        return token


def mask_nric(nric: str) -> str:
    s = nric.strip()
    if len(s) <= 4:
        return "****"
    return s[:2] + "*" * (len(s) - 4) + s[-2:]
