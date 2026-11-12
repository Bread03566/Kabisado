"""Regression tests for the final whole-branch review findings (C1, I2, I3, I4)."""
import concurrent.futures
import inspect
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app import cli
from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.models import Document, User
from app.routers import auth as auth_router
from tests.helpers import STRONG_PASSWORD, register_user, unique_username
from tests.test_api import make_doc


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---- C1: handlers must not block the event loop or hold a DB connection across a hash ----
def test_auth_handlers_run_in_the_threadpool_not_on_the_event_loop():
    for name in ("register", "login", "refresh", "logout", "recover", "me",
                 "change_password", "deactivate", "delete_account"):
        assert not inspect.iscoroutinefunction(getattr(auth_router, name)), name


def test_many_simultaneous_logins_all_complete(client):
    _, username, _ = register_user(client)

    def attempt(_):
        with TestClient(app) as c:
            return c.post("/api/auth/login", json={"username": username, "password": STRONG_PASSWORD}).status_code

    with concurrent.futures.ThreadPoolExecutor(12) as pool:
        codes = list(pool.map(attempt, range(12)))
    assert codes == [200] * 12


# ---- I2: registration is rate limited per client IP ----
def test_registration_is_rate_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY", True)
    monkeypatch.setattr(settings, "REGISTER_LIMIT_PER_HOUR", 3)
    ip = f"198.51.100.{uuid.uuid4().int % 250 + 1}"

    def reg():
        name = unique_username()
        return client.post("/api/auth/register", headers={"X-Forwarded-For": ip}, json={
            "display_name": "X", "username": name, "password": STRONG_PASSWORD, "confirm_password": STRONG_PASSWORD})

    assert [reg().status_code for _ in range(3)] == [201, 201, 201]
    blocked = reg()
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) >= 1
    other = client.post("/api/auth/register", headers={"X-Forwarded-For": "203.0.113.250"}, json={
        "display_name": "X", "username": unique_username(), "password": STRONG_PASSWORD, "confirm_password": STRONG_PASSWORD})
    assert other.status_code == 201  # a different IP is unaffected


# ---- I3: deleting an account removes the original uploaded files too ----
def test_delete_account_removes_uploaded_files_from_disk(client):
    headers, _, _ = register_user(client)
    client.headers.update(headers)
    try:
        doc = make_doc(client, title="With a file")
    finally:
        client.headers.pop("Authorization")
    path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}.txt")
    with open(path, "w") as f:
        f.write("original upload")
    with SessionLocal() as db:
        db.get(Document, doc["id"]).file_path = path
        db.commit()
    res = client.request("DELETE", "/api/auth/account", headers=headers, json={"password": STRONG_PASSWORD})
    assert res.status_code == 204
    assert not os.path.exists(path)


def test_delete_account_never_deletes_files_outside_the_upload_directory(client, tmp_path):
    headers, _, _ = register_user(client)
    outside = tmp_path / "precious.txt"
    outside.write_text("keep me")
    client.headers.update(headers)
    try:
        doc = make_doc(client, title="Bad path")
    finally:
        client.headers.pop("Authorization")
    with SessionLocal() as db:
        db.get(Document, doc["id"]).file_path = str(outside)
        db.commit()
    assert client.request("DELETE", "/api/auth/account", headers=headers, json={"password": STRONG_PASSWORD}).status_code == 204
    assert outside.exists()


# ---- I4: a deactivated account can be brought back by the owner ----
def test_cli_reactivate_lets_a_deactivated_student_log_in_again(client):
    headers, username, _ = register_user(client)
    assert client.post("/api/auth/deactivate", headers=headers, json={"password": STRONG_PASSWORD}).status_code == 204
    assert client.post("/api/auth/login", json={"username": username, "password": STRONG_PASSWORD}).status_code == 403
    with SessionLocal() as db:
        cli.reactivate(db, username.upper())
    assert client.post("/api/auth/login", json={"username": username, "password": STRONG_PASSWORD}).status_code == 200


def test_cli_reactivate_reports_unknown_users_and_main_wires_it(capsys):
    with SessionLocal() as db:
        with pytest.raises(cli.CliError, match="No user"):
            cli.reactivate(db, "nobody-" + uuid.uuid4().hex[:6])
    assert cli.main(["reactivate", "--username", "nobody-" + uuid.uuid4().hex[:6]]) == 1
    assert "No user" in capsys.readouterr().err
