"""Removing a user's files from disk (their rows are removed by the ORM cascade)."""
import logging
import os

from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import Document, User

logger = logging.getLogger("kabisado")


def delete_user_files(db: Session, user: User) -> int:
    """Unlink the original uploads of this user's documents. Only files inside UPLOAD_DIR are ever touched,
    so a bad `file_path` value cannot make this delete something elsewhere. Returns how many were removed."""
    root = os.path.realpath(settings.UPLOAD_DIR)
    removed = 0
    for (path,) in db.query(Document.file_path).filter(Document.user_id == user.id, Document.file_path.isnot(None)):
        real = os.path.realpath(path)
        if os.path.commonpath([root, real]) != root:
            logger.warning("Not deleting %s: outside the upload directory", path)
            continue
        try:
            os.remove(real)
            removed += 1
        except FileNotFoundError:
            pass
        except OSError:
            logger.exception("Could not delete uploaded file %s", path)
    return removed
