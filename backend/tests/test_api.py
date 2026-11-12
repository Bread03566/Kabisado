import pytest
from fastapi.testclient import TestClient
from app.main import app
from tests.helpers import register_user


def signed_in_client(**kwargs):
    """A TestClient for a freshly registered student (use as a context manager)."""
    c = TestClient(app, **kwargs)
    headers, _, _ = register_user(c)
    c.headers.update(headers)
    return c


@pytest.fixture(scope="module")
def client():
    with signed_in_client() as c:
        yield c

def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "Kabisado" in data["app"]

def test_create_document_text_and_flows(client):
    text_payload = {
        "title": "Introduction to Rizal and Philippine Nationalism",
        "text": (
            "Chapter 1: The Life of Jose Rizal\n"
            "Jose Rizal was born on June 19, 1861 in Calamba, Laguna. He is the national hero of the Philippines. "
            "Propaganda Movement was an organization of Filipino expatriates in Europe demanding civil rights.\n\n"
            "Chapter 2: The Novels of Rizal\n"
            "Noli Me Tangere was published in 1887 in Berlin, exposing the abuses of the Spanish friars. "
            "El Filibusterismo is the sequel published in Ghent in 1891 with a darker, more revolutionary theme."
        )
    }

    # 1. Create document
    create_res = client.post("/api/documents/text", json=text_payload)
    assert create_res.status_code == 201
    doc_data = create_res.json()
    doc_id = doc_data["id"]
    assert doc_data["title"] == text_payload["title"]
    assert len(doc_data["topics"]) >= 2

    # 2. Get documents list
    list_res = client.get("/api/documents")
    assert list_res.status_code == 200
    docs = list_res.json()
    assert any(d["id"] == doc_id for d in docs)

    # 3. Generate summary
    sum_res = client.post(f"/api/documents/{doc_id}/summarize", json={"length": "standard"})
    assert sum_res.status_code == 200
    sum_data = sum_res.json()
    assert "summary" in sum_data
    assert len(sum_data["summary"]) > 0

    # 4. Generate flashcards
    fc_res = client.post(f"/api/documents/{doc_id}/flashcards/generate", json={"count": 4})
    assert fc_res.status_code == 200
    cards = fc_res.json()
    assert len(cards) > 0
    first_card_id = cards[0]["id"]

    # 5. Review flashcard SM-2
    sm2_res = client.post(f"/api/flashcards/{first_card_id}/review", json={"rating": "good"})
    assert sm2_res.status_code == 200
    assert sm2_res.json()["repetitions"] >= 1

    # 6. Generate quiz
    quiz_res = client.post(f"/api/documents/{doc_id}/quiz/generate", json={"count": 2, "difficulty": "medium"})
    assert quiz_res.status_code == 200
    questions = quiz_res.json()
    assert len(questions) > 0

    # 7. Submit quiz attempt
    q_id = questions[0]["id"]
    c_idx = questions[0]["correct_index"]
    submit_res = client.post("/api/quizzes/submit", json={
        "document_id": doc_id,
        "difficulty": "medium",
        "answers": [{"question_id": q_id, "selected_index": c_idx}]
    })
    assert submit_res.status_code == 200
    score_report = submit_res.json()
    assert score_report["score"] == 1
    assert score_report["percentage"] == 100.0

    # 8. Flag card
    flag_res = client.post("/api/flags", json={
        "target_type": "flashcard",
        "target_id": first_card_id,
        "reason": "Maling spelling ng term"
    })
    assert flag_res.status_code == 201

    # 9. Due flashcards endpoint
    due_res = client.get("/api/flashcards/due")
    assert due_res.status_code == 200

    # 10. Dashboard progress stats
    dash_res = client.get("/api/progress/dashboard")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert "streak_days" in dash_data
    assert "topic_mastery" in dash_data
    assert len(dash_data["quiz_history"]) > 0

    # 11. Explainer Chat (Ask Kabisado)
    chat_res = client.post(f"/api/documents/{doc_id}/chat", json={
        "question": "Sino si Jose Rizal?",
        "explain_like_new": True
    })
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert len(chat_data["answer"]) > 0
    assert chat_data["found_in_document"] is True

    # 12. Weak-spot Quiz
    weak_res = client.post(f"/api/documents/{doc_id}/quiz/weak-spots")
    assert weak_res.status_code == 200
    weak_questions = weak_res.json()
    assert len(weak_questions) > 0



