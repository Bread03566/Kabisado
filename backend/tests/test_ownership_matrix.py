"""Every route is either public on purpose, or needs a login, and never lets one student touch another's data.

The test fails if a route is added that is not listed here, so new endpoints cannot silently skip these checks.
"""
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import register_user
from tests.test_api import make_doc

# Reachable without a token on purpose.
PUBLIC = {
    ("GET", "/"), ("GET", "/api/health"),
    ("POST", "/api/auth/register"), ("POST", "/api/auth/login"), ("POST", "/api/auth/refresh"),
    ("POST", "/api/auth/recover"), ("POST", "/api/auth/logout"),
}

# Routes that take no foreign ID: they only ever act on the caller's own rows.
SELF_SCOPED = {
    ("POST", "/api/documents/upload"), ("POST", "/api/documents/text"), ("GET", "/api/documents"),
    ("GET", "/api/flashcards/due"), ("GET", "/api/flags"), ("GET", "/api/progress/dashboard"),
    ("GET", "/api/auth/me"), ("POST", "/api/auth/password"), ("POST", "/api/auth/deactivate"),
    ("DELETE", "/api/auth/account"), ("GET", "/api/admin/ping"),
}


def cross_cases(ids):
    d, c, q, f = ids["doc"], ids["card"], ids["question"], ids["flag"]
    return {
        ("GET", "/api/documents/{document_id}"): (f"/api/documents/{d}", {}),
        ("DELETE", "/api/documents/{document_id}"): (f"/api/documents/{d}", {}),
        ("POST", "/api/documents/{document_id}/summarize"): (f"/api/documents/{d}/summarize", {"json": {"length": "brief"}}),
        ("POST", "/api/documents/{document_id}/chat"): (f"/api/documents/{d}/chat", {"json": {"question": "What is this?"}}),
        ("POST", "/api/documents/{document_id}/flashcards/generate"): (f"/api/documents/{d}/flashcards/generate", {"json": {"count": 2}}),
        ("GET", "/api/documents/{document_id}/flashcards"): (f"/api/documents/{d}/flashcards", {}),
        ("POST", "/api/flashcards"): ("/api/flashcards", {"json": {"document_id": d, "front": "x", "back": "y", "card_type": "term"}}),
        ("PUT", "/api/flashcards/{card_id}"): (f"/api/flashcards/{c}", {"json": {"front": "hacked"}}),
        ("DELETE", "/api/flashcards/{card_id}"): (f"/api/flashcards/{c}", {}),
        ("POST", "/api/flashcards/{card_id}/review"): (f"/api/flashcards/{c}/review", {"json": {"rating": "good"}}),
        ("POST", "/api/documents/{document_id}/quiz/generate"): (f"/api/documents/{d}/quiz/generate", {"json": {"count": 2}}),
        ("POST", "/api/documents/{document_id}/quiz/weak-spots"): (f"/api/documents/{d}/quiz/weak-spots", {}),
        ("GET", "/api/documents/{document_id}/questions"): (f"/api/documents/{d}/questions", {}),
        ("POST", "/api/quizzes/check"): ("/api/quizzes/check", {"json": {"question_id": q, "selected_index": 0}}),
        ("POST", "/api/quizzes/submit"): ("/api/quizzes/submit", {"json": {"document_id": d, "answers": [{"question_id": q, "selected_index": 0}]}}),
        ("POST", "/api/flags"): ("/api/flags", {"json": {"target_type": "flashcard", "target_id": c, "reason": "wrong"}}),
    }


def route_keys():
    keys = set()
    for r in app.routes:
        if isinstance(r, APIRoute):
            keys |= {(m, r.path) for m in r.methods if m not in ("HEAD", "OPTIONS")}
    return keys


def test_every_route_is_classified():
    ids = {"doc": 1, "card": 1, "question": 1, "flag": 1}
    known = PUBLIC | SELF_SCOPED | set(cross_cases(ids))
    unclassified = route_keys() - known
    assert not unclassified, f"New routes need an ownership/anonymous test entry: {sorted(unclassified)}"


def concrete(path: str) -> str:
    for name in ("document_id", "card_id", "question_id", "topic_id"):
        path = path.replace("{" + name + "}", "1")
    return path


def test_every_non_public_route_rejects_anonymous_requests():
    with TestClient(app) as anon:
        for method, path in sorted(route_keys() - PUBLIC):
            res = anon.request(method, concrete(path), json={})
            assert res.status_code == 401, (method, path, res.status_code)


@pytest.fixture(scope="module")
def world():
    with TestClient(app) as c:
        alice_h, _, _ = register_user(c)
        bob_h, _, _ = register_user(c)
        c.headers.update(alice_h)
        doc = make_doc(c, title="Alice private notes")
        card = c.post("/api/flashcards", json={"document_id": doc["id"], "front": "Q", "back": "A", "card_type": "term"}).json()
        question = c.post(f"/api/documents/{doc['id']}/quiz/generate", json={"count": 2}).json()[0]
        flag = c.post("/api/flags", json={"target_type": "flashcard", "target_id": card["id"], "reason": "wrong"}).json()
        c.headers.pop("Authorization")
        snapshot = {
            "docs": c.get("/api/documents", headers=alice_h).json(),
            "cards": c.get(f"/api/documents/{doc['id']}/flashcards", headers=alice_h).json(),
            "questions": c.get(f"/api/documents/{doc['id']}/questions", headers=alice_h).json(),
        }
        yield c, alice_h, bob_h, {"doc": doc["id"], "card": card["id"], "question": question["id"], "flag": flag["id"]}, snapshot


def test_bob_cannot_touch_alices_data_through_any_route(world):
    client, alice_h, bob_h, ids, snapshot = world
    for (method, template), (path, kwargs) in cross_cases(ids).items():
        res = client.request(method, path, headers=bob_h, **kwargs)
        assert res.status_code == 404, (method, template, res.status_code, res.text)

    # Routes that return the caller's own rows must simply not contain Alice's.
    assert ids["doc"] not in [d["id"] for d in client.get("/api/documents", headers=bob_h).json()]
    assert client.get(f"/api/flashcards/due?document_id={ids['doc']}", headers=bob_h).json() == []
    assert ids["flag"] not in [f["id"] for f in client.get("/api/flags", headers=bob_h).json()]
    assert client.get("/api/progress/dashboard", headers=bob_h).json()["total_cards"] == 0
    assert client.get(f"/api/progress/dashboard?document_id={ids['doc']}", headers=bob_h).status_code == 404

    # ...and Alice's data is exactly as she left it.
    assert client.get("/api/documents", headers=alice_h).json() == snapshot["docs"]
    assert client.get(f"/api/documents/{ids['doc']}/flashcards", headers=alice_h).json() == snapshot["cards"]
    assert client.get(f"/api/documents/{ids['doc']}/questions", headers=alice_h).json() == snapshot["questions"]
