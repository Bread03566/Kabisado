import datetime
import hashlib
import uuid

import jwt
import pytest

import app.main  # noqa: F401  (makes sure the schema exists)
from app.config import settings
from app.database import SessionLocal
from app.models.models import User, UserSession
from app.security import sessions, tokens


def naive_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def user(db):
    u = User(username=f"u-{uuid.uuid4().hex[:10]}", display_name="Test")
    db.add(u)
    db.commit()
    return u


# ---------- access tokens ----------
def test_access_token_round_trip():
    claims = tokens.decode_access_token(tokens.create_access_token(7, 42))
    assert claims["sub"] == 7 and claims["sid"] == 42 and "exp" in claims


def test_expired_access_token_rejected(monkeypatch):
    monkeypatch.setattr(settings, "ACCESS_TOKEN_MINUTES", -1)
    token = tokens.create_access_token(1, 1)
    with pytest.raises(tokens.TokenError):
        tokens.decode_access_token(token)


def test_wrong_signature_and_none_algorithm_rejected():
    forged = jwt.encode({"sub": "1", "sid": 1, "exp": 4102444800}, "some-other-secret-some-other-secret-xx", algorithm="HS256")
    with pytest.raises(tokens.TokenError):
        tokens.decode_access_token(forged)
    unsigned = jwt.encode({"sub": "1", "sid": 1, "exp": 4102444800}, None, algorithm="none")
    with pytest.raises(tokens.TokenError):
        tokens.decode_access_token(unsigned)
    with pytest.raises(tokens.TokenError):
        tokens.decode_access_token("not.a.jwt")


def test_token_signed_with_previous_secret_still_decodes(monkeypatch):
    old_secret = settings.JWT_SECRET
    token = tokens.create_access_token(3, 9)
    monkeypatch.setattr(settings, "JWT_SECRET", "brand-new-secret-brand-new-secret-123456")
    monkeypatch.setattr(settings, "JWT_SECRET_PREVIOUS", old_secret)
    assert tokens.decode_access_token(token)["sub"] == 3
    # and tokens minted now use the new secret, so dropping the previous one later invalidates only the old ones
    new_token = tokens.create_access_token(3, 9)
    monkeypatch.setattr(settings, "JWT_SECRET_PREVIOUS", None)
    assert tokens.decode_access_token(new_token)["sub"] == 3
    with pytest.raises(tokens.TokenError):
        tokens.decode_access_token(token)


# ---------- refresh sessions ----------
def test_refresh_token_is_stored_only_as_sha256(db, user):
    token, row = sessions.issue_session(db, user.id, "pytest-agent")
    assert row.refresh_hash == hashlib.sha256(token.encode()).hexdigest()
    stored = db.query(UserSession).filter_by(id=row.id).one()
    assert token not in {str(getattr(stored, c.name)) for c in UserSession.__table__.columns}
    assert stored.user_agent_hash and stored.user_agent_hash != "pytest-agent"


def test_rotation_issues_successor_and_marks_old_rotated(db, user):
    token, first = sessions.issue_session(db, user.id, None)
    new_token, second = sessions.rotate_session(db, token)
    assert new_token != token and second.id != first.id and second.family_id == first.family_id
    db.refresh(first)
    assert first.rotated_at is not None and first.replaced_by == second.id


def test_two_tabs_rotating_inside_the_grace_window_both_succeed(db, user):
    token, first = sessions.issue_session(db, user.id, None)
    a_token, a = sessions.rotate_session(db, token)
    b_token, b = sessions.rotate_session(db, token)  # second tab, same old token, moments later
    assert a_token != b_token and a.family_id == b.family_id == first.family_id
    # both new tokens are live
    sessions.rotate_session(db, a_token)
    sessions.rotate_session(db, b_token)


def test_replay_after_grace_revokes_the_whole_family(db, user):
    token, first = sessions.issue_session(db, user.id, None)
    live_token, live = sessions.rotate_session(db, token)
    first = db.query(UserSession).filter_by(id=first.id).one()
    first.rotated_at = naive_now() - datetime.timedelta(seconds=11)
    db.commit()
    with pytest.raises(sessions.SessionError):
        sessions.rotate_session(db, token)  # stolen/replayed token
    db.expire_all()
    family = db.query(UserSession).filter_by(family_id=first.family_id).all()
    assert family and all(s.revoked_at is not None for s in family)
    with pytest.raises(sessions.SessionError):
        sessions.rotate_session(db, live_token)  # the legitimate holder is logged out too


def test_unknown_expired_and_revoked_tokens_are_rejected(db, user):
    with pytest.raises(sessions.SessionError):
        sessions.rotate_session(db, "definitely-not-a-token")
    token, row = sessions.issue_session(db, user.id, None)
    row = db.query(UserSession).filter_by(id=row.id).one()
    row.expires_at = naive_now() - datetime.timedelta(seconds=1)
    db.commit()
    with pytest.raises(sessions.SessionError):
        sessions.rotate_session(db, token)
    token2, _ = sessions.issue_session(db, user.id, None)
    sessions.revoke_session(db, token2)
    with pytest.raises(sessions.SessionError):
        sessions.rotate_session(db, token2)


def test_revoke_all_for_user(db, user):
    t1, _ = sessions.issue_session(db, user.id, None)
    t2, _ = sessions.issue_session(db, user.id, None)
    sessions.revoke_all_for_user(db, user.id)
    for t in (t1, t2):
        with pytest.raises(sessions.SessionError):
            sessions.rotate_session(db, t)
