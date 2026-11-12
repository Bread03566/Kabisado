from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.identity import get_current_user, get_owned_document
from app.models.models import Document, Flag, Flashcard, Question, User
from app.schemas.schemas import FlagCreate, FlagResponse, MessageResponse

router = APIRouter(prefix="/api/flags", tags=["flags"])

@router.post("", response_model=FlagResponse, status_code=status.HTTP_201_CREATED)
def flag_item(
    payload: FlagCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Flag a problematic flashcard or question.
    """
    target = Flashcard if payload.target_type == "flashcard" else Question
    owned = (
        db.query(target.id)
        .join(Document, Document.id == target.document_id)
        .filter(target.id == payload.target_id, Document.user_id == user.id)
        .first()
    )
    if not owned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="That item isn't here, friend!")

    flag = Flag(
        user_id=user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=payload.reason.strip(),
        notes=payload.notes.strip() if payload.notes else None
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    return flag

@router.get("", response_model=List[FlagResponse])
def list_flags(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    List the current browser's flagged items.
    """
    return db.query(Flag).filter(Flag.user_id == user.id).order_by(Flag.created_at.desc()).all()
