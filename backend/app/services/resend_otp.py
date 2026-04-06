import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


async def send_email_otp(to_email: str, code: str) -> None:
    settings = get_settings()
    key = (settings.resend_api_key or "").strip().strip('"').strip("'")
    from_addr = (settings.resend_from_email or settings.email_from or "").strip().strip('"').strip("'")
    if not key:
        raise RuntimeError("RESEND_API_KEY is not configured")
    if not from_addr:
        raise RuntimeError(
            "RESEND_FROM_EMAIL or EMAIL_FROM must be set. "
            "For Resend testing without a domain, use: onboarding@resend.dev"
        )

    plain = (
        f"Your one-time verification code is {code}. It expires in 5 minutes. "
        "If you did not request this, ignore this email."
    )
    payload = {
        "from": from_addr,
        "to": [to_email.strip()],
        "subject": "Your verification code",
        "html": (
            f"<p>Your one-time verification code is <strong style='font-size:1.25em'>{code}</strong>.</p>"
            "<p>It expires in 5 minutes. If you did not request this, you can ignore this email.</p>"
        ),
        "text": plain,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.RequestError as e:
        logger.exception("Resend request failed")
        raise RuntimeError(f"Could not reach email provider: {e}") from e

    if r.status_code >= 400:
        err_snippet = (r.text or "")[:2000]
        logger.warning("Resend API error status=%s body=%s", r.status_code, err_snippet)
        hint = ""
        if r.status_code == 403:
            hint = " Check that RESEND_API_KEY is valid and not revoked."
        elif r.status_code == 422:
            hint = (
                " The `from` address must use a domain you verified in Resend, "
                "or use onboarding@resend.dev for sandbox sends."
            )
        raise RuntimeError(
            f"Email provider returned HTTP {r.status_code}.{hint} Details: {err_snippet}"
        )

    try:
        data = r.json()
        rid = data.get("id")
        if rid:
            logger.info("Resend accepted email id=%s to=%s", rid, to_email.strip()[:48])
    except Exception:
        logger.info("Resend email accepted (HTTP %s)", r.status_code)
