import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.otp_store import set_otp, verify_otp
from app.auth.passwords import verify_password
from app.config import get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, OtpRequest, OtpVerify, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

_LOGIN_FAILED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid username or password",
)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    uname = body.username.strip()
    if not uname:
        raise _LOGIN_FAILED
    result = await db.execute(select(User).where(User.username == uname))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not user.hashed_password:
        raise _LOGIN_FAILED
    if not verify_password(body.password, user.hashed_password):
        raise _LOGIN_FAILED
    token = create_access_token(
        str(user.id),
        {"role": user.role.value, "locale": user.locale},
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role.value,
        locale=user.locale,
    )


def _normalize_phone(phone: str) -> str:
    return phone.strip().replace(" ", "")


@router.post("/otp/request")
async def request_otp(body: OtpRequest):
    settings = get_settings()
    phone = _normalize_phone(body.phone)
    if settings.otp_dev_mode:
        code = settings.otp_dev_code
    else:
        code = "".join(secrets.choice(string.digits) for _ in range(6))
    await set_otp(phone, code)
    # In production, send SMS here
    return {"ok": True, "message": "OTP sent", "dev_code": code if settings.otp_dev_mode else None}


@router.post("/otp/verify", response_model=TokenResponse)
async def verify_otp_endpoint(body: OtpVerify, db: AsyncSession = Depends(get_db)):
    phone = _normalize_phone(body.phone)
    if not await verify_otp(phone, body.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No account for this phone. Registration is disabled.",
        )

    token = create_access_token(
        str(user.id),
        {"role": user.role.value, "locale": user.locale},
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role.value,
        locale=user.locale,
    )
