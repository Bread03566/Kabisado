import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any

from app.database import get_db
from app.models.models import (
    Document,
    Topic,
    Flashcard,
    Question,
    QuizAttempt,
    QuestionAttempt,
    User
)

router = APIRouter(prefix="/api/progress", tags=["progress"])

def get_utc_now():
    return datetime.datetime.now(datetime.timezone.utc)

@router.get("/dashboard")
def get_dashboard_stats(
    document_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Computes dashboard analytics:
    - Study streak (consecutive active days)
    - Cards due today for SM-2 review
    - Overall accuracy and total attempts
    - Per-topic mastery percentages
    - Weak topics list (topics needing urgent review)
    - Quiz score timeline / history
    """
    now = get_utc_now()
    
    # 1. Base queries
    doc_filter = [QuizAttempt.document_id == document_id] if document_id else []
    fc_filter = [Flashcard.document_id == document_id] if document_id else []

    # 2. Cards Due Today
    cards_due_count = db.query(Flashcard).filter(
        *fc_filter,
        Flashcard.next_review <= now
    ).count()

    total_cards = db.query(Flashcard).filter(*fc_filter).count()

    # 3. Quiz Attempts History
    attempts_query = db.query(QuizAttempt).filter(*doc_filter).order_by(QuizAttempt.completed_at.desc())
    recent_attempts = attempts_query.limit(15).all()

    total_quizzes = len(recent_attempts)
    total_questions_answered = 0
    total_correct = 0

    history_list = []
    for att in recent_attempts:
        pct = round((att.score / att.total_questions) * 100, 1) if att.total_questions > 0 else 0.0
        doc_title = att.document.title if att.document else "Module"
        history_list.append({
            "id": att.id,
            "document_id": att.document_id,
            "document_title": doc_title,
            "score": att.score,
            "total_questions": att.total_questions,
            "percentage": pct,
            "difficulty": att.difficulty or "medium",
            "completed_at": att.completed_at.isoformat() if att.completed_at else None
        })
        total_questions_answered += att.total_questions
        total_correct += att.score

    overall_accuracy = (
        round((total_correct / total_questions_answered) * 100, 1)
        if total_questions_answered > 0
        else 0.0
    )

    # 4. Per-Topic Mastery Breakdown
    # Join Topic with Question and QuestionAttempt
    topic_query = db.query(Topic)
    if document_id:
        topic_query = topic_query.filter(Topic.document_id == document_id)
    topics = topic_query.order_by(Topic.order_index).all()

    topic_mastery_list = []
    weak_topics_list = []

    for t in topics:
        q_ids = [q.id for q in t.questions]
        if not q_ids:
            # If no questions yet for topic, mastery is 0
            topic_mastery_list.append({
                "topic_id": t.id,
                "document_id": t.document_id,
                "topic_title": t.title,
                "total_answered": 0,
                "correct_count": 0,
                "mastery_percent": 0.0,
                "status": "untested"
            })
            continue

        attempts_for_topic = db.query(QuestionAttempt).filter(
            QuestionAttempt.question_id.in_(q_ids)
        ).all()

        total_ans = len(attempts_for_topic)
        correct_ans = sum(1 for a in attempts_for_topic if a.is_correct)
        mastery_pct = round((correct_ans / total_ans) * 100, 1) if total_ans > 0 else 0.0

        if total_ans == 0:
            status_label = "untested"
        elif mastery_pct >= 80:
            status_label = "mastered"
        elif mastery_pct >= 60:
            status_label = "reviewing" # Partly known, still needs review
        else:
            status_label = "weak"      # Weak spot

        item = {
            "topic_id": t.id,
            "document_id": t.document_id,
            "topic_title": t.title,
            "total_answered": total_ans,
            "correct_count": correct_ans,
            "mastery_percent": mastery_pct,
            "status": status_label
        }
        topic_mastery_list.append(item)

        if status_label in ["weak", "reviewing"] or (total_ans == 0 and len(topics) > 1):
            weak_topics_list.append(item)

    # Sort weak topics: lowest mastery first
    weak_topics_list.sort(key=lambda x: (x["mastery_percent"], -x["total_answered"]))

    # 5. Study Streak Calculation
    # Look at distinct dates of QuizAttempts and card reviews
    all_dates = set()
    for att in db.query(QuizAttempt.completed_at).all():
        if att[0]:
            all_dates.add(att[0].date())

    streak = calculate_consecutive_days_streak(all_dates)

    # 6. Funny Motivational Roast / Praise for Dashboard
    if streak >= 3 and overall_accuracy >= 80:
        mascot_mood = "happy"
        streak_message = f"Solid! A {streak}-day streak and {overall_accuracy}% accuracy! No failing grades for you!"
    elif streak > 0:
        mascot_mood = "studying"
        streak_message = f"Keep it up! Day {streak} of reviewing. Don't stop, so you don't forget!"
    elif cards_due_count > 0:
        mascot_mood = "sleepy"
        streak_message = f"You have {cards_due_count} flashcards to study today. Let's go before you get sleepy!"
    else:
        mascot_mood = "sleepy"
        streak_message = "Let's start a quiz or some flashcards to get your streak going!"

    return {
        "streak_days": streak,
        "cards_due_today": cards_due_count,
        "total_cards": total_cards,
        "total_quizzes_taken": total_quizzes,
        "overall_accuracy": overall_accuracy,
        "mascot_mood": mascot_mood,
        "mascot_message": streak_message,
        "topic_mastery": topic_mastery_list,
        "weak_topics": weak_topics_list[:5],
        "quiz_history": history_list
    }

def calculate_consecutive_days_streak(active_dates: set) -> int:
    """Calculates active daily streak up to today or yesterday."""
    if not active_dates:
        return 0

    today = datetime.datetime.now(datetime.timezone.utc).date()
    yesterday = today - datetime.timedelta(days=1)

    # If active today, count backwards from today; if not today but active yesterday, count from yesterday
    curr_date = today if today in active_dates else (yesterday if yesterday in active_dates else None)
    if not curr_date:
        return 0

    streak = 0
    while curr_date in active_dates:
        streak += 1
        curr_date -= datetime.timedelta(days=1)

    return streak
