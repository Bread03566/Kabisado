"""Exam Prep: what matters most, how well the student knows it, and a day-by-day plan. Fully offline."""
import math
import re
from typing import Any, Dict, List

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.models import Question, QuestionAttempt, QuizAttempt

DEFINITION_MARKERS = re.compile(r"\b(?:is|are|refers to|means|is defined as|was|were)\b", re.IGNORECASE)
UNTESTED_FACTOR = 0.8   # not yet tested counts as "mostly not known", but less urgent than proven weak
REVIEW_TOPICS = 3       # topics repeated on the final review day
WORDS_PER_MINUTE = 200


def topic_importance(topics: List[Dict[str, Any]]) -> Dict[int, float]:
    """0..1 per topic from how much of the material it covers and how many definitions it holds."""
    if not topics:
        return {}
    lengths = {t["id"]: len(t.get("content", "")) for t in topics}
    defs = {t["id"]: len(DEFINITION_MARKERS.findall(t.get("content", ""))) for t in topics}
    max_len, max_defs = max(lengths.values()) or 1, max(defs.values()) or 1
    raw = {i: 0.6 * lengths[i] / max_len + 0.4 * defs[i] / max_defs for i in lengths}
    top = max(raw.values()) or 1.0
    return {i: round(v / top, 4) for i, v in raw.items()}


def minutes_for(content: str) -> int:
    """Time to read a topic twice."""
    return max(5, math.ceil(len(content.split()) / WORDS_PER_MINUTE * 2))


def status_for(answered: int, pct: float) -> str:
    if answered == 0:
        return "untested"
    if pct >= 80:
        return "mastered"
    if pct >= 60:
        return "reviewing"
    return "weak"


def understanding(db: Session, user_id: int, topic_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """Answered and percentage correct per topic, from this student's own quiz history."""
    if not topic_ids:
        return {}
    rows = (
        db.query(Question.topic_id, func.count(QuestionAttempt.id),
                 func.sum(case((QuestionAttempt.is_correct, 1), else_=0)))
        .join(QuestionAttempt, QuestionAttempt.question_id == Question.id)
        .join(QuizAttempt, QuizAttempt.id == QuestionAttempt.attempt_id)
        .filter(QuizAttempt.user_id == user_id, Question.topic_id.in_(topic_ids))
        .group_by(Question.topic_id).all()
    )
    result: Dict[int, Dict[str, Any]] = {}
    for topic_id, total, correct in rows:
        pct = round(int(correct or 0) / total * 100, 1) if total else 0.0
        result[topic_id] = {"answered": total, "percentage": pct, "status": status_for(total, pct)}
    return result


def priority(importance: float, answered: int, pct: float) -> float:
    gap = UNTESTED_FACTOR if answered == 0 else 1 - pct / 100
    return round(importance * gap, 4)


def schedule(items: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    """Spread topics over the days, highest priority first; with two or more days the last is a review day."""
    ordered = sorted(items, key=lambda i: i["priority"], reverse=True)
    work_days = max(1, days - 1) if days >= 2 else 1
    per_day = math.ceil(len(ordered) / work_days) if ordered else 0
    plan: List[Dict[str, Any]] = []
    for n in range(work_days):
        chunk = [dict(i) for i in ordered[n * per_day:(n + 1) * per_day]]
        plan.append({"day": n + 1, "final_review": False, "topics": chunk,
                     "minutes": sum(i.get("minutes", 0) for i in chunk)})
    if days >= 2:
        review = [dict(i) for i in ordered[:REVIEW_TOPICS]]
        plan.append({"day": days, "final_review": True, "topics": review,
                     "minutes": 30 + sum(i.get("minutes", 0) for i in review) // 2})
    return plan


def readiness(percentage: float) -> str:
    return "Ready" if percentage >= 80 else "Almost there" if percentage >= 60 else "Needs work"
