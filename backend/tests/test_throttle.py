import datetime
import uuid

import pytest
from fastapi import HTTPException

import app.main  # noqa: F401
from app.database import SessionLocal
from app.models.models import LoginAttempt
from app.security import throttle


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def name():
    return f"thr{uuid.uuid4().hex[:8]}"


def test_four_failures_do_not_lock(db):
    u = name()
    for _ in range(4):
        throttle.record_failure(db, u, "1.2.3.4")
    throttle.check_allowed(db, u, "1.2.3.4")  # still fine


def test_fifth_failure_locks_with_retry_after(db):
    u = name()
    for _ in range(5):
        throttle.record_failure(db, u, "1.2.3.4")
    with pytest.raises(HTTPException) as exc:
        throttle.check_allowed(db, u, "1.2.3.4")
    assert exc.value.status_code == 429
    assert int(exc.value.headers["Retry-After"]) >= 1


def test_lock_is_per_username_and_ip_not_a_global_account_lockout(db):
    u = name()
    for _ in range(6):
        throttle.record_failure(db, u, "1.2.3.4")
    throttle.check_allowed(db, u, "9.9.9.9")        # the real owner from another IP is not locked out
    throttle.check_allowed(db, name(), "1.2.3.4")   # other usernames from the same IP are fine


def test_backoff_grows_and_is_capped(db):
    u = name()
    for _ in range(30):
        throttle.record_failure(db, u, "5.5.5.5")
    row = db.get(LoginAttempt, throttle.make_key(u, "5.5.5.5"))
    seconds = (row.locked_until - datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)).total_seconds()
    assert 800 < seconds <= 900


def test_success_clears_the_counter(db):
    u = name()
    for _ in range(5):
        throttle.record_failure(db, u, "1.2.3.4")
    throttle.record_success(db, u, "1.2.3.4")
    throttle.check_allowed(db, u, "1.2.3.4")
    assert db.get(LoginAttempt, throttle.make_key(u, "1.2.3.4")) is None


def test_old_failures_age_out(db):
    u = name()
    for _ in range(3):
        throttle.record_failure(db, u, "1.2.3.4")
    row = db.get(LoginAttempt, throttle.make_key(u, "1.2.3.4"))
    row.window_start = row.window_start - datetime.timedelta(minutes=16)
    db.commit()
    for _ in range(4):
        throttle.record_failure(db, u, "1.2.3.4")  # the 3 old failures expired, so only 4 count
    throttle.check_allowed(db, u, "1.2.3.4")
