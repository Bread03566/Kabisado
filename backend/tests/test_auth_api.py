import concurrent.futures
import threading
import unicodedata

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.models import LoginAttempt, User
from tests.helpers import CSRF, STRONG_PASSWORD, post_refresh, refresh_cookie_value, register_user, unique_username


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def body(username, password=STRONG_PASSWORD, **over):
    data = {"display_name": "Ana Reyes", "username": username, "password": password, "confirm_password": password}
    data.update(over)
    return data


def login(client, username, password=STRONG_PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


# ---------- register ----------
def test_register_returns_token_recovery_code_and_secure_cookie(client):
    u = unique_username()
    res = client.post("/api/auth/register", json=body(u))
    assert res.status_code == 201
    data = res.json()
    assert data["user"]["role"] == "student" and data["user"]["username"] == u and data["user"]["display_name"] == "Ana Reyes"
    assert data["access_token"] and len(data["recovery_code"].replace("-", "")) == 26
    assert STRONG_PASSWORD not in res.text and "password_hash" not in res.text
    cookie = next(h for h in res.headers.get_list("set-cookie") if h.startswith(settings.refresh_cookie_name))
    assert settings.refresh_cookie_name.startswith("__Host-")
    for flag in ("httponly", "secure", "samesite=strict", "path=/"):
        assert flag in cookie.lower()


@pytest.mark.parametrize("extra", [{"role": "admin"}, {"is_active": False}, {"subject_ref": "x" * 32}, {"email": "a@b.c"}])
def test_register_rejects_unknown_or_privileged_fields(client, extra):
    assert client.post("/api/auth/register", json=body(unique_username(), **extra)).status_code == 422


def test_duplicate_and_lookalike_usernames_create_exactly_one_account(client):
    base = unique_username("ana")
    assert client.post("/api/auth/register", json=body(base)).status_code == 201
    fullwidth = "".join(chr(ord(c) + 0xFEE0) if c.isalnum() else c for c in base)
    assert unicodedata.normalize("NFKC", fullwidth) == base and fullwidth != base
    for variant in (base, base.upper(), " " + base + " ", fullwidth):
        res = client.post("/api/auth/register", json=body(variant))
        assert res.status_code in (409, 422), (variant, res.status_code)
    with SessionLocal() as db:
        assert db.query(User).filter(User.username.like(base + "%")).count() == 1


def test_concurrent_registration_of_one_username_has_one_winner():
    u = unique_username("race")
    barrier = threading.Barrier(2)

    def attempt(_):
        with TestClient(app) as c:
            barrier.wait()
            return c.post("/api/auth/register", json=body(u)).status_code

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(attempt, range(2)))
    assert codes == [201, 409]


