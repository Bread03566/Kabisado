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
    QuestionResultDetail,
    QuestionAttemptInput,
    AnswerCheckResponse
)
from app.services.ai_service import ai_service
from app.services import grading
from app.services.topic_planner import plan_counts, run_per_topic, topics_for_generation

router = APIRouter(tags=["quizzes"])

# Order used when the student asks for a mix of question types
MIXED_TYPES = ["multiple_choice", "identification", "true_false", "matching"]


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
        question_type=q.question_type or "multiple_choice",
        style=q.style,
        answer_data=q.answer_data,
        created_at=q.created_at
    )


def get_document_or_404(db: Session, document_id: int) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return doc


async def create_questions(
    db: Session,
    doc: Document,
    plan: List[tuple],
    difficulty: str,
    question_type: str = "multiple_choice",
    style: str = "mixed",
) -> List[QuestionResponse]:
    """
    Generates and stores questions for each (topic, count) pair, spreading a mixed type list across
    topics. Matching sets need several facts, so they draw on all the planned topics at once instead
    of a single (often short) topic.
    """
    total = sum(count for _, count in plan)
    sequence = [MIXED_TYPES[i % len(MIXED_TYPES)] for i in range(total)] if question_type == "mixed" else [question_type] * total
    # Alternate styles across the whole quiz (not per topic), so "mixed" really gives both kinds
    styles = [("situational" if i % 2 == 0 else "definition") if style == "mixed" else style for i in range(total)]
    slots = list(zip(sequence, styles))
    types_by_topic = {}
    styles_by_topic = {}
    start = 0
    for topic, count in plan:
        topic_slots = [s for s in slots[start:start + count] if s[0] != "matching"]
        types_by_topic[topic.id] = [t for t, _ in topic_slots]
        styles_by_topic[topic.id] = [s for _, s in topic_slots]
        start += count
    matching_styles = [s for t, s in slots if t == "matching"]
    matching_count = len(matching_styles)

    async def generate(topic, count) -> List[Dict[str, Any]]:
        return await ai_service.generate_quiz_questions(
            document_title=doc.title,
            topic_title=topic.title,
            topic_content=topic.content,
            topic_id=topic.id,
            count=count,
            difficulty=difficulty,
            question_types=types_by_topic[topic.id],
            style=style,
            question_styles=styles_by_topic[topic.id]
        )

    per_topic_plan = [(topic, len(types_by_topic[topic.id])) for topic, _ in plan if types_by_topic[topic.id]]
    results = [(topic, count, generated) for topic, count, generated in await run_per_topic(per_topic_plan, generate)]

    if matching_count:
        # One combined passage, so each matching set can pair terms from different topics
        topics = [topic for topic, _ in plan]
        combined = "\n\n".join(f"{t.title}\n{t.content}" for t in topics)[:15000]
        matching_sets = await ai_service.generate_quiz_questions(
            document_title=doc.title,
            topic_title=doc.title,
            topic_content=combined,
            topic_id=topics[0].id if len(topics) == 1 else None,
            count=matching_count,
            difficulty=difficulty,
            question_types=["matching"] * matching_count,
            style=style,
            question_styles=matching_styles
        )
        results.append((None, matching_count, matching_sets))

    created: List[Question] = []
    for topic, count, generated in results:
        for q_data in generated[:count]:
            q = Question(
                document_id=doc.id,
                topic_id=topic.id if topic else q_data.get("topic_id"),
                question_text=q_data["question"],
                choices=q_data["choices"],
                correct_index=q_data["correct_index"],
                explanation=q_data["explanation"],
                difficulty=q_data.get("difficulty", "medium"),
                question_type=q_data.get("question_type", "multiple_choice"),
                style=q_data.get("style"),
                answer_data=q_data.get("answer_data")
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
    return await create_questions(
        db, doc, plan_counts(topics, payload.count), payload.difficulty or "medium", payload.question_type, payload.style
    )

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

@router.post("/api/quizzes/check", response_model=AnswerCheckResponse)
def check_answer(payload: QuestionAttemptInput, db: Session = Depends(get_db)):
    """
    Checks one answer for instant feedback (typed and matching answers need the server's
    forgiving comparison). Uses the same grader as the final score.
    """
    question = db.query(Question).filter(Question.id == payload.question_id).first()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
    return AnswerCheckResponse(
        is_correct=grading.grade(question, payload.selected_index, payload.text_answer, payload.matching),
        correct_answer=grading.describe_correct(question),
        explanation=question.explanation
    )


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
        is_correct = grading.grade(question, item.selected_index, item.text_answer, item.matching)
        score += int(is_correct)
        selected = item.selected_index if item.selected_index is not None else -1

        attempt.question_attempts.append(QuestionAttempt(
            question_id=question.id,
            selected_index=selected,
            response={"text_answer": item.text_answer, "matching": item.matching} if item.selected_index is None else None,
            is_correct=is_correct,
            answered_at=now
        ))
        results_detail.append(QuestionResultDetail(
            question_id=question.id,
            question_text=question.question_text,
            choices=question.choices,
            selected_index=selected,
            correct_index=question.correct_index,
            is_correct=is_correct,
            explanation=question.explanation,
            topic_title=question.topic.title if question.topic else None,
            question_type=question.question_type or "multiple_choice",
            answer_data=question.answer_data,
            your_answer=grading.describe_response(question, item.selected_index, item.text_answer, item.matching),
            correct_answer=grading.describe_correct(question)
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