HISTORY_TEXT = "\n\n".join(
    f"Chapter {i}: Events of {1880 + i}\n"
    f"In {1880 + i} the Propaganda Movement in Madrid published new essays about reform. "
    f"The writers met in Barcelona and Madrid to plan petitions to the Spanish Cortes. "
    f"Graciano Lopez Jaena and Marcelo del Pilar led many of these meetings in {1880 + i}."
    for i in range(1, 7)
)


def make_doc(client, title="History Module", text=HISTORY_TEXT):
    res = client.post("/api/documents/text", json={"title": title, "text": text})
    assert res.status_code == 201
    return res.json()


def docx_bytes(text: str) -> bytes:
    import io
    from docx import Document as DocxDocument
    d = DocxDocument()
    for paragraph in text.split("\n\n"):
        d.add_paragraph(paragraph)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_upload_rejects_files_over_the_size_limit(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0)
    res = client.post("/api/documents/upload", files={"file": ("big.docx", docx_bytes(HISTORY_TEXT), "application/octet-stream")})
    assert res.status_code == 413


def test_quiz_and_flashcard_counts_respect_the_request(client):
    doc = make_doc(client)
    assert len(doc["topics"]) == 6

    questions = client.post(f"/api/documents/{doc['id']}/quiz/generate", json={"count": 3}).json()
    assert 1 <= len(questions) <= 3

    cards = client.post(f"/api/documents/{doc['id']}/flashcards/generate", json={"count": 4}).json()
    assert 1 <= len(cards) <= 4


def test_regenerate_summary_bypasses_cache(client, monkeypatch):
    from app.services import ai_service as ai_module
    doc = make_doc(client)
    calls = []

    async def fake_summary(document_title, text_content, length="standard"):
        calls.append(length)
        return {"summary": f"Summary #{len(calls)}", "key_terms": [{"term": "Cortes", "definition": "The Spanish parliament."}]}

    monkeypatch.setattr(ai_module.ai_service, "generate_summary", fake_summary)
    url = f"/api/documents/{doc['id']}/summarize"
    assert client.post(url, json={"length": "brief"}).json()["summary"] == "Summary #1"
    assert client.post(url, json={"length": "brief"}).json()["summary"] == "Summary #1"  # cached
    assert client.post(url, json={"length": "brief", "force": True}).json()["summary"] == "Summary #2"


def test_dashboard_counts_every_attempt_and_flashcard_reviews(client):
    doc = make_doc(client)
    question = client.post(f"/api/documents/{doc['id']}/quiz/generate", json={"count": 1}).json()[0]
    before = client.get("/api/progress/dashboard").json()["total_quizzes_taken"]
    for _ in range(16):
        client.post("/api/quizzes/submit", json={
            "document_id": doc["id"],
            "answers": [{"question_id": question["id"], "selected_index": question["correct_index"]}],
        })
    dash = client.get("/api/progress/dashboard", params={"tz_offset_minutes": -480}).json()
    assert dash["total_quizzes_taken"] == before + 16
    assert len(dash["quiz_history"]) == 15
    assert dash["quiz_history"][0]["completed_at"].endswith("+00:00")
    assert dash["streak_days"] >= 1
    assert all("document_title" in t for t in dash["topic_mastery"])


def test_streak_counts_flashcard_reviews():
    import datetime
    from app.routers.progress import calculate_consecutive_days_streak
    today = datetime.date(2026, 10, 23)
    days = {today, today - datetime.timedelta(days=1), today - datetime.timedelta(days=3)}
    assert calculate_consecutive_days_streak(days, today=today) == 2


def test_submit_ignores_questions_from_other_documents(client):
    doc_a = make_doc(client, title="Doc A")
    doc_b = make_doc(client, title="Doc B")
    q_b = client.post(f"/api/documents/{doc_b['id']}/quiz/generate", json={"count": 1}).json()[0]
    res = client.post("/api/quizzes/submit", json={
        "document_id": doc_a["id"],
        "answers": [{"question_id": q_b["id"], "selected_index": q_b["correct_index"]}],
    })
    assert res.status_code == 400


def test_unexpected_errors_do_not_leak_details(monkeypatch):
    from fastapi.testclient import TestClient
    from app.services import ai_service as ai_module

    async def boom(*args, **kwargs):
        raise RuntimeError("internal secret path C:/server/db")

    monkeypatch.setattr(ai_module.ai_service, "answer_document_question", boom)
    with signed_in_client(raise_server_exceptions=False) as c:
        doc = make_doc(c)
        res = c.post(f"/api/documents/{doc['id']}/chat", json={"question": "Who led the meetings?"})
    assert res.status_code == 500
    assert "secret" not in res.text


