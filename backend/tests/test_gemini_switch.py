"""Gemini must be off unless GEMINI_ENABLED is true, whatever else is configured."""
import asyncio

import pytest

from app.config import settings
from app.services.ai_service import AIService

TEXT = (
    "Photosynthesis is the process by which plants convert light energy into chemical energy. "
    "Chlorophyll is the green pigment that absorbs sunlight. "
    "Glucose is the sugar produced during photosynthesis."
)


class ExplodingClient:
    """Stands in for a Gemini client; any use is a privacy violation."""

    def __getattr__(self, name):
        raise AssertionError(f"Gemini client was touched ({name}) while GEMINI_ENABLED is false")


def test_disabled_by_default_even_with_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_ENABLED", False)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "real-looking-key")
    svc = AIService()
    assert svc.client is None
    assert svc.is_api_configured() is False


def test_enabled_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_ENABLED", True)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert AIService().is_api_configured() is False


def test_enabled_with_key_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_ENABLED", True)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "real-looking-key")
    assert AIService().is_api_configured() is True


def test_no_network_when_disabled_even_if_a_client_exists(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_ENABLED", False)
    svc = AIService()
    svc.client = ExplodingClient()  # simulates a client created by some other path

    summary = asyncio.run(svc.generate_summary("Bio", TEXT, "brief"))
    cards = asyncio.run(svc.generate_flashcards("Bio", "Photosynthesis", TEXT, topic_id=1, count=2))
    quiz = asyncio.run(svc.generate_quiz_questions("Bio", "Photosynthesis", TEXT, topic_id=1, count=2))
    chat = asyncio.run(svc.answer_document_question(
        "Bio", [{"id": 1, "title": "Photosynthesis", "content": TEXT}], "What is chlorophyll?"))

    assert summary and isinstance(cards, list) and isinstance(quiz, list) and "answer" in chat


def test_direct_gemini_call_is_refused_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_ENABLED", False)
    svc = AIService()
    svc.client = ExplodingClient()
    with pytest.raises(RuntimeError):
        asyncio.run(svc._call_gemini_json("system", "user"))
