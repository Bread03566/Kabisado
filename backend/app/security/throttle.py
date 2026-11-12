"""Login/recovery throttling, stored in the database so it survives Render restarts.

Keyed by (username, client IP) with exponential backoff: the first 4 failures are free, then 2, 4, 8 ...
seconds capped at 15 minutes. It is never a hard per-username lockout, so an attacker cannot lock the
real owner out from a different IP.
"""
import datetime
import hashlib
import math

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.models import LoginAttempt

WINDOW = datetime.timedelta(minutes=15)
FREE_FAILURES = 4
MAX_DELAY_SECONDS = 900


def make_key(username: str, ip: str) -> str:
    return hashlib.sha256(f"{username}|{ip}".encode()).hexdigest()


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def check_allowed(db: Session, username: str, ip: str) -> None:
    row = db.get(LoginAttempt, make_key(username, ip))
    if row and row.locked_until and row.locked_until > _now():
        wait = max(1, math.ceil((row.locked_until - _now()).total_seconds()))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait a moment and try again.",
            headers={"Retry-After": str(wait)},
        )


def record_failure(db: Session, username: str, ip: str) -> None:
    key, now = make_key(username, ip), _now()
    row = db.get(LoginAttempt, key)
    if row is None:
        row = LoginAttempt(key=key, count=0, window_start=now)
        db.add(row)
    elif now - row.window_start > WINDOW:
        row.count, row.window_start, row.locked_until = 0, now, None
    row.count += 1
    if row.count > FREE_FAILURES:
        delay = min(2 ** (row.count - FREE_FAILURES), MAX_DELAY_SECONDS)
        row.locked_until = now + datetime.timedelta(seconds=delay)
    try:
        db.commit()
    except IntegrityError:  # two first failures raced to create the row; the other one counts
        db.rollback()


def record_success(db: Session, username: str, ip: str) -> None:
    row = db.get(LoginAttempt, make_key(username, ip))
    if row is not None:
        db.delete(row)
    db.commit()


REGISTER_WINDOW = datetime.timedelta(hours=1)


def register_gate(db: Session, ip: str) -> None:
    """Count one registration attempt for this IP; 429 once it exceeds the hourly limit. Each registration
    costs two Argon2 hashes on a very small CPU, so unlimited sign-ups would starve everyone's logins."""
    from app.config import settings  # read at call time so the limit can be changed without re-importing

    key, now = make_key("register", ip), _now()
    row = db.get(LoginAttempt, key)
    if row is None:
        db.add(LoginAttempt(key=key, count=1, window_start=now))
    elif now - row.window_start > REGISTER_WINDOW:
        row.count, row.window_start = 1, now
    elif row.count >= settings.REGISTER_LIMIT_PER_HOUR:
        wait = max(1, math.ceil((row.window_start + REGISTER_WINDOW - now).total_seconds()))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many new accounts from this network. Please try again later.",
            headers={"Retry-After": str(wait)},
        )
    else:
        row.count += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
