"""Deletes login/session metadata after 30 days, as the privacy notice promises.

Runs at startup (the free Render instance restarts whenever it wakes) and on demand via
`python -m app.cli purge-expired`. It never touches users or their study content.
"""
import datetime

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.models import LoginAttempt, UserSession

RETENTION = datetime.timedelta(days=30)


def purge_expired(db: Session, now: datetime.datetime | None = None) -> dict:
    now = now or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    cutoff = now - RETENTION
    sessions = db.query(UserSession).filter(
        or_(
            UserSession.expires_at < cutoff,
            UserSession.revoked_at < cutoff,
            UserSession.rotated_at < cutoff,
        )
    ).delete(synchronize_session=False)
    attempts = db.query(LoginAttempt).filter(
        and_(
            LoginAttempt.window_start < cutoff,
            or_(LoginAttempt.locked_until.is_(None), LoginAttempt.locked_until < now),
        )
    ).delete(synchronize_session=False)
    db.commit()
    return {"sessions": sessions, "login_attempts": attempts}
