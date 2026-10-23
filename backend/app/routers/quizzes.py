from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
import datetime

from app.database import get_db
from app.models.models import Document, Topic, Question, QuizAttempt, QuestionAttempt
from app.schemas.schemas import (
    QuizGenerateRequest,
    QuestionResponse,
    QuizSubmitRequest,
    QuizResultResponse,
    QuestionResultDetail
)
from app.services.ai_service import ai_service
from app.services.topic_planner import plan_counts, run_per_topic, topics_for_generation

router = APIRouter(tags=["quizzes"])


def to_response(q: Question) -> QuestionResponse:
    return QuestionResponse(
        id=q.id,
        document_id=q.document_id,
        topic_id=q.topic_id,
        topic_title=q.topic.title if q.topic else None,
        question_text=q.question_text,
        choices=q.choices,
        correct_index=q.correct_index,
        explanation=q.explanation,
        difficulty=q.difficulty,
        created_at=q.created_at
    )


def get_document_or_404(db: Session, document_id: int) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return doc


async def create_questions(db: Session, doc: Document, plan: List[tuple], difficulty: str) -> List[QuestionResponse]:
    """Generates and stores questions for each (topic, count) pair."""
    async def generate(topic, count) -> List[Dict[str, Any]]:
        return await ai_service.generate_quiz_questions(
            document_title=doc.title,
            topic_title=topic.title,
            topic_content=topic.content,
            topic_id=topic.id,
            count=count,
            difficulty=difficulty
        )

    created: List[Question] = []
    for topic, count, generated in await run_per_topic(plan, generate):
        for q_data in generated[:count]:
            q = Question(
                document_id=doc.id,
                topic_id=topic.id,
                question_text=q_data["question"],
                choices=q_data["choices"],
                correct_index=q_data["correct_index"],
                explanation=q_data["explanation"],
                difficulty=q_data.get("difficulty", "medium")
            )
            db.add(q)
            created.append(q)

    if not created:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kabi couldn't find enough facts in this text to write quiz questions. Try a longer module, or connect an AI key."
        )

    db.commit()
    for q in created:
        db.refresh(q)
    return [to_response(q) for q in created]


@router.post("/api/documents/{document_id}/quiz/generate", response_model=List[QuestionResponse])
async def generate_quiz_questions(
    document_id: int,
    payload: QuizGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Generate multiple-choice questions for a document or specific topic.
    The requested count is spread across topics, so asking for 5 questions gives about 5 questions.
    """
    doc = get_document_or_404(db, document_id)
    topics = topics_for_generation(db, doc, payload.topic_id)
    return await create_questions(db, doc, plan_counts(topics, payload.count), payload.difficulty or "medium")

@router.post("/api/documents/{document_id}/quiz/weak-spots", response_model=List[QuestionResponse])
async def generate_weak_spot_quiz(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Generates a targeted quiz from the student's lowest-mastery topics (Weak-Spot Quiz).
    """
    doc = get_document_or_404(db, document_id)

    topics = db.query(Topic).filter(Topic.document_id == doc.id).all()
    if not topics:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This document has no topics.")

    # Calculate mastery per topic
    topic_scores = []
    for t in topics:
        q_ids = [q.id for q in t.questions]
        attempts = db.query(QuestionAttempt).filter(QuestionAttempt.question_id.in_(q_ids)).all() if q_ids else []
        correct = sum(1 for a in attempts if a.is_correct)
        pct = (correct / len(attempts)) * 100 if attempts else 0.0
        topic_scores.append((t, pct, len(attempts)))

    # Lowest mastery first; among equals, topics with more evidence of struggle first
    topic_scores.sort(key=lambda x: (x[1], -x[2]))
    weak_topics = [item[0] for item in topic_scores[:3]]

    return await create_questions(db, doc, [(topic, 2) for topic in weak_topics], "medium")


@router.get("/api/documents/{document_id}/questions", response_model=List[QuestionResponse])
def get_document_questions(
    document_id: int,
    topic_id: Optional[int] = None,
    difficulty: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get all questions for a document.
    """
    query = db.query(Question).filter(Question.document_id == document_id)
    if topic_id:
        query = query.filter(Question.topic_id == topic_id)
    if difficulty and difficulty != "mixed":
        query = query.filter(Question.difficulty == difficulty)
    return [to_response(q) for q in query.order_by(Question.created_at.desc()).all()]

@router.post("/api/quizzes/submit", response_model=QuizResultResponse)
def submit_quiz_attempt(
    payload: QuizSubmitRequest,
    db: Session = Depends(get_db)
):
    """
    Submit quiz answers, record attempts, and return scored results with roast/praise.
    """
    if not payload.answers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No answers were submitted!")
    get_document_or_404(db, payload.document_id)

    question_ids = [a.question_id for a in payload.answers]
    questions = {
        q.id: q
        for q in db.query(Question).filter(
            Question.id.in_(question_ids),
            Question.document_id == payload.document_id
        ).all()
    }
    answers = [a for a in payload.answers if a.question_id in questions]
    if not answers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="None of these questions belong to this module.")

    now = datetime.datetime.now(datetime.timezone.utc)
    attempt = QuizAttempt(
        user_id=1,
        document_id=payload.document_id,
        topic_id=payload.topic_id,
        score=0,
        total_questions=len(answers),
        difficulty=payload.difficulty,
        completed_at=now
    )
    db.add(attempt)

    score = 0
    results_detail: List[QuestionResultDetail] = []
    for item in answers:
        question = questions[item.question_id]
        is_correct = item.selected_index == question.correct_index
        score += int(is_correct)

        attempt.question_attempts.append(QuestionAttempt(
            question_id=question.id,
            selected_index=item.selected_index,
            is_correct=is_correct,
            answered_at=now
        ))
        results_detail.append(QuestionResultDetail(
            question_id=question.id,
            question_text=question.question_text,
            choices=question.choices,
            selected_index=item.selected_index,
            correct_index=question.correct_index,
            is_correct=is_correct,
            explanation=question.explanation,
            topic_title=question.topic.title if question.topic else None
        ))

    attempt.score = score
    db.commit()
    db.refresh(attempt)

    total = len(answers)
    pct = round((score / total) * 100, 1)

    # Funny roast / praise based on score
    if pct == 100:
        grade = "Perfect! 100%"
        roast = "Whoa! Dean's Lister material?! Not a single miss! You've truly mastered this module!"
    elif pct >= 80:
        grade = "Passed! Great job!"
        roast = "Solid, friend! Just a little more polish before the exam and you're sure to score high!"
    elif pct >= 60:
        grade = "Passed, but barely!"
        roast = "Still a pass, but you might get nervous on the real exam. Take a look at the ones you missed!"
    elif pct >= 40:
        grade = "A bit foggy..."
        roast = "Were you sleepy, or scrolling TikTok while studying? Let's go back to those flashcards!"
    else:
        grade = "Failed, friend..."
        roast = "Take a 15-minute nap or grab a coffee. Don't give up, let's study again today so you pass tomorrow!"

    return QuizResultResponse(
        attempt_id=attempt.id,
        score=score,
        total_questions=total,
        percentage=pct,
        grade_message=grade,
        roast_or_praise=roast,
        results=results_detail
    )
