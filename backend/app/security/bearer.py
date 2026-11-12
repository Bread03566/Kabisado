"""Authenticate a request from its Authorization: Bearer access token.

Role and active state are read from the database on every request, and the token's session must still be
live, so deactivation, logout and role changes take effect immediately rather than when the token expires.
"""
import datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User, UserSession
from app.security.tokens import TokenError, decode_access_token


def _unauthorized(detail: str = "Please sign in.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail,
                         headers={"WWW-Authenticate": "Bearer"})


def authenticate_bearer(request: Request, db: Session) -> User:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized()
    try:
        claims = decode_access_token(token.strip())
    except TokenError:
        raise _unauthorized("Your session has expired. Please sign in again.")
    row = (
        db.query(User, UserSession)
        .join(UserSession, UserSession.user_id == User.id)
        .filter(User.id == claims["sub"], UserSession.id == claims["sid"])
        .first()
    )
    if row is None:
        raise _unauthorized()
    user, session = row
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    if not user.is_active or session.revoked_at is not None or session.expires_at <= now:
        raise _unauthorized()
    return user


def get_bearer_user(request: Request, db: Session = Depends(get_db)) -> User:
    return authenticate_bearer(request, db)
