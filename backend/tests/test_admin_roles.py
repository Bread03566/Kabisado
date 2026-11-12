import pytest
from fastapi.testclient import TestClient

from app import cli
from app.database import SessionLocal
from app.main import app
from app.models.models import User
from tests.helpers import STRONG_PASSWORD, register_user, unique_username


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def test_student_and_anonymous_cannot_reach_admin_routes(client):
    headers, _, _ = register_user(client)
    assert client.get("/api/admin/ping").status_code == 401
    assert client.get("/api/admin/ping", headers=headers).status_code == 403


def test_cli_created_admin_can_log_in_and_reach_admin_routes(client, db):
    username = unique_username("adm")
    code = cli.create_admin(db, username, "Site Admin", STRONG_PASSWORD)
    assert len(code.replace("-", "")) == 26
    row = db.query(User).filter_by(username=username).one()
    assert row.role == "admin" and row.is_active and row.recovery_hash and row.password_hash != STRONG_PASSWORD
    res = client.post("/api/auth/login", json={"username": username, "password": STRONG_PASSWORD})
    assert res.status_code == 200 and res.json()["user"]["role"] == "admin"
    token = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert client.get("/api/admin/ping", headers=token).json() == {"ok": True}


def test_create_admin_refuses_an_existing_username(db):
    username = unique_username("adm")
    cli.create_admin(db, username, "A", STRONG_PASSWORD)
    with pytest.raises(cli.CliError, match="already exists"):
        cli.create_admin(db, username.upper(), "B", STRONG_PASSWORD)


def test_create_admin_applies_the_same_username_and_password_rules(db):
    with pytest.raises(cli.CliError):
        cli.create_admin(db, "no spaces allowed", "A", STRONG_PASSWORD)
    with pytest.raises(cli.CliError):
        cli.create_admin(db, unique_username("adm"), "A", "short")


def test_public_registration_can_never_produce_an_admin(client):
    res = client.post("/api/auth/register", json={
        "display_name": "Sneaky", "username": unique_username(), "password": STRONG_PASSWORD,
        "confirm_password": STRONG_PASSWORD, "role": "admin"})
    assert res.status_code == 422
    headers, username, _ = register_user(client)
    assert client.get("/api/auth/me", headers=headers).json()["role"] == "student"


def test_purge_legacy_removes_only_passwordless_users(client, db):
    legacy = unique_username("client-")
    db.add(User(username=legacy, display_name=legacy))
    db.commit()
    _, real, _ = register_user(client)
    assert cli.purge_legacy(db) >= 1
    assert db.query(User).filter_by(username=legacy).first() is None
    assert db.query(User).filter_by(username=real).first() is not None


def test_cli_main_creates_an_admin_and_prints_the_code_once(monkeypatch, capsys, db):
    username = unique_username("adm")
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": STRONG_PASSWORD)
    assert cli.main(["create-admin", "--username", username]) == 0
    out = capsys.readouterr().out
    assert "recovery code" in out and username not in out.split("code")[-1]
    assert db.query(User).filter_by(username=username).one().role == "admin"


def test_cli_main_rejects_mismatched_passwords(monkeypatch, capsys):
    answers = iter([STRONG_PASSWORD, "something-else-123"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(answers))
    assert cli.main(["create-admin", "--username", unique_username("adm")]) == 1
    assert "do not match" in capsys.readouterr().err


def test_cli_purge_needs_explicit_confirmation(db, capsys):
    legacy = unique_username("client-")
    db.add(User(username=legacy, display_name=legacy))
    db.commit()
    assert cli.main(["purge-legacy"]) == 1
    assert db.query(User).filter_by(username=legacy).first() is not None   # untouched without --yes
    assert cli.main(["purge-legacy", "--yes"]) == 0
    db.expire_all()
    assert db.query(User).filter_by(username=legacy).first() is None
