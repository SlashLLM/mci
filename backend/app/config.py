from functools import lru_cache
from typing import Any, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_bool(v: Any, *, default: bool) -> bool:
    """Parse bool from env strings (.env often uses false, "false", quoted values)."""
    if isinstance(v, bool):
        return v
    if v is None or v == "":
        return default
    s = str(v).strip().strip('"').strip("'").lower()
    if s in ("0", "false", "no", "off", "n", "disabled"):
        return False
    if s in ("1", "true", "yes", "on", "y", "enabled"):
        return True
    return default


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://mci:mci@localhost:5432/mci_workforce"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-secret-change-in-production"
    fernet_key: str = ""  # optional; if empty, PII stored plaintext in dev only (not recommended prod)

    upload_dir: str = "./uploads"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    otp_dev_mode: bool = True
    otp_dev_code: str = "123456"

    access_token_expire_minutes: int = 60 * 24 * 7
    shift_attendance_change_cutoff_hours: int = 4

    max_upload_bytes: int = 15 * 1024 * 1024  # override via MAX_UPLOAD_BYTES

    support_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""

    resend_api_key: str = ""
    resend_from_email: str = ""

    @field_validator("otp_dev_mode", mode="before")
    @classmethod
    def coerce_otp_dev_mode(cls, v: Any) -> bool:
        return _env_bool(v, default=True)

    @field_validator("resend_api_key", "resend_from_email", "email_from", mode="before")
    @classmethod
    def strip_quotes_whitespace(cls, v: Any) -> str:
        if v is None:
            return ""
        s = str(v).strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
            s = s[1:-1].strip()
        return s

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
