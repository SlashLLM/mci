import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger(__name__)


def send_support_email(subject: str, body: str) -> None:
    settings = get_settings()
    to_addr = (settings.support_email or "").strip()
    if not to_addr:
        logger.warning("support_email not set; skipping outbound email: %s", subject)
        return
    host = (settings.smtp_host or "").strip()
    if not host:
        logger.warning("SMTP not configured; support email (not sent): %s | %s", subject, body[:500])
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = (settings.email_from or settings.smtp_user or "noreply@localhost").strip()
    msg["To"] = to_addr
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, settings.smtp_port, timeout=30) as smtp:
            if settings.smtp_user and settings.smtp_password:
                smtp.starttls()
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except OSError as e:
        logger.exception("Failed to send support email: %s", e)
