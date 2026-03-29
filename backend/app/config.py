from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    max_upload_bytes: int = 15 * 1024 * 1024  # override via MAX_UPLOAD_BYTES

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
