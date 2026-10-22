import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
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