def test_mixed_quiz_has_every_question_type_and_grades_each(client):
    doc = make_doc(client, title="Mixed Types")
    res = client.post(f"/api/documents/{doc['id']}/quiz/generate", json={"count": 8, "question_type": "mixed", "style": "definition"})
    assert res.status_code == 200
    questions = res.json()
    types = {q["question_type"] for q in questions}
    assert {"multiple_choice", "identification", "true_false", "matching"} <= types, types

    def correct_answer(q):
        if q["question_type"] == "identification":
            return {"text_answer": q["answer_data"]["answer"].upper() + "!"}  # case and punctuation don't matter
        if q["question_type"] == "matching":
            return {"matching": list(range(len(q["answer_data"]["pairs"])))}
        return {"selected_index": q["correct_index"]}

    answers = [{"question_id": q["id"], **correct_answer(q)} for q in questions]
    report = client.post("/api/quizzes/submit", json={"document_id": doc["id"], "answers": answers}).json()
    assert report["score"] == len(questions)
    assert all(r["your_answer"] and r["correct_answer"] for r in report["results"])


def test_check_endpoint_forgives_typos_in_typed_answers(client):
    doc = make_doc(client, title="Identification")
    q = client.post(f"/api/documents/{doc['id']}/quiz/generate", json={"count": 1, "question_type": "identification"}).json()[0]
    answer = q["answer_data"]["answer"]
    typo = answer[:-2] + answer[-1] + answer[-2] if len(answer) >= 6 else answer
    good = client.post("/api/quizzes/check", json={"question_id": q["id"], "text_answer": typo}).json()
    assert good["is_correct"] is True
    bad = client.post("/api/quizzes/check", json={"question_id": q["id"], "text_answer": "definitely wrong"}).json()
    assert bad["is_correct"] is False
    assert bad["correct_answer"] == answer


def test_each_student_only_sees_their_own_documents():
    with signed_in_client() as alice, signed_in_client() as bob:
        doc = make_doc(alice, title="Alice private notes")
        card = alice.post("/api/flashcards", json={"document_id": doc["id"], "front": "Q", "back": "A", "card_type": "term"})
        assert card.status_code == 201
        card_id = card.json()["id"]

        assert doc["id"] in [d["id"] for d in alice.get("/api/documents").json()]
        assert doc["id"] not in [d["id"] for d in bob.get("/api/documents").json()]

        doc_id = doc["id"]
        assert bob.get(f"/api/documents/{doc_id}").status_code == 404
        assert bob.delete(f"/api/documents/{doc_id}").status_code == 404
        assert bob.post(f"/api/documents/{doc_id}/chat", json={"question": "What is this?"}).status_code == 404
        assert bob.post(f"/api/documents/{doc_id}/summarize", json={"length": "brief"}).status_code == 404
        assert bob.get(f"/api/documents/{doc_id}/flashcards").status_code == 404
        assert bob.get(f"/api/documents/{doc_id}/questions").status_code == 404
        assert bob.post(f"/api/documents/{doc_id}/quiz/generate", json={"count": 2}).status_code == 404
        assert bob.get(f"/api/flashcards/due?document_id={doc_id}").json() == []
        assert bob.put(f"/api/flashcards/{card_id}", json={"front": "hacked"}).status_code == 404
        assert bob.post(f"/api/flashcards/{card_id}/review", json={"rating": "good"}).status_code == 404
        assert bob.delete(f"/api/flashcards/{card_id}").status_code == 404
        assert bob.post("/api/flags", json={"target_type": "flashcard", "target_id": card_id, "reason": "wrong"}).status_code == 404
        assert bob.get("/api/progress/dashboard").json()["total_cards"] == 0
        assert bob.get(f"/api/progress/dashboard?document_id={doc_id}").status_code == 404

        # Alice is unaffected by Bob's attempts
        assert alice.get(f"/api/documents/{doc_id}").status_code == 200
        assert alice.get("/api/progress/dashboard").json()["total_cards"] >= 1


def test_anonymous_requests_are_rejected_but_health_is_open():
    with TestClient(app) as anon:
        assert anon.get("/api/documents").status_code == 401
        assert anon.get("/api/health").status_code == 200
