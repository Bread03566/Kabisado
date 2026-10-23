import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import Optional

from app.database import get_db
from app.models.models import (
    Document,
    Topic,
    Flashcard,
    Question,
    QuizAttempt,
    QuestionAttempt,
    ReviewLog
)

router = APIRouter(prefix="/api/progress", tags=["progress"])

def get_utc_now():
    return datetime.datetime.now(datetime.timezone.utc)

def as_utc(value: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """SQLite returns naive datetimes; everything is stored in UTC, so label it as such."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)

@router.get("/dashboard")
def get_dashboard_stats(
    document_id: Optional[int] = None,
    tz_offset_minutes: int = Query(0, ge=-14 * 60, le=14 * 60, description="Browser's Date.getTimezoneOffset(), so streak days follow the student's local calendar"),
    db: Session = Depends(get_db)
):
    """
    Computes dashboard analytics:
    - Study streak (consecutive active days, counting quizzes and flashcard reviews)
    - Cards due today for SM-2 review
    - Overall accuracy and total attempts
    - Per-topic mastery percentages
    - Weak topics list (topics needing urgent review)
    - Quiz score timeline / history
    """
    now = get_utc_now()
    # getTimezoneOffset() is minutes *behind* UTC (Manila is -480), so subtract it
    local_delta = datetime.timedelta(minutes=-tz_offset_minutes)

    # 1. Base queries
    doc_filter = [QuizAttempt.document_id == document_id] if document_id else []
    fc_filter = [Flashcard.document_id == document_id] if document_id else []

    # 2. Cards Due Today
    cards_due_count = db.query(Flashcard).filter(*fc_filter, Flashcard.next_review <= now).count()
    total_cards = db.query(Flashcard).filter(*fc_filter).count()

    # 3. Quiz totals over every attempt, plus the 15 most recent for the history list
    total_quizzes, total_correct, total_questions_answered = db.query(
        func.count(QuizAttempt.id),
        func.coalesce(func.sum(QuizAttempt.score), 0),
        func.coalesce(func.sum(QuizAttempt.total_questions), 0),
    ).filter(*doc_filter).one()

    overall_accuracy = (
        round((total_correct / total_questions_answered) * 100, 1)
        if total_questions_answered > 0
        else 0.0
    )

    recent_attempts = (
        db.query(QuizAttempt).filter(*doc_filter).order_by(QuizAttempt.completed_at.desc()).limit(15).all()
    )
    history_list = []
    for att in recent_attempts:
        pct = round((att.score / att.total_questions) * 100, 1) if att.total_questions > 0 else 0.0
        completed = as_utc(att.completed_at)
        history_list.append({
            "id": att.id,
            "document_id": att.document_id,
            "document_title": att.document.title if att.document else "Module",
            "score": att.score,
            "total_questions": att.total_questions,
            "percentage": pct,
            "difficulty": att.difficulty or "medium",
            "completed_at": completed.isoformat() if completed else None
        })

    # 4. Per-Topic Mastery Breakdown, one aggregate query instead of one per topic
    answered_by_topic = dict(
        (topic_id, (total, correct))
        for topic_id, total, correct in db.query(
            Question.topic_id,
            func.count(QuestionAttempt.id),
            func.sum(case((QuestionAttempt.is_correct, 1), else_=0)),
        ).join(QuestionAttempt, QuestionAttempt.question_id == Question.id).group_by(Question.topic_id).all()
    )

    topic_query = db.query(Topic, Document.title).join(Document, Document.id == Topic.document_id)
    if document_id:
        topic_query = topic_query.filter(Topic.document_id == document_id)
    topics = topic_query.order_by(Document.created_at.desc(), Topic.order_index).all()

    topic_mastery_list = []
    weak_topics_list = []

    for t, doc_title in topics:
        total_ans, correct_ans = answered_by_topic.get(t.id, (0, 0))
        correct_ans = int(correct_ans or 0)
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
            "document_title": doc_title,
            "topic_title": t.title,
            "total_answered": total_ans,
            "correct_count": correct_ans,
            "mastery_percent": mastery_pct,
            "status": status_label
        }
        topic_mastery_list.append(item)

        if status_label in ["weak", "reviewing"]:
            weak_topics_list.append(item)

    # Tested weak spots first (lowest mastery); untested topics only fill remaining slots
    weak_topics_list.sort(key=lambda x: (x["mastery_percent"], -x["total_answered"]))
    if len(weak_topics_list) < 3:
        weak_topics_list += [t for t in topic_mastery_list if t["status"] == "untested"][: 3 - len(weak_topics_list)]

    # 5. Study Streak: any day with a quiz or a flashcard review, in the student's local calendar
    activity_times = [row[0] for row in db.query(QuizAttempt.completed_at).all()]
    activity_times += [row[0] for row in db.query(ReviewLog.reviewed_at).all()]
    active_dates = {(as_utc(t) + local_delta).date() for t in activity_times if t}
    streak = calculate_consecutive_days_streak(active_dates, today=(now + local_delta).date())

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

def calculate_consecutive_days_streak(active_dates: set, today: Optional[datetime.date] = None) -> int:
    """Calculates active daily streak up to today or yesterday."""
    if not active_dates:
        return 0

    today = today or get_utc_now().date()
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
