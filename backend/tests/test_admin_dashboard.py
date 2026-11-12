import pytest
from fastapi.testclient import TestClient

from app import cli
from app.database import SessionLocal
from app.main import app
from app.models.models import AuditLog, Document, User
from tests.helpers import STRONG_PASSWORD, post_refresh, register_user, unique_username


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def admin(client, db):
    username = unique_username("adm")
    cli.create_admin(db, username, "Site Admin", STRONG_PASSWORD)
    res = client.post("/api/auth/login", json={"username": username, "password": STRONG_PASSWORD})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}, username, res.json()["user"]


def _public_id(client, headers):
    return client.get("/api/auth/me", headers=headers).json()["public_id"]


def test_every_dashboard_route_is_admin_only(client):
    student, _, _ = register_user(client)
    calls = [("get", "/api/admin/overview"), ("get", "/api/admin/students"), ("get", "/api/admin/audit"),
             ("post", "/api/admin/students/abc/deactivate"), ("post", "/api/admin/students/abc/reactivate")]
    for method, url in calls:
        assert getattr(client, method)(url).status_code == 401, url
        assert getattr(client, method)(url, headers=student).status_code == 403, url


def test_overview_counts_students_and_content(client, db, admin):
    headers, _, _ = admin
    before = client.get("/api/admin/overview", headers=headers).json()
    s_headers, _, _ = register_user(client)
    sid = db.query(User).filter_by(public_id=_public_id(client, s_headers)).one().id
    db.add(Document(user_id=sid, title="t", file_type="text", raw_text="x"))
    db.commit()
    after = client.get("/api/admin/overview", headers=headers).json()
    assert after["students"] == before["students"] + 1
    assert after["active_students"] == before["active_students"] + 1
    assert after["documents"] == before["documents"] + 1
    assert after["admins"] >= 1
    assert set(after) >= {"students", "active_students", "disabled_students", "admins", "documents",
                          "flashcards", "questions", "quiz_attempts"}


def test_student_list_shows_metadata_only_and_supports_search(client, admin):
    headers, _, _ = admin
    name = unique_username("findme")
    register_user(client, username=name, display_name="Zed Searchable")
    rows = client.get("/api/admin/students", params={"q": name[:-2]}, headers=headers).json()["students"]
    assert [r["username"] for r in rows] == [name]
    row = rows[0]
    assert set(row) == {"id", "username", "display_name", "role", "is_active", "created_at",
                        "last_login_at", "document_count"}
    by_display = client.get("/api/admin/students", params={"q": "zed searchable"}, headers=headers).json()["students"]
    assert name in [r["username"] for r in by_display]
    assert client.get("/api/admin/students", params={"q": "no-such-person-xyz"}, headers=headers).json()["students"] == []


def test_deactivate_blocks_login_and_kills_sessions_and_reactivate_restores(client, db, admin):
    headers, admin_name, _ = admin
    s_headers, s_name, _ = register_user(client)
    pid = _public_id(client, s_headers)

    assert client.post(f"/api/admin/students/{pid}/deactivate", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=s_headers).status_code in (401, 403)
    assert client.post("/api/auth/login", json={"username": s_name, "password": STRONG_PASSWORD}).status_code == 403

    assert client.post(f"/api/admin/students/{pid}/reactivate", headers=headers).status_code == 204
    assert client.post("/api/auth/login", json={"username": s_name, "password": STRONG_PASSWORD}).status_code == 200


def test_admin_cannot_deactivate_themselves_or_another_admin_or_unknown_ids(client, db, admin):
    headers, _, me = admin
    assert client.post(f"/api/admin/students/{me['public_id']}/deactivate", headers=headers).status_code == 400
    other = unique_username("adm")
    cli.create_admin(db, other, "Other Admin", STRONG_PASSWORD)
    other_pid = db.query(User).filter_by(username=other).one().public_id
    assert client.post(f"/api/admin/students/{other_pid}/deactivate", headers=headers).status_code == 400
    assert client.post("/api/admin/students/does-not-exist/deactivate", headers=headers).status_code == 404
    assert client.post("/api/admin/students/does-not-exist/reactivate", headers=headers).status_code == 404


def test_admin_writes_are_audited_without_secrets(client, db, admin):
    headers, admin_name, _ = admin
    s_headers, s_name, _ = register_user(client)
    pid = _public_id(client, s_headers)
    client.post(f"/api/admin/students/{pid}/deactivate", headers=headers)
    client.post(f"/api/admin/students/{pid}/reactivate", headers=headers)
    entries = client.get("/api/admin/audit", headers=headers).json()["entries"]
    actions = [e["action"] for e in entries[:2]]
    assert actions == ["student.reactivate", "student.deactivate"]  # newest first
    assert entries[0]["target"] == pid and entries[0]["actor"] == admin_name
    assert set(entries[0]) == {"id", "action", "actor", "target", "created_at"}
    assert db.query(AuditLog).count() >= 2


def test_deactivated_students_old_refresh_cookie_stops_working(client, db, admin):
    headers, _, _ = admin
    res = client.post("/api/auth/register", json={
        "display_name": "Cookie Kid", "username": unique_username(), "password": STRONG_PASSWORD,
        "confirm_password": STRONG_PASSWORD})
    pid = res.json()["user"]["public_id"]
    token = next(v for k, v in client.cookies.items() if k.endswith("kabisado_rt"))
    assert client.post(f"/api/admin/students/{pid}/deactivate", headers=headers).status_code == 204
    assert post_refresh(client, token).status_code == 401
