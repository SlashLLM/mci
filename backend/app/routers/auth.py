import logging
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.otp_store import set_otp, verify_otp
from app.auth.passwords import verify_password
from app.config import get_settings
from app.db.session import get_db
from app.models import ClientOrganization, ClientProfile, User, UserRole, WorkerProfile
from app.schemas.auth import (
    LoginRequest,
    OtpRequest,
    OtpVerify,
    TokenResponse,
    ClientEmailOtpRequest,
    ClientEmailOtpVerify,
    WorkerEmailOtpRequest,
    WorkerEmailOtpVerify,
)
from app.services.resend_otp import send_email_otp

logger = logging.getLogger(__name__)

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


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _otp_key_email(email: str) -> str:
    return f"email:{_normalize_email(email)}"


def _locale_from_request(locale: str | None) -> str:
    if not locale:
        return "en"
    x = locale.strip().lower()
    if x.startswith("zh"):
        return "zh"
    return "en"


@router.post("/worker/email-otp/request")
async def worker_email_otp_request(body: WorkerEmailOtpRequest):
    settings = get_settings()
    norm = _normalize_email(str(body.email))
    if not norm:
        raise HTTPException(status_code=400, detail="Invalid email")
    key = _otp_key_email(norm)
    has_key = bool((settings.resend_api_key or "").strip())
    has_from = bool((settings.resend_from_email or settings.email_from or "").strip())
    # WARNING so it shows even if LOG_LEVEL was misconfigured
    logger.warning(
        "email-otp/request target=%s OTP_DEV_MODE=%s (True=no real email, only dev_code) resend_key=%s from=%s",
        norm,
        settings.otp_dev_mode,
        has_key,
        has_from,
    )
    if settings.otp_dev_mode:
        code = settings.otp_dev_code
    else:
        if not (settings.resend_api_key or "").strip():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery is not configured",
            )
        code = "".join(secrets.choice(string.digits) for _ in range(6))
    await set_otp(key, code)
    dev_code = code if settings.otp_dev_mode else None
    if not settings.otp_dev_mode:
        logger.info("Worker email OTP: sending via Resend to %s", norm)
        try:
            await send_email_otp(str(body.email).strip(), code)
        except RuntimeError as e:
            logger.warning("Email OTP not sent: %s", e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(e),
            ) from e
        except Exception as e:
            logger.exception("Failed to send email OTP")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to send verification email: {e!s}",
            ) from e
        logger.warning("email-otp/request Resend OK for %s (check provider dashboard if inbox empty)", norm)
    return {
        "ok": True,
        "message": "Verification code sent",
        "dev_code": dev_code,
        "delivery": "dev" if settings.otp_dev_mode else "resend",
    }


@router.post("/worker/email-otp/verify", response_model=TokenResponse)
async def worker_email_otp_verify(body: WorkerEmailOtpVerify, db: AsyncSession = Depends(get_db)):
    norm = _normalize_email(str(body.email))
    key = _otp_key_email(norm)
    if not await verify_otp(key, body.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    result = await db.execute(select(User).where(func.lower(User.email) == norm))
    user = result.scalar_one_or_none()
    if user:
        if user.role != UserRole.worker:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already registered with a different account type",
            )
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    else:
        loc = _locale_from_request(body.locale)
        user = User(
            email=norm,
            phone=None,
            role=UserRole.worker,
            locale=loc,
            username=None,
            hashed_password=None,
        )
        db.add(user)
        await db.flush()
        db.add(WorkerProfile(user_id=user.id))
        await db.flush()

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


@router.post("/client/email-otp/request")
async def client_email_otp_request(body: ClientEmailOtpRequest):
    settings = get_settings()
    norm = _normalize_email(str(body.email))
    if not norm:
        raise HTTPException(status_code=400, detail="Invalid email")
    key = _otp_key_email(norm)
    if settings.otp_dev_mode:
        code = settings.otp_dev_code
    else:
        if not (settings.resend_api_key or "").strip():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery is not configured",
            )
        code = "".join(secrets.choice(string.digits) for _ in range(6))
    await set_otp(key, code)
    dev_code = code if settings.otp_dev_mode else None
    if not settings.otp_dev_mode:
        try:
            await send_email_otp(str(body.email).strip(), code)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to send verification email: {e!s}",
            ) from e
    return {
        "ok": True,
        "message": "Verification code sent",
        "dev_code": dev_code,
        "delivery": "dev" if settings.otp_dev_mode else "resend",
    }


@router.post("/client/email-otp/verify", response_model=TokenResponse)
async def client_email_otp_verify(body: ClientEmailOtpVerify, db: AsyncSession = Depends(get_db)):
    norm = _normalize_email(str(body.email))
    key = _otp_key_email(norm)
    if not await verify_otp(key, body.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    result = await db.execute(select(User).where(func.lower(User.email) == norm))
    user = result.scalar_one_or_none()
    if user:
        if user.role != UserRole.client:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already registered with a different account type",
            )
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    else:
        loc = _locale_from_request(body.locale)
        org = ClientOrganization(name="New client organization")
        db.add(org)
        await db.flush()
        user = User(
            email=norm,
            phone=None,
            role=UserRole.client,
            locale=loc,
            username=None,
            hashed_password=None,
            client_org_id=org.id,
        )
        db.add(user)
        await db.flush()
        db.add(
            ClientProfile(
                user_id=user.id,
                company_name="",
                contact_email=norm,
            )
        )
        await db.flush()

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
