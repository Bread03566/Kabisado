"""Short-lived access tokens (JWT, HS256). The role is deliberately NOT in the token: it is read from the
database on every request so deactivation and role changes take effect immediately."""
import datetime
import hashlib

import jwt

from app.config import settings

ALGORITHM = "HS256"


class TokenError(Exception):
    pass


def _kid(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:8]


def _keys() -> dict[str, str]:
    """kid -> secret for the current secret and, while rotating, the previous one."""
    return {_kid(s): s for s in (settings.JWT_SECRET, settings.JWT_SECRET_PREVIOUS) if s}


def create_access_token(user_id: int, session_id: int) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user_id),
        "sid": session_id,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM, headers={"kid": _kid(settings.JWT_SECRET)})


def decode_access_token(token: str) -> dict:
    try:
        key = _keys().get(jwt.get_unverified_header(token).get("kid"))
        if key is None:
            raise TokenError("unknown signing key")
        claims = jwt.decode(token, key, algorithms=[ALGORITHM], options={"require": ["exp", "sub", "sid"]})
        return {"sub": int(claims["sub"]), "sid": int(claims["sid"]), "exp": claims["exp"]}
    except TokenError:
        raise
    except (jwt.PyJWTError, ValueError, TypeError) as err:
        raise TokenError(str(err)) from err
