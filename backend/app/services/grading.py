"""
Answer checking for every quiz question type. The quiz screen's instant feedback and the final
score both go through grade(), so they can never disagree.
"""
import difflib
import re
from typing import List, Optional

LEADING_ARTICLE = re.compile(r"^(?:the|a|an)\s+")

# Typed answers at least this long may differ by a small typo and still count
TYPO_MIN_LENGTH = 5
TYPO_SIMILARITY = 0.85


def normalize(text: Optional[str]) -> str:
    """Lowercase, drop punctuation and a leading article, collapse spaces."""
    cleaned = re.sub(r"[^\w\s]", " ", (text or "").lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return LEADING_ARTICLE.sub("", cleaned)


def accepted_answers(question) -> List[str]:
    data = question.answer_data or {}
    return [a for a in [data.get("answer", "")] + list(data.get("accepted_answers") or []) if a]


def matches_identification(answer: Optional[str], accepted: List[str]) -> bool:
    given = normalize(answer)
    if not given:
        return False
    for option in accepted:
        target = normalize(option)
        if not target:
            continue
        if given == target:
            return True
        if len(target) >= TYPO_MIN_LENGTH and difflib.SequenceMatcher(None, given, target).ratio() >= TYPO_SIMILARITY:
            return True
    return False


def grade(question, selected_index: Optional[int] = None, text_answer: Optional[str] = None, matching: Optional[List[int]] = None) -> bool:
    question_type = question.question_type or "multiple_choice"
    if question_type == "identification":
        return matches_identification(text_answer, accepted_answers(question))
    if question_type == "matching":
        pairs = (question.answer_data or {}).get("pairs") or []
        return bool(pairs) and matching is not None and list(matching) == list(range(len(pairs)))
    return selected_index is not None and selected_index == question.correct_index


def describe_correct(question) -> str:
    """The right answer in words, for feedback and the results review."""
    question_type = question.question_type or "multiple_choice"
    if question_type == "identification":
        answers = accepted_answers(question)
        return answers[0] if answers else ""
    if question_type == "matching":
        pairs = (question.answer_data or {}).get("pairs") or []
        return "; ".join(f"{p['term']} → {p['definition']}" for p in pairs)
    if 0 <= question.correct_index < len(question.choices or []):
        return question.choices[question.correct_index]
    return ""


def describe_response(question, selected_index: Optional[int], text_answer: Optional[str], matching: Optional[List[int]]) -> str:
    """The student's answer in words, for the results review."""
    question_type = question.question_type or "multiple_choice"
    if question_type == "identification":
        return text_answer.strip() if text_answer and text_answer.strip() else "No answer"
    if question_type == "matching":
        pairs = (question.answer_data or {}).get("pairs") or []
        if not matching:
            return "No answer"
        right = sum(1 for i, chosen in enumerate(matching) if chosen == i)
        return f"{right} of {len(pairs)} matched correctly"
    if selected_index is not None and 0 <= selected_index < len(question.choices or []):
        return question.choices[selected_index]
    return "No answer (Timeout)"
