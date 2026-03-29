import time
from typing import Optional

import redis.asyncio as redis

from app.config import get_settings

_memory: dict[str, tuple[str, float]] = {}
_redis: Optional[redis.Redis] = None


async def get_redis_optional() -> Optional[redis.Redis]:
    """Public alias for integrations (reminders, queues)."""
    return await _get_redis()


async def _get_redis() -> Optional[redis.Redis]:
    global _redis
    if _redis is not None:
        return _redis
    try:
        _redis = redis.from_url(get_settings().redis_url, decode_responses=True)
        await _redis.ping()
        return _redis
    except Exception:
        _redis = None
        return None


async def set_otp(phone: str, code: str, ttl_seconds: int = 300) -> None:
    r = await _get_redis()
    if r:
        await r.setex(f"otp:{phone}", ttl_seconds, code)
        return
    _memory[phone] = (code, time.time() + ttl_seconds)


async def verify_otp(phone: str, code: str) -> bool:
    settings = get_settings()
    if settings.otp_dev_mode and code == settings.otp_dev_code:
        return True
    r = await _get_redis()
    if r:
        stored = await r.get(f"otp:{phone}")
        if stored and stored == code:
            await r.delete(f"otp:{phone}")
            return True
        return False
    if phone not in _memory:
        return False
    stored, exp = _memory[phone]
    if time.time() > exp:
        del _memory[phone]
        return False
    ok = stored == code
    if ok:
        del _memory[phone]
    return ok
