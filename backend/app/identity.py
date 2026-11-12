"""
Who is calling, and what may they touch.

Identity comes from a bearer access token (see app.security.bearer); the role and active state are read from
the database on every request. Routers keep importing `get_current_user` and `get_owned_document` from here.
"""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Document, User
from app.security.bearer import authenticate_bearer


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    return authenticate_bearer(request, db)


def require_student(user: User = Depends(get_current_user)) -> User:
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This area is for student accounts.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrators only.")
    return user


def get_owned_document(db: Session, user: User, document_id: int, detail: str = "Document not found.") -> Document:
    """The document, or 404 whether it is missing or belongs to someone else (so IDs can't be probed)."""
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return doc