def test_overlong_password_rejected_before_any_hashing(client, monkeypatch):
    import app.routers.auth as auth_router

    async def boom(_):
        raise AssertionError("hash_password must not run for oversized input")

    monkeypatch.setattr(auth_router, "hash_password", boom)
    for size in (129, 5_000_000):
        pw = ("Aa1!" * (size // 4 + 1))[:size]
        res = client.post("/api/auth/register", json=body(unique_username(), password=pw))
        assert res.status_code == 422, size


@pytest.mark.parametrize("over,needle", [
    ({"confirm_password": "different-Pass-1"}, "match"),
    ({"password": "short1!", "confirm_password": "short1!"}, "10"),
    ({"password": "password123", "confirm_password": "password123"}, "common"),
    ({"username": "ab"}, ""),
    ({"username": "has space"}, ""),
    ({"username": "x" * 33}, ""),
    ({"display_name": "   "}, ""),
    ({"display_name": "bad\x00name"}, ""),
])
def test_registration_validation_errors(client, over, needle):
    data = body(unique_username())
    data.update(over)
    res = client.post("/api/auth/register", json=data)
    assert res.status_code == 422
    assert needle in res.text


# ---------- login ----------
def test_login_success_returns_token_and_cookie(client):
    _, u, _ = register_user(client)
    res = login(client, u)
    assert res.status_code == 200 and res.json()["access_token"] and refresh_cookie_value(res)


def test_login_failure_is_identical_for_unknown_user_and_wrong_password(client):
    _, u, _ = register_user(client)
    wrong = login(client, u, "Wrong-Password-1")
    unknown = login(client, unique_username("nobody"), STRONG_PASSWORD)
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_five_failures_then_429_with_retry_after_then_success_after_wait(client):
    _, u, _ = register_user(client)
    for _ in range(5):
        assert login(client, u, "Wrong-Password-1").status_code == 401
    locked = login(client, u)  # even the right password is delayed now
    assert locked.status_code == 429 and int(locked.headers["Retry-After"]) >= 1
    with SessionLocal() as db:
        db.query(LoginAttempt).delete()  # simulate the wait having passed
        db.commit()
    assert login(client, u).status_code == 200


def test_deactivated_user_cannot_log_in_and_legacy_rows_cannot_either(client):
    _, u, _ = register_user(client)
    with SessionLocal() as db:
        db.query(User).filter_by(username=u).update({"is_active": False})
        db.commit()
    assert login(client, u).status_code == 403
    legacy = unique_username("client-")
    with SessionLocal() as db:
        db.add(User(username=legacy, display_name=legacy))  # password_hash NULL, like migrated client-id rows
        db.commit()
    assert login(client, legacy).status_code == 401


# ---------- refresh / logout ----------
def test_refresh_requires_cookie_header_and_origin(client):
    assert post_refresh(client, None).status_code == 401
    assert post_refresh(client, "garbage-token").status_code == 401
    token = refresh_cookie_value(client.post("/api/auth/register", json=body(unique_username())))
    client.cookies.clear()
    no_header = client.post("/api/auth/refresh", headers={"Cookie": f"{settings.refresh_cookie_name}={token}"})
    assert no_header.status_code == 403
    assert post_refresh(client, token, Origin="https://evil.example").status_code == 403
    ok = post_refresh(client, token, Origin="http://localhost:5173")
    assert ok.status_code == 200 and ok.json()["access_token"]
    assert refresh_cookie_value(ok) not in (None, token)


def test_two_tabs_refreshing_the_same_cookie_both_succeed(client):
    token = refresh_cookie_value(client.post("/api/auth/register", json=body(unique_username())))
    first, second = post_refresh(client, token), post_refresh(client, token)
    assert first.status_code == second.status_code == 200


def test_logout_revokes_the_session_and_is_idempotent(client):
    token = refresh_cookie_value(client.post("/api/auth/register", json=body(unique_username())))
    client.cookies.clear()
    out = client.post("/api/auth/logout", headers={**CSRF, "Cookie": f"{settings.refresh_cookie_name}={token}"})
    assert out.status_code == 204
    assert post_refresh(client, token).status_code == 401
    assert client.post("/api/auth/logout", headers=CSRF).status_code == 204  # no cookie: still fine


# ---------- recovery ----------
def recover(client, username, code, new="Brand-New-Pass-77"):
    return client.post("/api/auth/recover", json={
        "username": username, "recovery_code": code, "new_password": new, "confirm_password": new})


def test_recover_accepts_sloppy_code_rotates_it_and_revokes_sessions(client):
    reg = client.post("/api/auth/register", json=body(unique_username()))
    u, code, old_refresh = reg.json()["user"]["username"], reg.json()["recovery_code"], refresh_cookie_value(reg)
    res = recover(client, u, code.lower().replace("-", " "))
    assert res.status_code == 200
    new_code = res.json()["recovery_code"]
    assert new_code != code and res.json()["access_token"]
    assert login(client, u, "Brand-New-Pass-77").status_code == 200
    assert login(client, u, STRONG_PASSWORD).status_code == 401           # old password is dead
    assert recover(client, u, code).status_code == 401                     # old code is dead
    assert post_refresh(client, old_refresh).status_code == 401            # old sessions revoked


def test_recover_failure_is_indistinguishable_for_unknown_user(client):
    _, u, _ = register_user(client)
    wrong_code = recover(client, u, "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GG")
    unknown = recover(client, unique_username("ghost"), "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GG")
    assert wrong_code.status_code == unknown.status_code == 401
    assert wrong_code.json() == unknown.json()


def test_recover_refuses_deactivated_accounts(client):
    _, u, code = register_user(client)
    with SessionLocal() as db:
        db.query(User).filter_by(username=u).update({"is_active": False})
        db.commit()
    assert recover(client, u, code).status_code == 403


# ---------- me ----------
def test_me_requires_a_valid_bearer_token(client):
    headers, u, _ = register_user(client)
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["username"] == u and "password" not in me.text
