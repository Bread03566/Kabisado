from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.models import Document, Topic
from app.schemas.schemas import SummaryGenerateRequest, SummaryResponse, KeyTermItem
from app.services.ai_service import ai_service

router = APIRouter(prefix="/api/documents", tags=["summaries"])

@router.post("/{document_id}/summarize", response_model=SummaryResponse)
async def summarize_document(
    document_id: int,
    payload: SummaryGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Generate or retrieve summary and key terms for a document or specific topic.
    Length can be 'brief', 'standard', or 'detailed'.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wala rito yung document, lodi!"
        )

    # If summarizing a specific topic
    if payload.topic_id:
        topic = db.query(Topic).filter(Topic.id == payload.topic_id, Topic.document_id == doc.id).first()
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hindi mahanap ang specific topic na ito sa document."
            )
        ai_res = await ai_service.generate_summary(
            document_title=f"{doc.title} - {topic.title}",
            text_content=topic.content,
            length=payload.length
        )
        topic.summary = ai_res.get("summary")
        db.commit()
        return SummaryResponse(
            summary=ai_res.get("summary", ""),
            length=payload.length,
            key_terms=[KeyTermItem(**item) for item in ai_res.get("key_terms", [])]
        )

    # Check cache for document-level summary if already generated
    cached_summary = None
    if payload.length == "brief" and doc.summary_brief:
        cached_summary = doc.summary_brief
    elif payload.length == "standard" and doc.summary_standard:
        cached_summary = doc.summary_standard
    elif payload.length == "detailed" and doc.summary_detailed:
        cached_summary = doc.summary_detailed

    if cached_summary and doc.key_terms:
        return SummaryResponse(
            summary=cached_summary,
            length=payload.length,
            key_terms=[KeyTermItem(**item) for item in doc.key_terms]
        )

    # Generate via AI service
    ai_res = await ai_service.generate_summary(
        document_title=doc.title,
        text_content=doc.raw_text,
        length=payload.length
    )

    summary_text = ai_res.get("summary", "")
    terms_list = ai_res.get("key_terms", [])

    # Update database cache
    if payload.length == "brief":
        doc.summary_brief = summary_text
    elif payload.length == "standard":
        doc.summary_standard = summary_text
    elif payload.length == "detailed":
        doc.summary_detailed = summary_text

    if not doc.key_terms:
        doc.key_terms = terms_list

    db.commit()
    db.refresh(doc)

    return SummaryResponse(
        summary=summary_text,
        length=payload.length,
        key_terms=[KeyTermItem(**item) for item in terms_list]
    )
