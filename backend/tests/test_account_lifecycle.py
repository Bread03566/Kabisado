import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.models import Document, Flag, Flashcard, Question, QuizAttempt, Topic, User, UserSession
from tests.helpers import STRONG_PASSWORD, post_refresh, refresh_cookie_value, register_user, unique_username
from tests.test_api import make_doc

NEW_PASSWORD = "Another-Strong-Pass-42"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def change(client, headers, current=STRONG_PASSWORD, new=NEW_PASSWORD, confirm=None):
    return client.post("/api/auth/password", headers=headers, json={
        "current_password": current, "new_password": new, "confirm_password": confirm or new})


def with_password(client, method, path, headers, password):
    return client.request(method, path, headers=headers, json={"password": password})


# ---------- change password ----------
def test_change_password_needs_the_current_password(client):
    headers, _, _ = register_user(client)
    res = change(client, headers, current="Not-The-Password-1")
    assert res.status_code == 403            # 403 not 401, so the app does not mistake it for an expired session
    assert client.get("/api/auth/me", headers=headers).status_code == 200


def test_change_password_validates_the_new_password(client):
    headers, _, _ = register_user(client)
    assert change(client, headers, new="short").status_code == 422
    assert change(client, headers, confirm="Mismatch-Strong-Pass-1").status_code == 422
    assert change(client, headers, new="password123").status_code == 422


def test_change_password_signs_out_other_sessions_but_keeps_this_one(client):
    headers, username, _ = register_user(client)
    other = login(client, username, STRONG_PASSWORD)          # a second device
    other_refresh = refresh_cookie_value(other)
    assert change(client, headers).status_code == 204
    assert post_refresh(client, other_refresh).status_code == 401
    assert client.get("/api/auth/me", headers=headers).status_code == 200      # current session survives
    assert login(client, username, STRONG_PASSWORD).status_code == 401
    assert login(client, username, NEW_PASSWORD).status_code == 200


def test_password_confirmation_endpoints_are_throttled(client):
    headers, _, _ = register_user(client)
    for _ in range(5):
        assert change(client, headers, current="Wrong-Password-1").status_code == 403
    res = change(client, headers, current=STRONG_PASSWORD)
    assert res.status_code == 429 and int(res.headers["Retry-After"]) >= 1


# ---------- deactivate ----------
def test_deactivate_needs_the_password_then_locks_the_account(client):
    headers, username, code = register_user(client)
    other_headers, other_name, _ = register_user(client)
    assert with_password(client, "POST", "/api/auth/deactivate", headers, "wrong-Password-1").status_code == 403
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert with_password(client, "POST", "/api/auth/deactivate", headers, STRONG_PASSWORD).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert login(client, username, STRONG_PASSWORD).status_code == 403
    assert client.get("/api/auth/me", headers=other_headers).status_code == 200   # others unaffected


# ---------- delete ----------
def test_delete_account_removes_everything_the_student_owned(client):
    headers, username, _ = register_user(client)
    other_headers, _, _ = register_user(client)

    client.headers.update(headers)
    doc = make_doc(client, title="Mine")
    card = client.post("/api/flashcards", json={"document_id": doc["id"], "front": "Q", "back": "A", "card_type": "term"}).json()
    questions = client.post(f"/api/documents/{doc['id']}/quiz/generate", json={"count": 2}).json()
    attempt = client.post("/api/quizzes/submit", json={
        "document_id": doc["id"],
        "answers": [{"question_id": q["id"], "selected_index": q["correct_index"]} for q in questions]}).json()
    flag = client.post("/api/flags", json={"target_type": "flashcard", "target_id": card["id"], "reason": "wrong"}).json()
    client.headers.pop("Authorization")

    mine = make_doc_for(client, other_headers, "Theirs")

    assert with_password(client, "DELETE", "/api/auth/account", headers, "wrong-Password-1").status_code == 403
    assert with_password(client, "DELETE", "/api/auth/account", headers, STRONG_PASSWORD).status_code == 204

    with SessionLocal() as db:
        assert db.query(User).filter_by(username=username).first() is None
        assert db.get(Document, doc["id"]) is None
        assert db.query(Topic).filter(Topic.document_id == doc["id"]).count() == 0
        assert db.get(Flashcard, card["id"]) is None
        assert db.query(Question).filter(Question.document_id == doc["id"]).count() == 0
        assert db.query(QuizAttempt).filter(QuizAttempt.document_id == doc["id"]).count() == 0
        assert db.get(Flag, flag["id"]) is None
        assert db.query(UserSession).join(User, isouter=True).filter(User.id.is_(None)).count() == 0
        assert db.get(Document, mine["id"]) is not None            # the other student's data is intact
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert login(client, username, STRONG_PASSWORD).status_code == 401
    assert client.get(f"/api/documents/{mine['id']}", headers=other_headers).status_code == 200


def make_doc_for(client, headers, title):
    client.headers.update(headers)
    try:
        return make_doc(client, title=title)
    finally:
        client.headers.pop("Authorization")
