"""Gemini consent: the single gate in front of every request that would leave the server.

`authorize` reads the database fresh on every call (never a token, cache or request object), and fails closed:
an unknown student, a missing consent, a stale policy version, an inactive account, a missing age confirmation,
the global switch being off, or an exhausted budget all mean "use the offline engine".
"""
import datetime
import hashlib
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.models import AiUsage, ConsentLog, User

CURRENT_POLICY_VERSION = "1"


def _utc_naive_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _row_hash(prev_hash: str, user_id: int, event: str, version: str, created_at: datetime.datetime) -> str:
    stamp = created_at.replace(tzinfo=None).isoformat()
    return hashlib.sha256(f"{prev_hash}|{user_id}|{event}|{version}|{stamp}".encode()).hexdigest()


def append_event(db: Session, user: User, event: str) -> ConsentLog:
    """Adds one entry to the student's chain. The caller commits, so the entry and the flag change together."""
    last = db.query(ConsentLog).filter_by(user_id=user.id).order_by(ConsentLog.id.desc()).first()
    prev = last.row_hash if last else ""
    now = _utc_naive_now()
    row = ConsentLog(user_id=user.id, event=event, policy_version=CURRENT_POLICY_VERSION, prev_hash=prev,
                     row_hash=_row_hash(prev, user.id, event, CURRENT_POLICY_VERSION, now), created_at=now)
    db.add(row)
    return row


def verify_chain(db: Session, user_id: Optional[int] = None) -> List[str]:
    """Problems found in the chain(s), as readable strings; an empty list means every link checks out."""
    query = db.query(ConsentLog).order_by(ConsentLog.user_id, ConsentLog.id)
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    problems: List[str] = []
    prev_by_user: dict = {}
    for row in query:
        expected_prev = prev_by_user.get(row.user_id, "")
        if row.prev_hash != expected_prev:
            problems.append(f"entry {row.id} (student {row.user_id}): chain is broken before this entry")
        elif row.row_hash != _row_hash(row.prev_hash, row.user_id, row.event, row.policy_version, row.created_at):
            problems.append(f"entry {row.id} (student {row.user_id}): contents were changed")
        prev_by_user[row.user_id] = row.row_hash
    return problems


def _within_budget(db: Session, user_id: int) -> bool:
    day_start = _utc_naive_now().replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = db.query(func.count(AiUsage.id)).filter(AiUsage.created_at >= day_start)
    if sent_today.filter(AiUsage.user_id == user_id).scalar() >= settings.GEMINI_USER_DAILY_CALLS:
        return False
    return sent_today.scalar() < settings.GEMINI_GLOBAL_DAILY_CALLS


def _eligible(db: Session, user_id: Optional[int]) -> bool:
    if user_id is None or not settings.GEMINI_ENABLED:
        return False
    user = db.get(User, user_id)
    return bool(
        user is not None and user.is_active and user.age_band == "adult" and user.gemini_consent
        and user.consent_policy_version == CURRENT_POLICY_VERSION
    )


def authorize(user_id: Optional[int]) -> bool:
    """May this student's content be sent to Gemini right now? Does not count against the budget."""
    with SessionLocal() as db:
        return _eligible(db, user_id) and _within_budget(db, user_id)


def reserve_gemini_call(user_id: Optional[int], feature: str) -> bool:
    """Authorize and, if allowed, record the request, immediately before the network call (every attempt)."""
    with SessionLocal() as db:
        if not (_eligible(db, user_id) and _within_budget(db, user_id)):
            return False
        db.add(AiUsage(user_id=user_id, feature=feature, engine="gemini", created_at=_utc_naive_now()))
        db.commit()
        return True
