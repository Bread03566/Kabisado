import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app

ALLOWED = "http://localhost:5173"
EVIL = "https://evil.example"


def preflight(origin):
    with TestClient(app) as c:
        return c.options(
            "/api/health",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET",
                     "Access-Control-Request-Headers": "authorization"},
        )


def test_cors_rejects_unlisted_origin():
    res = preflight(EVIL)
    assert "access-control-allow-origin" not in res.headers


def test_cors_allows_listed_origin():
    res = preflight(ALLOWED)
    assert res.headers.get("access-control-allow-origin") == ALLOWED


def test_credentials_not_allowed():
    res = preflight(ALLOWED)
    assert "access-control-allow-credentials" not in res.headers


def test_short_jwt_secret_rejected_when_not_debug():
    with pytest.raises(ValidationError):
        Settings(JWT_SECRET="too-short", DEBUG=False, _env_file=None)


def test_short_jwt_secret_allowed_in_debug():
    assert Settings(JWT_SECRET="too-short", DEBUG=True, _env_file=None).JWT_SECRET == "too-short"


def test_wildcard_origin_rejected():
    with pytest.raises(ValidationError):
        Settings(JWT_SECRET="x" * 32, ALLOWED_ORIGINS="*", _env_file=None)


def test_production_safe_defaults(monkeypatch):
    for name in ("DEBUG", "GEMINI_ENABLED", "COOKIE_SECURE", "AUTO_CREATE_SCHEMA", "ARGON2_MEMORY_KIB",
                 "ARGON2_TIME_COST", "ALLOWED_ORIGINS", "MAX_UPLOAD_MB"):
        monkeypatch.delenv(name, raising=False)  # conftest overrides some for speed; check true defaults
    s = Settings(JWT_SECRET="x" * 32, _env_file=None)
    assert s.DEBUG is False
    assert s.GEMINI_ENABLED is False
    assert s.COOKIE_SECURE is True
    assert s.AUTO_CREATE_SCHEMA is False
    assert s.MAX_UPLOAD_MB == 10
    assert (s.ACCESS_TOKEN_MINUTES, s.REFRESH_TOKEN_DAYS) == (15, 7)
    assert (s.ARGON2_MEMORY_KIB, s.ARGON2_TIME_COST) == (19456, 2)
    assert (s.DB_POOL_SIZE, s.DB_MAX_OVERFLOW) == (3, 2)
    assert s.allowed_origins == [ALLOWED]
