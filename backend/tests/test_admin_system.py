import datetime

import pytest
from fastapi.testclient import TestClient

from app import cli
from app.database import SessionLocal
from app.main import app
from app.models.models import AiUsage, Document, SystemStatus, User
from app.services import system_status
from tests.helpers import STRONG_PASSWORD, register_user, unique_username


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin(client):
    with SessionLocal() as db:
        name = unique_username("adm")
        cli.create_admin(db, name, "Admin", STRONG_PASSWORD)
    tok = client.post("/api/auth/login", json={"username": name, "password": STRONG_PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def clear_backup():
    with SessionLocal() as db:
        db.query(SystemStatus).filter_by(key="last_backup").delete()
        db.commit()


def test_system_panel_is_admin_only(client):
    headers, _, _ = register_user(client)
    assert client.get("/api/admin/system").status_code == 401
    assert client.get("/api/admin/system", headers=headers).status_code == 403


def test_system_panel_reports_usage_and_has_no_secrets(client, admin):
    body = client.get("/api/admin/system", headers=admin).json()
    assert set(body) == {"database", "text_storage", "ai", "backup", "version"}
    assert body["text_storage"]["budget_mb"] > 0 and body["text_storage"]["used_mb"] >= 0
    assert set(body["ai"]) == {"enabled", "calls_today", "global_daily_limit", "consenting_students"}
    assert body["ai"]["enabled"] is False
    assert "DATABASE_URL" not in str(body) and "postgres" not in str(body).lower().replace("postgresql", "")


def test_text_storage_and_ai_calls_are_counted(client, admin):
    before = client.get("/api/admin/system", headers=admin).json()
    h, _, _ = register_user(client)
    uid = client.get("/api/auth/me", headers=h).json()["public_id"]
    with SessionLocal() as db:
        owner = db.query(User).filter_by(public_id=uid).one()
        db.add(Document(user_id=owner.id, title="t", file_type="text", raw_text="x" * 200_000))
        db.add(AiUsage(user_id=owner.id, feature="summary", engine="gemini"))
        db.commit()
    after = client.get("/api/admin/system", headers=admin).json()
    assert after["text_storage"]["used_mb"] > before["text_storage"]["used_mb"]
    assert after["ai"]["calls_today"] == before["ai"]["calls_today"] + 1


def test_no_recorded_backup_is_a_warning(client, admin):
    clear_backup()
    backup = client.get("/api/admin/system", headers=admin).json()["backup"]
    assert backup["last_at"] is None and backup["warning"] is True and "no backup" in backup["message"].lower()


def test_fresh_backup_is_fine_and_an_old_one_warns(client, admin):
    with SessionLocal() as db:
        system_status.record(db, "last_backup", "ok")
    fresh = client.get("/api/admin/system", headers=admin).json()["backup"]
    assert fresh["warning"] is False and fresh["age_hours"] < 1
    with SessionLocal() as db:
        row = db.get(SystemStatus, "last_backup")
        row.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=40)
        db.commit()
    old = client.get("/api/admin/system", headers=admin).json()["backup"]
    assert old["warning"] is True and old["age_hours"] > 36
