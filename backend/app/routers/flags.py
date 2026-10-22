from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.models import Flag
from app.schemas.schemas import FlagCreate, FlagResponse, MessageResponse

router = APIRouter(prefix="/api/flags", tags=["flags"])

@router.post("", response_model=FlagResponse, status_code=status.HTTP_201_CREATED)
def flag_item(
    payload: FlagCreate,
    db: Session = Depends(get_db)
):
    """
    Flag a problematic flashcard or question.
    """
    flag = Flag(
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
def list_flags(db: Session = Depends(get_db)):
    """
    List all flagged items.
    """
    return db.query(Flag).order_by(Flag.created_at.desc()).all()
