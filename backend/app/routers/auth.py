from __future__ import annotations

import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.models import User
from app.schemas.auth import (
    LoginRequest, RecoverRequest, RecoveryTokenResponse, RegisterRequest, TokenResponse, UserOut,
)
from app.security import throttle
from app.security.bearer import get_bearer_user
from app.security.passwords import hash_password, needs_rehash, validate_password, verify_password
from app.security.recovery import generate_recovery_code, hash_recovery_code, verify_recovery_code
from app.security.sessions import (
    SessionError, issue_session, revoke_all_for_user, revoke_session, rotate_session,
)
from app.security.tokens import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

BAD_LOGIN = "Incorrect username or password."
BAD_RECOVERY = "That username and recovery code do not match."


def client_ip(request: Request) -> str:
    if settings.TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()  # the hop our own proxy appended, not a client claim
    return request.client.host if request.client else "unknown"


def user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _cookie_args() -> dict:
    return dict(key=settings.refresh_cookie_name, path="/", secure=settings.COOKIE_SECURE,
                httponly=True, samesite="strict")


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(value=token, max_age=settings.REFRESH_TOKEN_DAYS * 86400, **_cookie_args())


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(**_cookie_args())


def require_cookie_csrf(request: Request) -> None:
    """Endpoints that act on the refresh cookie need a custom header (cannot be set by a plain cross-site
    form) and, when the browser sends an Origin, it must be ours."""
    if request.headers.get("x-kabisado-request") != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing request header.")
    origin = request.headers.get("origin")
    if origin and origin not in settings.allowed_origins and urlparse(origin).netloc != request.headers.get("host", ""):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Request origin not allowed.")


def _unauthorized(detail: str, clear_cookie: bool = False) -> JSONResponse:
    resp = JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": detail})
    if clear_cookie:
        clear_refresh_cookie(resp)
    return resp


def _naive_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _start_session(db: Session, user: User, request: Request, response: Response) -> str:
    refresh_token, session = issue_session(db, user.id, user_agent(request))
    set_refresh_cookie(response, refresh_token)
    return create_access_token(user.id, session.id)


@router.post("/register", response_model=RecoveryTokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        validate_password(payload.password, payload.username)
    except ValueError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(err))
    if db.query(User.id).filter(User.username == payload.username).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is already taken.")

    recovery_code = generate_recovery_code()
    password_hash = await hash_password(payload.password)
    recovery_hash = await hash_recovery_code(recovery_code)
    user = User(username=payload.username, display_name=payload.display_name,
                password_hash=password_hash, recovery_hash=recovery_hash)  # role/is_active use safe defaults
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # lost a race for the same username
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is already taken.")
    access = _start_session(db, user, request, response)
    return RecoveryTokenResponse(access_token=access, user=UserOut.model_validate(user), recovery_code=recovery_code)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    throttle.check_allowed(db, payload.username, ip)
    user = db.query(User).filter(User.username == payload.username).first()
    ok = await verify_password(user.password_hash if user else None, payload.password)
    if not (user and ok):
        throttle.record_failure(db, payload.username, ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, BAD_LOGIN)
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated.")
    if needs_rehash(user.password_hash):
        user.password_hash = await hash_password(payload.password)
    user.last_login_at = _naive_now()
    throttle.record_success(db, payload.username, ip)  # also commits the changes above
    access = _start_session(db, user, request, response)
    return TokenResponse(access_token=access, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: Session = Depends(get_db),
                  _: None = Depends(require_cookie_csrf)):
    token = request.cookies.get(settings.refresh_cookie_name)
    if not token:
        return _unauthorized("Please sign in.")
    try:
        new_token, session = rotate_session(db, token, user_agent(request))
    except SessionError:
        return _unauthorized("Your session has expired. Please sign in again.", clear_cookie=True)
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        revoke_all_for_user(db, session.user_id)
        return _unauthorized("Please sign in.", clear_cookie=True)
    set_refresh_cookie(response, new_token)
    return TokenResponse(access_token=create_access_token(user.id, session.id), user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, db: Session = Depends(get_db), _: None = Depends(require_cookie_csrf)):
    token = request.cookies.get(settings.refresh_cookie_name)
    if token:
        revoke_session(db, token)
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(resp)
    return resp


@router.post("/recover", response_model=RecoveryTokenResponse)
async def recover(payload: RecoverRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip, throttle_name = client_ip(request), "recover:" + payload.username
    throttle.check_allowed(db, throttle_name, ip)
    try:
        validate_password(payload.new_password, payload.username)
    except ValueError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(err))
    user = db.query(User).filter(User.username == payload.username).first()
    ok = await verify_recovery_code(user.recovery_hash if user else None, payload.recovery_code)
    if not (user and ok):
        throttle.record_failure(db, throttle_name, ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, BAD_RECOVERY)
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated.")

    new_code = generate_recovery_code()
    user.password_hash = await hash_password(payload.new_password)
    user.recovery_hash = await hash_recovery_code(new_code)
    db.commit()
    revoke_all_for_user(db, user.id)
    throttle.record_success(db, throttle_name, ip)
    access = _start_session(db, user, request, response)
    return RecoveryTokenResponse(access_token=access, user=UserOut.model_validate(user), recovery_code=new_code)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_bearer_user)):
    return user
