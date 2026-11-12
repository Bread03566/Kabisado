import os
from pathlib import Path
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# backend/ — relative paths in settings resolve from here, not from the
# directory the server happens to be started in.
BASE_DIR = Path(__file__).resolve().parent.parent


def normalize_database_url(url: str) -> str:
    """Hosts hand out `postgres://` or `postgresql://`; SQLAlchemy needs the psycopg 3 driver named."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Settings(BaseSettings):
    APP_NAME: str = "Kabisado API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Storage & Database
    DATABASE_URL: str = "sqlite:///./kabisado.db"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 10
    DB_POOL_SIZE: int = 3
    DB_MAX_OVERFLOW: int = 2
    # False in production: the schema is owned by Alembic and the app only checks its revision.
    AUTO_CREATE_SCHEMA: bool = False

    # Web / auth
    ALLOWED_ORIGINS: str = "http://localhost:5173"  # comma-separated; never "*"
    JWT_SECRET: str  # required; no default so a forgotten secret fails loudly
    JWT_SECRET_PREVIOUS: Optional[str] = None  # accepted for verification while rotating JWT_SECRET
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 7
    COOKIE_SECURE: bool = True  # false only for local http development
    ARGON2_MEMORY_KIB: int = 19456
    ARGON2_TIME_COST: int = 2

    # Gemini AI. Global kill switch: nothing is ever sent to Google unless this is true, even when a
    # key is set. Stays false until the owner has verified billing and reviewed Google's terms.
    GEMINI_ENABLED: bool = False
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    # Comma-separated models tried in order when the main one is overloaded or slow
    GEMINI_FALLBACK_MODELS: str = "gemini-3.8-flash"
    GEMINI_TIMEOUT_SECONDS: float = 60.0

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def no_wildcard_origin(cls, value: str) -> str:
        if "*" in value:
            raise ValueError("ALLOWED_ORIGINS must list explicit origins, not '*'.")
        return value

    @model_validator(mode="after")
    def jwt_secret_is_strong(self):
        if not self.DEBUG and len(self.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters.")
        return self

    @property
    def gemini_models(self) -> list[str]:
        extra = [m.strip() for m in self.GEMINI_FALLBACK_MODELS.split(",") if m.strip()]
        return [self.GEMINI_MODEL] + [m for m in extra if m != self.GEMINI_MODEL]

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def anchor_sqlite_path(cls, url: str) -> str:
        url = normalize_database_url(url)
        prefix = "sqlite:///"
        if not url.startswith(prefix) or url.startswith(prefix + "/") or url == "sqlite:///:memory:":
            return url
        path = Path(url[len(prefix):])
        if path.is_absolute():
            return url
        return prefix + (BASE_DIR / path).resolve().as_posix()

    @field_validator("UPLOAD_DIR")
    @classmethod
    def anchor_upload_dir(cls, value: str) -> str:
        path = Path(value)
        return str(path if path.is_absolute() else (BASE_DIR / path).resolve())

settings = Settings()

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
