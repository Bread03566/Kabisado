from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.database import get_db
from app.identity import get_current_user, get_owned_document
from app.models.models import User
from app.services.ai_service import ai_service

router = APIRouter(prefix="/api/documents", tags=["chat"])

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2)
    explain_like_new: bool = False
    conversation_history: Optional[List[Dict[str, str]]] = []

class ChatResponse(BaseModel):
    answer: str
    citation: Optional[str] = None
    found_in_document: bool

@router.post("/{document_id}/chat", response_model=ChatResponse)
async def ask_kabisado(
    document_id: int,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Ask Kabisado a question about an uploaded module.
    - Grounded only in document topics.
    - Cites source section.
    - Declares when info is not in the material instead of guessing.
    - Supports 'explain like I'm new to this' toggle.
    """
    doc = get_owned_document(db, user, document_id)

    topics_data = [
        {"id": t.id, "title": t.title, "content": t.content}
        for t in doc.topics
    ]
    if not topics_data:
        topics_data = [{"id": 0, "title": doc.title, "content": doc.raw_text}]

    result = await ai_service.answer_document_question(
            user_id=user.id,
        document_title=doc.title,
        topics=topics_data,
        question=payload.question.strip(),
        explain_like_new=payload.explain_like_new,
        conversation_history=payload.conversation_history
    )

    return ChatResponse(
        answer=result.get("answer", ""),
        citation=result.get("citation"),
        found_in_document=result.get("found_in_document", False)
    )
