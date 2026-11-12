"""Operational heartbeats and the numbers behind the admin System panel."""
import datetime
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import AiUsage, Document, SystemStatus, User

BACKUP_WARN_HOURS = 36
DB_LIMIT_MB = 500  # Supabase Free database size


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def record(db: Session, key: str, value: str = "ok") -> None:
    row = db.get(SystemStatus, key)
    if row is None:
        db.add(SystemStatus(key=key, value=value, updated_at=_now()))
    else:
        row.value, row.updated_at = value, _now()
    db.commit()


def backup_status(db: Session) -> dict:
    row = db.get(SystemStatus, "last_backup")
    if row is None:
        return {"last_at": None, "age_hours": None, "warning": True,
                "message": "No backup has been recorded yet. Set up the nightly backup (see the runbook)."}
    age = (_now() - row.updated_at).total_seconds() / 3600
    warning = age > BACKUP_WARN_HOURS
    return {"last_at": row.updated_at.isoformat(), "age_hours": round(age, 1), "warning": warning,
            "message": f"Last backup {age:.0f} hours ago." + (" That is too old: check the Actions tab." if warning else "")}


def _database_size_mb(db: Session) -> Optional[float]:
    if db.bind.dialect.name != "postgresql":
        return None
    return round(db.execute(text("select pg_database_size(current_database())")).scalar() / 1024 / 1024, 1)


def system_report(db: Session) -> dict:
    day_start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    used = db.query(func.coalesce(func.sum(func.length(Document.raw_text)), 0)).scalar()
    return {
        "database": {"engine": db.bind.dialect.name, "size_mb": _database_size_mb(db), "limit_mb": DB_LIMIT_MB},
        "text_storage": {"used_mb": round(used / 1024 / 1024, 2), "budget_mb": settings.GLOBAL_TEXT_QUOTA_MB},
        "ai": {
            "enabled": bool(settings.GEMINI_ENABLED),
            "calls_today": db.query(func.count(AiUsage.id)).filter(AiUsage.created_at >= day_start).scalar(),
            "global_daily_limit": settings.GEMINI_GLOBAL_DAILY_CALLS,
            "consenting_students": db.query(func.count(User.id)).filter(User.gemini_consent.is_(True)).scalar(),
        },
        "backup": backup_status(db),
        "version": settings.APP_VERSION,
    }
