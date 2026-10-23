import os
import shutil
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
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

    # Read bytes
    contents = await file.read()
    if not contents or len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hmm, why is the file empty? This is a blank file."
        )

    # Save physical file
    saved_filename = f"{user.id}_{int(os.times().system)}_{filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, saved_filename)
    with open(file_path, "wb") as f:
        f.write(contents)

    # Extract text
    if file_ext == "pdf":
        raw_text = parser_service.parse_pdf(contents, filename)
    else:
        raw_text = parser_service.parse_docx(contents, filename)

    title = custom_title.strip() if custom_title and custom_title.strip() else filename.rsplit(".", 1)[0]

    # Create document
    doc = Document(
        user_id=user.id,
        title=title,
        file_type=file_ext,
        file_path=file_path,
        raw_text=raw_text
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Segment text into topics
    topic_data_list = segmenter_service.segment_text(raw_text, document_title=title)
    for topic_dict in topic_data_list:
        topic = Topic(
            document_id=doc.id,
            title=topic_dict["title"],
            content=topic_dict["content"],
            order_index=topic_dict["order_index"]
        )
        db.add(topic)
    
    db.commit()
    db.refresh(doc)
    return doc

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

    doc = Document(
        user_id=user.id,
        title=payload.title.strip(),
        file_type="text",
        file_path=None,
        raw_text=raw_text
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    topic_data_list = segmenter_service.segment_text(raw_text, document_title=payload.title)
    for topic_dict in topic_data_list:
        topic = Topic(
            document_id=doc.id,
            title=topic_dict["title"],
            content=topic_dict["content"],
            order_index=topic_dict["order_index"]
        )
        db.add(topic)

    db.commit()
    db.refresh(doc)
    return doc

@router.get("", response_model=List[DocumentListItem])
def list_documents(db: Session = Depends(get_db)):
    """
    Get all uploaded documents with summary stats.
    """
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    results = []
    for d in docs:
        topic_count = db.query(Topic).filter(Topic.document_id == d.id).count()
        flashcard_count = db.query(Flashcard).filter(Flashcard.document_id == d.id).count()
        question_count = db.query(Question).filter(Question.document_id == d.id).count()
        word_count = len(d.raw_text.split()) if d.raw_text else 0

        results.append(DocumentListItem(
            id=d.id,
            title=d.title,
            file_type=d.file_type,
            created_at=d.created_at,
            topics_count=topic_count,
            flashcards_count=flashcard_count,
            questions_count=question_count,
            word_count=word_count
        ))
    return results

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
