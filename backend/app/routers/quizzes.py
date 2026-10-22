from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime

from app.database import get_db
from app.models.models import Document, Topic, Question, QuizAttempt, QuestionAttempt, User
from app.schemas.schemas import (
    QuizGenerateRequest,
    QuestionResponse,
    QuizSubmitRequest,
    QuizResultResponse,
    QuestionResultDetail
)
from app.services.ai_service import ai_service

router = APIRouter(tags=["quizzes"])

@router.post("/api/documents/{document_id}/quiz/generate", response_model=List[QuestionResponse])
async def generate_quiz_questions(
    document_id: int,
    payload: QuizGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Generate multiple-choice questions for a document or specific topic.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    topics_to_process = []
    if payload.topic_id:
        topic = db.query(Topic).filter(Topic.id == payload.topic_id, Topic.document_id == doc.id).first()
        if not topic:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
        topics_to_process.append(topic)
    else:
        topics_to_process = db.query(Topic).filter(Topic.document_id == doc.id).order_by(Topic.order_index).all()
        if not topics_to_process:
            topic = Topic(document_id=doc.id, title="Pangunahing Paksa", content=doc.raw_text, order_index=0)
            db.add(topic)
            db.commit()
            db.refresh(topic)
            topics_to_process.append(topic)

    questions_per_topic = max(1, payload.count // len(topics_to_process)) if len(topics_to_process) > 0 else payload.count

    created_questions = []
    for topic in topics_to_process:
        generated = await ai_service.generate_quiz_questions(
            document_title=doc.title,
            topic_title=topic.title,
            topic_content=topic.content,
            topic_id=topic.id,
            count=questions_per_topic,
            difficulty=payload.difficulty or "medium"
        )

        for q_data in generated:
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
            created_questions.append(q)

    db.commit()
    for q in created_questions:
        db.refresh(q)

    results = []
    for q in created_questions:
        t_title = q.topic.title if q.topic else None
        results.append(QuestionResponse(
            id=q.id,
            document_id=q.document_id,
            topic_id=q.topic_id,
            topic_title=t_title,
            question_text=q.question_text,
            choices=q.choices,
            correct_index=q.correct_index,
            explanation=q.explanation,
            difficulty=q.difficulty,
            created_at=q.created_at
        ))

    return results

@router.post("/api/documents/{document_id}/quiz/weak-spots", response_model=List[QuestionResponse])
async def generate_weak_spot_quiz(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Generates a targeted quiz from the student's lowest-mastery topics (Weak-Spot Quiz).
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    topics = db.query(Topic).filter(Topic.document_id == doc.id).all()
    if not topics:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Walang topics ang document na ito.")

    # Calculate mastery per topic
    topic_scores = []
    for t in topics:
        q_ids = [q.id for q in t.questions]
        if not q_ids:
            topic_scores.append((t, 0.0, 0))
            continue
        attempts = db.query(QuestionAttempt).filter(QuestionAttempt.question_id.in_(q_ids)).all()
        if not attempts:
            topic_scores.append((t, 0.0, 0))
        else:
            correct = sum(1 for a in attempts if a.is_correct)
            pct = (correct / len(attempts)) * 100
            topic_scores.append((t, pct, len(attempts)))

    # Sort topics by lowest mastery first
    topic_scores.sort(key=lambda x: (x[1], -x[2]))
    weak_topics = [item[0] for item in topic_scores[:3]]

    # Generate or pick 2 questions per weak topic
    created_questions = []
    for topic in weak_topics:
        generated = await ai_service.generate_quiz_questions(
            document_title=doc.title,
            topic_title=topic.title,
            topic_content=topic.content,
            topic_id=topic.id,
            count=2,
            difficulty="medium"
        )
        for q_data in generated:
            q = Question(
                document_id=doc.id,
                topic_id=topic.id,
                question_text=q_data["question"],
                choices=q_data["choices"],
                correct_index=q_data["correct_index"],
                explanation=q_data["explanation"],
                difficulty="medium"
            )
            db.add(q)
            created_questions.append(q)

    db.commit()
    for q in created_questions:
        db.refresh(q)

    results = []
    for q in created_questions:
        t_title = q.topic.title if q.topic else None
        results.append(QuestionResponse(
            id=q.id,
            document_id=q.document_id,
            topic_id=q.topic_id,
            topic_title=t_title,
            question_text=q.question_text,
            choices=q.choices,
            correct_index=q.correct_index,
            explanation=q.explanation,
            difficulty=q.difficulty,
            created_at=q.created_at
        ))
    return results


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

    questions = query.order_by(Question.created_at.desc()).all()
    results = []
    for q in questions:
        t_title = q.topic.title if q.topic else None
        results.append(QuestionResponse(
            id=q.id,
            document_id=q.document_id,
            topic_id=q.topic_id,
            topic_title=t_title,
            question_text=q.question_text,
            choices=q.choices,
            correct_index=q.correct_index,
            explanation=q.explanation,
            difficulty=q.difficulty,
            created_at=q.created_at
        ))
    return results

@router.post("/api/quizzes/submit", response_model=QuizResultResponse)
def submit_quiz_attempt(
    payload: QuizSubmitRequest,
    db: Session = Depends(get_db)
):
    """
    Submit quiz answers, record attempts, and return scored results with roast/praise.
    """
    total = len(payload.answers)
    if total == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Walang sagot na na-submit!")

    score = 0
    results_detail: List[QuestionResultDetail] = []

    # Create quiz attempt
    attempt = QuizAttempt(
        user_id=1,
        document_id=payload.document_id,
        topic_id=payload.topic_id,
        score=0,
        total_questions=total,
        difficulty=payload.difficulty,
        completed_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    for item in payload.answers:
        question = db.query(Question).filter(Question.id == item.question_id).first()
        if not question:
            continue

        is_correct = (item.selected_index == question.correct_index)
        if is_correct:
            score += 1

        qa = QuestionAttempt(
            attempt_id=attempt.id,
            question_id=question.id,
            selected_index=item.selected_index,
            is_correct=is_correct,
            answered_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(qa)

        t_title = question.topic.title if question.topic else None
        results_detail.append(QuestionResultDetail(
            question_id=question.id,
            question_text=question.question_text,
            choices=question.choices,
            selected_index=item.selected_index,
            correct_index=question.correct_index,
            is_correct=is_correct,
            explanation=question.explanation,
            topic_title=t_title
        ))

    attempt.score = score
    db.commit()

    pct = round((score / total) * 100, 1) if total > 0 else 0.0

    # Funny Taglish roast / praise based on score
    if pct == 100:
        grade = "Perpekto! 100%"
        roast = "Hala siya! Dean's Lister yarn?! Walang mintis! Kabisado mo na talaga 'tong module!"
    elif pct >= 80:
        grade = "Pasado! Galing!"
        roast = "Solid, lodi! Konting kembot na lang bago mag-exam, sigurado nang mataas marka mo!"
    elif pct >= 60:
        grade = "Pasado pero muntik na!"
        roast = "Pasa pa rin naman, pero baka mamaya kabahan ka sa actual exam. Silipin yung mga namali mo!"
    elif pct >= 40:
        grade = "Medyo sabaw..."
        roast = "Inantok ka ba o nag-scroll sa TikTok habang nag-aaral? Balikan natin yung mga flashcards!"
    else:
        grade = "Bagsak, lods..."
        roast = "Tulog muna 15 minutes o uminom ng kape. Wag susuko, aral ulit tayo ngayon para pasa bukas!"

    return QuizResultResponse(
        attempt_id=attempt.id,
        score=score,
        total_questions=total,
        percentage=pct,
        grade_message=grade,
        roast_or_praise=roast,
        results=results_detail
    )
