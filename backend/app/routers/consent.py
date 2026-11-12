from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.identity import get_current_user
from app.models.models import User
from app.services import consent

router = APIRouter(prefix="/api/consent", tags=["consent"])


class GrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_adult: bool
    accept_disclosure: bool
    policy_version: str


def _gemini_available() -> bool:
    return bool(settings.GEMINI_ENABLED) and bool((settings.GEMINI_API_KEY or "").strip())


@router.get("")
def status_of_my_consent(user: User = Depends(get_current_user)):
    consenting = bool(user.gemini_consent and user.consent_policy_version == consent.CURRENT_POLICY_VERSION)
    return {
        "gemini_available": _gemini_available(),
        "consent": consenting,
        "needs_reaccept": bool(user.gemini_consent) and not consenting,
        "policy_version": consent.CURRENT_POLICY_VERSION,
    }


@router.post("/gemini")
def give_consent(payload: GrantRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _gemini_available():
        raise HTTPException(status.HTTP_409_CONFLICT, "Gemini AI is not available on this site.")
    if not (payload.confirm_adult and payload.accept_disclosure):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Both confirmations are needed.")
    if payload.policy_version != consent.CURRENT_POLICY_VERSION:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The notice has changed. Please reload and read it again.")
    reask = bool(user.gemini_consent) and user.consent_policy_version != consent.CURRENT_POLICY_VERSION
    if reask:
        consent.append_event(db, user, "policy_reask")
    user.age_band = "adult"
    user.gemini_consent = True
    user.consent_policy_version = consent.CURRENT_POLICY_VERSION
    consent.append_event(db, user, "grant")
    db.commit()
    return {"consent": True}


@router.delete("/gemini", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_consent(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Takes effect at once: the gate re-reads this flag before every request to Gemini."""
    user.gemini_consent = False
    consent.append_event(db, user, "withdraw")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
