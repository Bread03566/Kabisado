"""Shared test helpers for authenticated API tests."""
import uuid

from app.config import settings

STRONG_PASSWORD = "Zq7!mK2pXwR9"
CSRF = {"X-Kabisado-Request": "1"}


def unique_username(prefix: str = "stu") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def register_user(client, username: str | None = None, display_name: str = "Test Student",
                  password: str = STRONG_PASSWORD) -> tuple[dict, str, str]:
    """Register a fresh student. Returns (auth headers, username, recovery code)."""
    username = username or unique_username()
    res = client.post("/api/auth/register", json={
        "display_name": display_name, "username": username,
        "password": password, "confirm_password": password,
    })
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}, username, res.json()["recovery_code"]


def refresh_cookie_value(response) -> str | None:
    """The refresh token from a response's Set-Cookie (cookies are Secure, so tests pass them by hand)."""
    prefix = settings.refresh_cookie_name + "="
    for header in response.headers.get_list("set-cookie"):
        if header.startswith(prefix):
            return header.split(";", 1)[0][len(prefix):]
    return None


def post_refresh(client, token: str | None, **extra_headers):
    headers = {**CSRF, **extra_headers}
    if token is not None:
        headers["Cookie"] = f"{settings.refresh_cookie_name}={token}"
    client.cookies.clear()
    return client.post("/api/auth/refresh", headers=headers)
