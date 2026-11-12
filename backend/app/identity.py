"""
Per-browser identity. The frontend generates a random ID once, keeps it in localStorage and sends it
as the X-Client-Id header. Each ID maps to its own User row, so one browser never sees another's
documents. This is separation, not security: anyone who learns an ID can act as that browser.
"""
import re
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Document, User

CLIENT_ID_HEADER = "X-Client-Id"
CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{16,64}$")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    client_id = request.headers.get(CLIENT_ID_HEADER, "")
    if not CLIENT_ID_PATTERN.match(client_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid client ID. Please refresh the page and try again."
        )

    username = f"client-{client_id}"
    user = db.query(User).filter_by(username=username).first()
    if user:
        return user

    user = User(username=username, display_name=username[:60])  # temporary: removed with client-id auth in Task 10
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two first requests from a new browser raced; the other one won
        db.rollback()
        return db.query(User).filter_by(username=username).one()
    db.refresh(user)
    return user


def get_owned_document(db: Session, user: User, document_id: int, detail: str = "Document not found.") -> Document:
    """The document, or 404 whether it is missing or belongs to someone else (so IDs can't be probed)."""
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return doc
