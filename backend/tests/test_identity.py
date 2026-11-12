import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.identity import require_admin, require_student
from app.main import app
from app.models.models import User, UserSession
from app.security.sessions import revoke_all_for_user
from tests.helpers import register_user


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def set_user(username, **fields):
    with SessionLocal() as db:
        db.query(User).filter_by(username=username).update(fields)
        db.commit()


def test_no_header_is_401_not_a_fresh_identity(client):
    res = client.get("/api/documents")
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


def test_garbage_and_malformed_tokens_are_401(client):
    for header in ("Bearer nope", "Bearer ", "Basic abc", "bearer", "Token abc"):
        assert client.get("/api/documents", headers={"Authorization": header}).status_code == 401, header


def test_valid_token_reaches_the_route(client):
    headers, _, _ = register_user(client)
    assert client.get("/api/documents", headers=headers).status_code == 200


def test_old_client_id_header_alone_is_not_an_identity(client):
    res = client.get("/api/documents", headers={"X-Client-Id": "alice-0123456789abcdef"})
    assert res.status_code == 401
    with SessionLocal() as db:
        assert db.query(User).filter(User.username == "client-alice-0123456789abcdef").count() == 0


def test_deactivating_a_user_kills_their_unexpired_token(client):
    headers, username, _ = register_user(client)
    assert client.get("/api/documents", headers=headers).status_code == 200
    set_user(username, is_active=False)
    assert client.get("/api/documents", headers=headers).status_code == 401


def test_revoking_the_session_kills_the_access_token(client):
    headers, username, _ = register_user(client)
    with SessionLocal() as db:
        revoke_all_for_user(db, db.query(User).filter_by(username=username).one().id)
    assert client.get("/api/documents", headers=headers).status_code == 401


def test_role_guards_read_the_role_from_the_database_not_the_token(client):
    probe = FastAPI()

    @probe.get("/admin-only")
    def admin_only(user: User = Depends(require_admin)):
        return {"u": user.username}

    @probe.get("/student-only")
    def student_only(user: User = Depends(require_student)):
        return {"u": user.username}

    headers, username, _ = register_user(client)
    with TestClient(probe) as p:
        assert p.get("/admin-only").status_code == 401
        assert p.get("/admin-only", headers=headers).status_code == 403
        assert p.get("/student-only", headers=headers).status_code == 200
        set_user(username, role="admin")  # same token, new role
        assert p.get("/admin-only", headers=headers).status_code == 200
        assert p.get("/student-only", headers=headers).status_code == 403
