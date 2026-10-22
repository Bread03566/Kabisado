from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from app.database import get_db
from app.models.models import Document, Topic, Flashcard
from app.schemas.schemas import (
    FlashcardGenerateRequest,
    FlashcardCreate,
    FlashcardUpdate,
    FlashcardResponse,
    SM2ReviewRequest,
    MessageResponse
)
from app.services.ai_service import ai_service

router = APIRouter(tags=["flashcards"])

@router.get("/api/flashcards/due", response_model=List[FlashcardResponse])
def get_due_flashcards(
    document_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get all flashcards due for SM-2 review today (next_review <= now).
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    query = db.query(Flashcard).filter(Flashcard.next_review <= now)
    if document_id:
        query = query.filter(Flashcard.document_id == document_id)

    cards = query.order_by(Flashcard.next_review.asc()).all()
    results = []
    for c in cards:
        t_title = c.topic.title if c.topic else None
        results.append(FlashcardResponse(
            id=c.id,
            document_id=c.document_id,
            topic_id=c.topic_id,
            topic_title=t_title,
            front=c.front,
            back=c.back,
            card_type=c.card_type,
            ease_factor=c.ease_factor,
            interval=c.interval,
            repetitions=c.repetitions,
            next_review=c.next_review,
            created_at=c.created_at
        ))
    return results


@router.post("/api/documents/{document_id}/flashcards/generate", response_model=List[FlashcardResponse])
async def generate_flashcards(
    document_id: int,
    payload: FlashcardGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Generate AI flashcards from document topics and save to database.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )

    topics_to_process = []
    if payload.topic_id:
        topic = db.query(Topic).filter(Topic.id == payload.topic_id, Topic.document_id == doc.id).first()
        if not topic:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
        topics_to_process.append(topic)
    else:
        topics_to_process = db.query(Topic).filter(Topic.document_id == doc.id).order_by(Topic.order_index).all()
        if not topics_to_process:
            # Fallback if no topic rows exist
            topic = Topic(document_id=doc.id, title="Pangkalahatan", content=doc.raw_text, order_index=0)
            db.add(topic)
            db.commit()
            db.refresh(topic)
            topics_to_process.append(topic)

    # Calculate cards per topic
    cards_per_topic = max(2, payload.count // len(topics_to_process)) if len(topics_to_process) > 0 else payload.count

    created_cards = []
    for topic in topics_to_process:
        generated = await ai_service.generate_flashcards(
            document_title=doc.title,
            topic_title=topic.title,
            topic_content=topic.content,
            topic_id=topic.id,
            count=cards_per_topic,
            card_type=payload.card_type or "mixed"
        )

        for card_data in generated:
            fc = Flashcard(
                document_id=doc.id,
                topic_id=topic.id,
                front=card_data["front"],
                back=card_data["back"],
                card_type=card_data.get("card_type", "term"),
                ease_factor=2.5,
                interval=0,
                repetitions=0,
                next_review=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(fc)
            created_cards.append(fc)

    db.commit()
    for c in created_cards:
        db.refresh(c)

    # Attach topic_title for response
    results = []
    for c in created_cards:
        t_title = c.topic.title if c.topic else None
        results.append(FlashcardResponse(
            id=c.id,
            document_id=c.document_id,
            topic_id=c.topic_id,
            topic_title=t_title,
            front=c.front,
            back=c.back,
            card_type=c.card_type,
            ease_factor=c.ease_factor,
            interval=c.interval,
            repetitions=c.repetitions,
            next_review=c.next_review,
            created_at=c.created_at
        ))

    return results

@router.get("/api/documents/{document_id}/flashcards", response_model=List[FlashcardResponse])
def get_document_flashcards(
    document_id: int,
    topic_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    List all flashcards for a document, with optional topic filter.
    """
    query = db.query(Flashcard).filter(Flashcard.document_id == document_id)
    if topic_id:
        query = query.filter(Flashcard.topic_id == topic_id)
    
    cards = query.order_by(Flashcard.created_at.desc()).all()
    results = []
    for c in cards:
        t_title = c.topic.title if c.topic else None
        results.append(FlashcardResponse(
            id=c.id,
            document_id=c.document_id,
            topic_id=c.topic_id,
            topic_title=t_title,
            front=c.front,
            back=c.back,
            card_type=c.card_type,
            ease_factor=c.ease_factor,
            interval=c.interval,
            repetitions=c.repetitions,
            next_review=c.next_review,
            created_at=c.created_at
        ))
    return results

@router.post("/api/flashcards", response_model=FlashcardResponse, status_code=status.HTTP_201_CREATED)
def create_custom_flashcard(
    payload: FlashcardCreate,
    db: Session = Depends(get_db)
):
    """
    Manually create a custom flashcard.
    """
    card = Flashcard(
        document_id=payload.document_id,
        topic_id=payload.topic_id,
        front=payload.front.strip(),
        back=payload.back.strip(),
        card_type=payload.card_type,
        ease_factor=2.5,
        interval=0,
        repetitions=0,
        next_review=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    t_title = card.topic.title if card.topic else None
    return FlashcardResponse(
        id=card.id,
        document_id=card.document_id,
        topic_id=card.topic_id,
        topic_title=t_title,
        front=card.front,
        back=card.back,
        card_type=card.card_type,
        ease_factor=card.ease_factor,
        interval=card.interval,
        repetitions=card.repetitions,
        next_review=card.next_review,
        created_at=card.created_at
    )

@router.put("/api/flashcards/{card_id}", response_model=FlashcardResponse)
def update_flashcard(
    card_id: int,
    payload: FlashcardUpdate,
    db: Session = Depends(get_db)
):
    """
    Edit a flashcard's front, back, or topic.
    """
    card = db.query(Flashcard).filter(Flashcard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found.")

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
    t_title = card.topic.title if card.topic else None
    return FlashcardResponse(
        id=card.id,
        document_id=card.document_id,
        topic_id=card.topic_id,
        topic_title=t_title,
        front=card.front,
        back=card.back,
        card_type=card.card_type,
        ease_factor=card.ease_factor,
        interval=card.interval,
        repetitions=card.repetitions,
        next_review=card.next_review,
        created_at=card.created_at
    )

@router.delete("/api/flashcards/{card_id}", response_model=MessageResponse)
def delete_flashcard(card_id: int, db: Session = Depends(get_db)):
    """
    Delete a flashcard.
    """
    card = db.query(Flashcard).filter(Flashcard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
    db.delete(card)
    db.commit()
    return MessageResponse(message="Flashcard deleted successfully.")

@router.post("/api/flashcards/{card_id}/review", response_model=FlashcardResponse)
def review_flashcard_sm2(
    card_id: int,
    payload: SM2ReviewRequest,
    db: Session = Depends(get_db)
):
    """
    SM-2 spaced repetition update after reviewing a card.
    Ratings:
    - 'again': reset interval to 1 day, repetition to 0.
    - 'hard': interval = max(1, interval * 1.2), ease_factor decreased slightly.
    - 'good': normal interval progression.
    - 'easy': bonus interval progression and ease factor boost.
    """
    card = db.query(Flashcard).filter(Flashcard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")

    rating = payload.rating.lower()
    now = datetime.datetime.now(datetime.timezone.utc)

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
    db.commit()
    db.refresh(card)

    t_title = card.topic.title if card.topic else None
    return FlashcardResponse(
        id=card.id,
        document_id=card.document_id,
        topic_id=card.topic_id,
        topic_title=t_title,
        front=card.front,
        back=card.back,
        card_type=card.card_type,
        ease_factor=card.ease_factor,
        interval=card.interval,
        repetitions=card.repetitions,
        next_review=card.next_review,
        created_at=card.created_at
    )
