import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# backend/ — relative paths in settings resolve from here, not from the
# directory the server happens to be started in.
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    APP_NAME: str = "Kabisado API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Storage & Database
    DATABASE_URL: str = "sqlite:///./kabisado.db"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 20

    # Gemini AI
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    # Comma-separated models tried in order when the main one is overloaded or slow
    GEMINI_FALLBACK_MODELS: str = "gemini-3.8-flash"
    GEMINI_TIMEOUT_SECONDS: float = 60.0

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
