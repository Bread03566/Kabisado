import datetime
import json

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.identity import get_current_user
from app.models.models import Document, QuizAttempt, User

router = APIRouter(prefix="/api/auth", tags=["account"])


@router.get("/export")
def export_my_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Everything the signed-in student owns, as one JSON download. No password or recovery hashes, tokens or
    internal references are included."""
    docs = (db.query(Document).options(
        selectinload(Document.topics), selectinload(Document.flashcards), selectinload(Document.questions))
        .filter(Document.user_id == user.id).order_by(Document.id).all())
    attempts = db.query(QuizAttempt).filter(QuizAttempt.user_id == user.id).order_by(QuizAttempt.id).all()
    payload = {
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "account": {
            "username": user.username, "display_name": user.display_name,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "documents": [
            {
                "id": d.id, "title": d.title, "file_type": d.file_type,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "text": d.raw_text,
                "summaries": {"brief": d.summary_brief, "standard": d.summary_standard, "detailed": d.summary_detailed},
                "key_terms": d.key_terms,
                "topics": [{"title": t.title, "content": t.content, "summary": t.summary} for t in d.topics],
                "flashcards": [
                    {"front": f.front, "back": f.back, "type": f.card_type, "ease_factor": f.ease_factor,
                     "interval_days": f.interval, "repetitions": f.repetitions,
                     "next_review": f.next_review.isoformat() if f.next_review else None}
                    for f in d.flashcards],
                "questions": [
                    {"question": q.question_text, "choices": q.choices, "correct_index": q.correct_index,
                     "explanation": q.explanation, "difficulty": q.difficulty, "type": q.question_type,
                     "answer_data": q.answer_data}
                    for q in d.questions],
            }
            for d in docs
        ],
        "quiz_attempts": [
            {"document_id": a.document_id, "score": a.score, "total": a.total_questions,
             "difficulty": a.difficulty, "completed_at": a.completed_at.isoformat() if a.completed_at else None}
            for a in attempts
        ],
    }
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="kabisado-my-data.json"', "Cache-Control": "no-store"},
    )
