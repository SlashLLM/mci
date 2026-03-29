"""Signed JWTs embedded in client-displayed QR codes for shift clock-in/out."""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import get_settings

ALGORITHM = "HS256"
ATTENDANCE_QR_AUD = "mci-attendance-qr"
# Cap token lifetime so QR codes do not work indefinitely
_MAX_TOKEN_TTL = timedelta(hours=48)
_QR_VALID_AFTER_SHIFT = timedelta(hours=6)


def create_attendance_qr_token(
    *,
    job_id: int,
    shift_id: int,
    action: str,
    shift_ends_at: datetime,
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    ends = shift_ends_at if shift_ends_at.tzinfo else shift_ends_at.replace(tzinfo=timezone.utc)
    exp_by_shift = ends + _QR_VALID_AFTER_SHIFT
    exp_cap = now + _MAX_TOKEN_TTL
    exp = min(exp_by_shift, exp_cap)
    if exp <= now:
        exp = now + timedelta(minutes=30)
    to_encode = {
        "job_id": job_id,
        "shift_id": shift_id,
        "action": action,
        "exp": exp,
        "aud": ATTENDANCE_QR_AUD,
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_attendance_qr_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[ALGORITHM],
        audience=ATTENDANCE_QR_AUD,
    )
