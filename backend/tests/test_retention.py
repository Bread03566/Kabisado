import datetime

import pytest
from fastapi.testclient import TestClient

from app import cli
from app.database import SessionLocal
from app.main import app
from app.models.models import LoginAttempt, User, UserSession
from app.security import retention
from tests.helpers import register_user

NOW = datetime.datetime(2026, 11, 12, 12, 0, 0)
DAY = datetime.timedelta(days=1)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def make_user(db, username):
    u = User(username=username, display_name=username)
    db.add(u)
    db.commit()
    return u


def make_session(db, user, token, **fields):
    row = dict(user_id=user.id, family_id=token, refresh_hash=token, created_at=NOW - 40 * DAY,
               expires_at=NOW - 33 * DAY)
    row.update(fields)
    s = UserSession(**row)
    db.add(s)
    db.commit()
    return s.id


def test_purge_removes_session_metadata_older_than_30_days_and_keeps_the_rest(db):
    u = make_user(db, "ret-owner-1")
    old_expired = make_session(db, u, "t-old-expired")
    old_revoked = make_session(db, u, "t-old-revoked", revoked_at=NOW - 31 * DAY, expires_at=NOW + 2 * DAY)
    old_rotated = make_session(db, u, "t-old-rotated", rotated_at=NOW - 35 * DAY, expires_at=NOW + 2 * DAY)
    recent_expired = make_session(db, u, "t-recent-expired", created_at=NOW - 10 * DAY, expires_at=NOW - 3 * DAY)
    live = make_session(db, u, "t-live", created_at=NOW - DAY, expires_at=NOW + 6 * DAY)
    recently_revoked = make_session(db, u, "t-recently-revoked", created_at=NOW - 2 * DAY,
                                    expires_at=NOW + 5 * DAY, revoked_at=NOW - DAY)

    removed = retention.purge_expired(db, now=NOW)

    kept = {s.id for s in db.query(UserSession).filter(UserSession.user_id == u.id)}
    assert kept == {recent_expired, live, recently_revoked}
    assert removed["sessions"] >= 3
    assert not ({old_expired, old_revoked, old_rotated} & kept)


def test_purge_removes_stale_login_attempts_but_not_active_lockouts(db):
    stale = LoginAttempt(key="ret-stale", count=3, window_start=NOW - 40 * DAY)
    old_but_locked = LoginAttempt(key="ret-locked", count=9, window_start=NOW - 40 * DAY, locked_until=NOW + DAY)
    fresh = LoginAttempt(key="ret-fresh", count=1, window_start=NOW - DAY)
    db.add_all([stale, old_but_locked, fresh])
    db.commit()
    removed = retention.purge_expired(db, now=NOW)
    keys = {a.key for a in db.query(LoginAttempt).filter(LoginAttempt.key.like("ret-%"))}
    assert keys == {"ret-locked", "ret-fresh"}
    assert removed["login_attempts"] >= 1


def test_purge_never_touches_users_or_their_documents(db):
    u = make_user(db, "ret-owner-2")
    make_session(db, u, "t-x")
    retention.purge_expired(db, now=NOW)
    assert db.query(User).filter_by(username="ret-owner-2").first() is not None


def test_cli_purge_expired_reports_counts(db, capsys):
    u = make_user(db, "ret-owner-3")
    make_session(db, u, "t-cli", created_at=datetime.datetime(2000, 1, 1), expires_at=datetime.datetime(2000, 1, 8))
    assert cli.main(["purge-expired"]) == 0
    assert "session" in capsys.readouterr().out
    assert db.query(UserSession).filter_by(refresh_hash="t-cli").first() is None


def test_app_startup_purges_and_a_purge_failure_never_blocks_startup(monkeypatch):
    calls = []
    monkeypatch.setattr(retention, "purge_expired", lambda db, now=None: calls.append(1) or {"sessions": 0, "login_attempts": 0})
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200
    assert calls == [1]

    def boom(db, now=None):
        raise RuntimeError("db hiccup")

    monkeypatch.setattr(retention, "purge_expired", boom)
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200


def test_live_session_survives_the_purge_end_to_end():
    with TestClient(app) as c:
        headers, _, _ = register_user(c)
        with SessionLocal() as db:
            retention.purge_expired(db)
        assert c.get("/api/auth/me", headers=headers).status_code == 200
