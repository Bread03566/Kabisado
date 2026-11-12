import asyncio
import pathlib
import types

import pytest
from fastapi.testclient import TestClient

from app import cli
from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.models import ConsentLog, User
from app.services import consent
from app.services.ai_service import AIService
from tests.helpers import STRONG_PASSWORD, register_user, unique_username

TEXT = (
    "Photosynthesis is the process by which plants convert light energy into chemical energy. "
    "Chlorophyll is the green pigment that absorbs sunlight. "
    "Glucose is the sugar produced during photosynthesis."
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def gemini_on(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_ENABLED", True)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "real-looking-key")


def uid_of(client, headers):
    pid = client.get("/api/auth/me", headers=headers).json()["public_id"]
    with SessionLocal() as db:
        return db.query(User).filter_by(public_id=pid).one().id


GRANT = {"confirm_adult": True, "accept_disclosure": True, "policy_version": consent.CURRENT_POLICY_VERSION}


# ---------------- the consent API ----------------
def test_consent_status_starts_off_and_says_gemini_is_unavailable_when_the_switch_is_off(client):
    headers, _, _ = register_user(client)
    body = client.get("/api/consent", headers=headers).json()
    assert body["gemini_available"] is False and body["consent"] is False
    assert body["policy_version"] == consent.CURRENT_POLICY_VERSION


def test_cannot_consent_while_the_site_has_gemini_switched_off(client):
    headers, _, _ = register_user(client)
    assert client.post("/api/consent/gemini", headers=headers, json=GRANT).status_code == 409


def test_consent_needs_login(client):
    assert client.get("/api/consent").status_code == 401
    assert client.post("/api/consent/gemini", json=GRANT).status_code == 401
    assert client.delete("/api/consent/gemini").status_code == 401


def test_consent_requires_both_confirmations_and_the_current_policy_version(client, gemini_on):
    headers, _, _ = register_user(client)
    for bad in ({**GRANT, "confirm_adult": False}, {**GRANT, "accept_disclosure": False},
                {**GRANT, "policy_version": "0"}):
        assert client.post("/api/consent/gemini", headers=headers, json=bad).status_code in (400, 422)
    assert client.get("/api/consent", headers=headers).json()["consent"] is False


def test_grant_then_withdraw_is_logged_and_takes_effect_immediately(client, gemini_on):
    headers, _, _ = register_user(client)
    uid = uid_of(client, headers)
    assert client.get("/api/consent", headers=headers).json()["gemini_available"] is True
    assert client.post("/api/consent/gemini", headers=headers, json=GRANT).status_code == 200
    assert client.get("/api/consent", headers=headers).json()["consent"] is True
    assert consent.authorize(uid) is True
    assert client.delete("/api/consent/gemini", headers=headers).status_code == 204
    assert client.get("/api/consent", headers=headers).json()["consent"] is False
    assert consent.authorize(uid) is False
    with SessionLocal() as db:
        events = [r.event for r in db.query(ConsentLog).filter_by(user_id=uid).order_by(ConsentLog.id)]
    assert events == ["grant", "withdraw"]


def test_consent_log_is_a_hash_chain_that_detects_tampering(client, gemini_on):
    headers, _, _ = register_user(client)
    uid = uid_of(client, headers)
    client.post("/api/consent/gemini", headers=headers, json=GRANT)
    client.delete("/api/consent/gemini", headers=headers)
    client.post("/api/consent/gemini", headers=headers, json=GRANT)
    with SessionLocal() as db:
        assert consent.verify_chain(db, uid) == []
        first = db.query(ConsentLog).filter_by(user_id=uid).order_by(ConsentLog.id).first()
        first.event = "withdraw"  # someone edits history
        db.commit()
        problems = consent.verify_chain(db, uid)
    assert problems and str(first.id) in problems[0]


def test_consent_and_its_log_are_deleted_with_the_account(client, gemini_on):
    headers, _, _ = register_user(client)
    uid = uid_of(client, headers)
    client.post("/api/consent/gemini", headers=headers, json=GRANT)
    res = client.request("DELETE", "/api/auth/account", headers={**headers, "Origin": "http://localhost:5173",
                         "X-Kabisado-Request": "1"}, json={"password": STRONG_PASSWORD})
    assert res.status_code == 204, res.text
    with SessionLocal() as db:
        assert db.query(ConsentLog).filter_by(user_id=uid).count() == 0


def test_admin_overview_shows_only_the_number_of_consenting_students(client, gemini_on):
    with SessionLocal() as db:
        name = unique_username("adm")
        cli.create_admin(db, name, "A", STRONG_PASSWORD)
    admin = client.post("/api/auth/login", json={"username": name, "password": STRONG_PASSWORD}).json()["access_token"]
    ah = {"Authorization": f"Bearer {admin}"}
    before = client.get("/api/admin/overview", headers=ah).json()["gemini_consents"]
    headers, _, _ = register_user(client)
    client.post("/api/consent/gemini", headers=headers, json=GRANT)
    assert client.get("/api/admin/overview", headers=ah).json()["gemini_consents"] == before + 1


# ---------------- the gate ----------------
def test_gate_refuses_everyone_it_cannot_identify_or_whose_conditions_fail(client, gemini_on, monkeypatch):
    headers, _, _ = register_user(client)
    uid = uid_of(client, headers)
    assert consent.authorize(None) is False and consent.authorize(999999) is False
    assert consent.authorize(uid) is False  # no consent yet
    client.post("/api/consent/gemini", headers=headers, json=GRANT)
    assert consent.authorize(uid) is True

    monkeypatch.setattr(consent, "CURRENT_POLICY_VERSION", "2")  # policy changed: consent lapses until re-accepted
    assert consent.authorize(uid) is False
    monkeypatch.undo()

    with SessionLocal() as db:
        db.query(User).filter_by(id=uid).update({"is_active": False})
        db.commit()
    assert consent.authorize(uid) is False
    with SessionLocal() as db:
        db.query(User).filter_by(id=uid).update({"is_active": True, "age_band": None})
        db.commit()
    assert consent.authorize(uid) is False  # age confirmation missing


def test_gate_is_closed_when_the_global_switch_is_off(client, gemini_on, monkeypatch):
    headers, _, _ = register_user(client)
    uid = uid_of(client, headers)
    client.post("/api/consent/gemini", headers=headers, json=GRANT)
    monkeypatch.setattr(settings, "GEMINI_ENABLED", False)
    assert consent.authorize(uid) is False


def test_daily_budget_is_enforced_per_student_and_globally(client, gemini_on, monkeypatch):
    a, _, _ = register_user(client)
    b, _, _ = register_user(client)
    ua, ub = uid_of(client, a), uid_of(client, b)
    for h in (a, b):
        client.post("/api/consent/gemini", headers=h, json=GRANT)
    monkeypatch.setattr(settings, "GEMINI_USER_DAILY_CALLS", 2)
    assert [consent.reserve_gemini_call(ua, "summary") for _ in range(3)] == [True, True, False]
    assert consent.reserve_gemini_call(ub, "summary") is True  # another student is unaffected
    monkeypatch.setattr(settings, "GEMINI_GLOBAL_DAILY_CALLS", 1)
    assert consent.reserve_gemini_call(ub, "summary") is False


# ---------------- real traffic goes through the gate ----------------
class FakeGemini:
    """Stands in for the Google client. Records every request that would have left the server."""

    def __init__(self, reply='{"summary": "S", "key_terms": []}', on_call=None):
        self.calls = 0
        self.reply, self.on_call = reply, on_call
        self.aio = types.SimpleNamespace(models=types.SimpleNamespace(generate_content=self._call))

    async def _call(self, **kwargs):
        self.calls += 1
        if self.on_call:
            self.on_call(self.calls)
        return types.SimpleNamespace(text=self.reply)


def service(fake):
    svc = AIService()
    svc.client = fake
    return svc


def test_no_consent_means_zero_requests_leave_the_server(client, gemini_on):
    headers, _, _ = register_user(client)
    uid = uid_of(client, headers)
    fake = FakeGemini()
    svc = service(fake)
    out = asyncio.run(svc.generate_summary("Bio", TEXT, "brief", user_id=uid))
    asyncio.run(svc.generate_flashcards("Bio", "T", TEXT, topic_id=1, count=2, user_id=uid))
    asyncio.run(svc.generate_quiz_questions("Bio", "T", TEXT, topic_id=1, count=2, user_id=uid))
    asyncio.run(svc.answer_document_question("Bio", [{"id": 1, "title": "T", "content": TEXT}], "What?", user_id=uid))
    assert fake.calls == 0 and out["summary"]
    # and a caller that forgets to say who is asking is treated as "no consent"
    asyncio.run(svc.generate_summary("Bio", TEXT, "brief"))
    assert fake.calls == 0


def test_with_consent_the_request_is_sent_and_recorded_in_usage(client, gemini_on):
    headers, _, _ = register_user(client)
    uid = uid_of(client, headers)
    client.post("/api/consent/gemini", headers=headers, json=GRANT)
    fake = FakeGemini()
    out = asyncio.run(service(fake).generate_summary("Bio", TEXT, "brief", user_id=uid))
    assert fake.calls == 1 and out["summary"] == "S"
    with SessionLocal() as db:
        from app.models.models import AiUsage
        rows = db.query(AiUsage).filter_by(user_id=uid).all()
    assert len(rows) == 1 and rows[0].engine == "gemini" and rows[0].feature == "summary"


def test_withdrawing_between_a_call_and_its_retry_stops_the_retry(client, gemini_on):
    headers, _, _ = register_user(client)
    uid = uid_of(client, headers)
    client.post("/api/consent/gemini", headers=headers, json=GRANT)

    def withdraw_after_first(n):
        if n == 1:
            client.delete("/api/consent/gemini", headers=headers)

    fake = FakeGemini(reply="not json at all", on_call=withdraw_after_first)  # invalid JSON forces a retry
    out = asyncio.run(service(fake).generate_summary("Bio", TEXT, "brief", user_id=uid))
    assert fake.calls == 1  # the retry and the fallback model never went out
    assert out["summary"]   # the student still gets the offline summary


# ---------------- structure ----------------
def test_only_the_ai_service_talks_to_google():
    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    offenders = [str(p.relative_to(root)) for p in root.rglob("*.py")
                 if p.name != "ai_service.py" and ("google.genai" in p.read_text(encoding="utf-8")
                                                   or "from google import" in p.read_text(encoding="utf-8"))]
    assert offenders == []
