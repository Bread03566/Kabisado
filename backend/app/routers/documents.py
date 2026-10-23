import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models.models import Document, Topic, Flashcard, Question, User
from app.schemas.schemas import (
    DocumentListItem,
    DocumentDetailResponse,
    DocumentCreateText,
    MessageResponse
)
from app.services.parser_service import parser_service
from app.services.segmenter_service import segmenter_service
from app.config import settings

router = APIRouter(prefix="/api/documents", tags=["documents"])

def get_or_create_default_user(db: Session) -> User:
    user = db.query(User).filter_by(username="iskolar").first()
    if not user:
        user = User(username="iskolar", email="iskolar@kabisado.ph")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def safe_stem(filename: str) -> str:
    """Display title from an uploaded filename, without any directory parts."""
    stem = Path(filename.replace("\\", "/")).name.rsplit(".", 1)[0].strip()
    return stem[:255] or "Uploaded module"

def save_document(db: Session, user: User, title: str, file_type: str, file_path: Optional[str], raw_text: str) -> Document:
    """Stores a document and its topics in one transaction, so a failure leaves nothing half-saved."""
    doc = Document(user_id=user.id, title=title, file_type=file_type, file_path=file_path, raw_text=raw_text)
    db.add(doc)
    for topic_dict in segmenter_service.segment_text(raw_text, document_title=title):
        doc.topics.append(Topic(
            title=topic_dict["title"][:255],
            content=topic_dict["content"],
            order_index=topic_dict["order_index"]
        ))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(doc)
    return doc

@router.post("/upload", response_model=DocumentDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    custom_title: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF or DOCX module, extract text, split into topics, and save.
    """
    user = get_or_create_default_user(db)
    filename = file.filename or "uploaded_file"
    file_ext = filename.split(".")[-1].lower() if "." in filename else ""

    if file_ext not in ["pdf", "docx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The .{file_ext} format isn't supported, friend! Only PDF or DOCX for now."
        )

    # Read bytes, refusing anything over the size limit
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"That file is over {settings.MAX_UPLOAD_MB} MB. Try splitting the module into smaller files."
        )
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hmm, why is the file empty? This is a blank file."
        )

    # Extract text first, so unreadable files are rejected before anything is stored
    if file_ext == "pdf":
        raw_text = parser_service.parse_pdf(contents, filename)
    else:
        raw_text = parser_service.parse_docx(contents, filename)

    title = custom_title.strip() if custom_title and custom_title.strip() else safe_stem(filename)

    # Save physical file under a generated name; the client's filename never becomes part of a path
    file_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}.{file_ext}")
    with open(file_path, "wb") as f:
        f.write(contents)

    try:
        return save_document(db, user, title, file_ext, file_path, raw_text)
    except Exception:
        os.remove(file_path)
        raise

@router.post("/text", response_model=DocumentDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_document_from_text(
    payload: DocumentCreateText,
    db: Session = Depends(get_db)
):
    """
    Create a document by directly pasting plain text.
    """
    user = get_or_create_default_user(db)
    raw_text = parser_service.parse_plain_text(payload.text)
    return save_document(db, user, payload.title.strip(), "text", None, raw_text)

@router.get("", response_model=List[DocumentListItem])
def list_documents(db: Session = Depends(get_db)):
    """
    Get all uploaded documents with summary stats.
    """
    def counts_by_document(model) -> dict:
        return dict(db.query(model.document_id, func.count(model.id)).group_by(model.document_id).all())

    topic_counts = counts_by_document(Topic)
    flashcard_counts = counts_by_document(Flashcard)
    question_counts = counts_by_document(Question)

    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return [
        DocumentListItem(
            id=d.id,
            title=d.title,
            file_type=d.file_type,
            created_at=d.created_at,
            topics_count=topic_counts.get(d.id, 0),
            flashcards_count=flashcard_counts.get(d.id, 0),
            questions_count=question_counts.get(d.id, 0),
            word_count=len(d.raw_text.split()) if d.raw_text else 0
        )
        for d in docs
    ]

@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """
    Get a specific document by ID with all its topics.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That document isn't here, friend! It may have been deleted, or the ID is wrong."
        )
    return doc

@router.delete("/{document_id}", response_model=MessageResponse)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """
    Delete a document and all related topics, cards, questions, and attempts.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find the document to delete."
        )

    # Remove file on disk if exists
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass

    db.delete(doc)
    db.commit()
    return MessageResponse(
        message="Successfully deleted!",
        detail=f"'{doc.title}' has been deleted. Time to move on."
    )
