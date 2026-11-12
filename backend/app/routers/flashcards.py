from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from app.database import get_db
from app.identity import get_current_user, get_owned_document
from app.models.models import Document, Flashcard, ReviewLog, User
from app.schemas.schemas import (
    FlashcardGenerateRequest,
    FlashcardCreate,
    FlashcardUpdate,
    FlashcardResponse,
    SM2ReviewRequest,
    MessageResponse
)
from app.services.ai_service import ai_service
from app.services.topic_planner import plan_counts, run_per_topic, topics_for_generation

router = APIRouter(tags=["flashcards"])


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def to_response(card: Flashcard) -> FlashcardResponse:
    return FlashcardResponse(
        id=card.id,
        document_id=card.document_id,
        topic_id=card.topic_id,
        topic_title=card.topic.title if card.topic else None,
        front=card.front,
        back=card.back,
        card_type=card.card_type,
        ease_factor=card.ease_factor,
        interval=card.interval,
        repetitions=card.repetitions,
        next_review=card.next_review,
        created_at=card.created_at
    )


def get_card_or_404(db: Session, user: User, card_id: int) -> Flashcard:
    card = (
        db.query(Flashcard)
        .join(Document, Document.id == Flashcard.document_id)
        .filter(Flashcard.id == card_id, Document.user_id == user.id)
        .first()
    )
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found.")
    return card


@router.get("/api/flashcards/due", response_model=List[FlashcardResponse])
def get_due_flashcards(
    document_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get all flashcards due for SM-2 review today (next_review <= now).
    """
    query = (
        db.query(Flashcard)
        .join(Document, Document.id == Flashcard.document_id)
        .filter(Document.user_id == user.id, Flashcard.next_review <= utc_now())
    )
    if document_id:
        query = query.filter(Flashcard.document_id == document_id)
    return [to_response(c) for c in query.order_by(Flashcard.next_review.asc()).all()]


@router.post("/api/documents/{document_id}/flashcards/generate", response_model=List[FlashcardResponse])
async def generate_flashcards(
    document_id: int,
    payload: FlashcardGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Generate AI flashcards from document topics and save to database.
    The requested count is spread across topics, so asking for 8 cards gives about 8 cards.
    """
    doc = get_owned_document(db, user, document_id)

    topics = topics_for_generation(db, doc, payload.topic_id)

    async def generate(topic, count):
        return await ai_service.generate_flashcards(
            document_title=doc.title,
            topic_title=topic.title,
            topic_content=topic.content,
            topic_id=topic.id,
            count=count,
            card_type=payload.card_type or "mixed"
        )

    created_cards = []
    for topic, count, generated in await run_per_topic(plan_counts(topics, payload.count), generate):
        for card_data in generated[:count]:
            fc = Flashcard(
                document_id=doc.id,
                topic_id=topic.id,
                front=card_data["front"],
                back=card_data["back"],
                card_type=card_data.get("card_type", "term"),
                ease_factor=2.5,
                interval=0,
                repetitions=0,
                next_review=utc_now()
            )
            db.add(fc)
            created_cards.append(fc)

    if not created_cards:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kabi couldn't find enough facts in this text to make flashcards. Try a longer module, or add cards yourself."
        )

    db.commit()
    for c in created_cards:
        db.refresh(c)
    return [to_response(c) for c in created_cards]

@router.get("/api/documents/{document_id}/flashcards", response_model=List[FlashcardResponse])
def get_document_flashcards(
    document_id: int,
    topic_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    List all flashcards for a document, with optional topic filter.
    """
    get_owned_document(db, user, document_id)
    query = db.query(Flashcard).filter(Flashcard.document_id == document_id)
    if topic_id:
        query = query.filter(Flashcard.topic_id == topic_id)
    return [to_response(c) for c in query.order_by(Flashcard.created_at.desc()).all()]

@router.post("/api/flashcards", response_model=FlashcardResponse, status_code=status.HTTP_201_CREATED)
def create_custom_flashcard(
    payload: FlashcardCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Manually create a custom flashcard.
    """
    get_owned_document(db, user, payload.document_id)

    card = Flashcard(
        document_id=payload.document_id,
        topic_id=payload.topic_id,
        front=payload.front.strip(),
        back=payload.back.strip(),
        card_type=payload.card_type,
        ease_factor=2.5,
        interval=0,
        repetitions=0,
        next_review=utc_now()
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return to_response(card)

@router.put("/api/flashcards/{card_id}", response_model=FlashcardResponse)
def update_flashcard(
    card_id: int,
    payload: FlashcardUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Edit a flashcard's front, back, or topic.
    """
    card = get_card_or_404(db, user, card_id)

    if payload.front is not None:
        card.front = payload.front.strip()
    if payload.back is not None:
        card.back = payload.back.strip()
    if payload.topic_id is not None:
        card.topic_id = payload.topic_id
    if payload.card_type is not None:
        card.card_type = payload.card_type

    db.commit()
    db.refresh(card)
    return to_response(card)

@router.delete("/api/flashcards/{card_id}", response_model=MessageResponse)
def delete_flashcard(card_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Delete a flashcard.
    """
    card = get_card_or_404(db, user, card_id)
    db.delete(card)
    db.commit()
    return MessageResponse(message="Flashcard deleted successfully.")

@router.post("/api/flashcards/{card_id}/review", response_model=FlashcardResponse)
def review_flashcard_sm2(
    card_id: int,
    payload: SM2ReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    SM-2 spaced repetition update after reviewing a card.
    Ratings:
    - 'again': reset interval to 1 day, repetition to 0.
    - 'hard': interval = max(1, interval * 1.2), ease_factor decreased slightly.
    - 'good': normal interval progression.
    - 'easy': bonus interval progression and ease factor boost.
    """
    card = get_card_or_404(db, user, card_id)

    rating = payload.rating.lower()
    now = utc_now()

    if rating == "again":
        card.repetitions = 0
        card.interval = 1
        card.ease_factor = max(1.3, card.ease_factor - 0.2)
    elif rating == "hard":
        if card.repetitions == 0:
            card.interval = 1
        else:
            card.interval = max(1, int(card.interval * 1.2))
        card.ease_factor = max(1.3, card.ease_factor - 0.15)
        card.repetitions += 1
    elif rating == "good":
        if card.repetitions == 0:
            card.interval = 1
        elif card.repetitions == 1:
            card.interval = 6
        else:
            card.interval = max(1, int(card.interval * card.ease_factor))
        card.repetitions += 1
    elif rating == "easy":
        if card.repetitions == 0:
            card.interval = 2
        elif card.repetitions == 1:
            card.interval = 7
        else:
            card.interval = max(1, int(card.interval * card.ease_factor * 1.3))
        card.ease_factor = min(3.0, card.ease_factor + 0.15)
        card.repetitions += 1

    card.next_review = now + datetime.timedelta(days=card.interval)
    db.add(ReviewLog(flashcard_id=card.id, rating=rating, reviewed_at=now))
    db.commit()
    db.refresh(card)
    return to_response(card)
