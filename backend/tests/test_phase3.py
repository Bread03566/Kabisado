import io
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.models import Document
from tests.helpers import register_user
from tests.test_api import HISTORY_TEXT, docx_bytes


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def upload(client, headers, name, data, ctype="application/octet-stream"):
    return client.post("/api/documents/upload", headers=headers, files={"file": (name, data, ctype)})


def paste(client, headers, title="Notes", text=HISTORY_TEXT):
    return client.post("/api/documents/text", headers=headers, json={"title": title, "text": text})


# ---- originals are discarded after text extraction ----
def test_uploaded_originals_are_not_kept_on_disk_or_referenced(client):
    headers, _, _ = register_user(client)
    before = set(os.listdir(settings.UPLOAD_DIR))
    res = upload(client, headers, "../../escape.docx", docx_bytes(HISTORY_TEXT))
    assert res.status_code == 201 and res.json()["title"] == "escape"
    assert set(os.listdir(settings.UPLOAD_DIR)) == before
    with SessionLocal() as db:
        assert db.get(Document, res.json()["id"]).file_path is None


# ---- content checks, not just the extension ----
def test_a_pdf_name_with_docx_bytes_is_rejected(client):
    headers, _, _ = register_user(client)
    assert upload(client, headers, "fake.pdf", docx_bytes(HISTORY_TEXT)).status_code == 400


def test_a_docx_name_with_plain_text_bytes_is_rejected(client):
    headers, _, _ = register_user(client)
    assert upload(client, headers, "fake.docx", HISTORY_TEXT.encode()).status_code == 400


def test_a_zip_that_is_not_a_word_file_is_rejected(client):
    headers, _, _ = register_user(client)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "hi")
    assert upload(client, headers, "x.docx", buf.getvalue()).status_code == 400


def test_a_docx_that_expands_enormously_is_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "DOCX_MAX_UNCOMPRESSED_MB", 1)
    headers, _, _ = register_user(client)
    good = zipfile.ZipFile(io.BytesIO(docx_bytes(HISTORY_TEXT)))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for item in good.infolist():
            z.writestr(item.filename, good.read(item.filename))
        z.writestr("word/bomb.bin", b"\0" * (3 * 1024 * 1024))  # compresses to a few KB
    assert len(buf.getvalue()) < 100_000
    res = upload(client, headers, "bomb.docx", buf.getvalue())
    assert res.status_code == 400 and "too large once unpacked" in res.json()["detail"]


# ---- length cap ----
def test_pasted_and_uploaded_text_over_the_length_cap_is_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_TEXT_CHARS", 100)
    headers, _, _ = register_user(client)
    assert paste(client, headers).status_code == 413
    assert upload(client, headers, "long.docx", docx_bytes(HISTORY_TEXT)).status_code == 413


# ---- quotas ----
def test_per_student_document_limit_does_not_affect_other_students(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_DOCS_PER_USER", 1)
    a, _, _ = register_user(client)
    b, _, _ = register_user(client)
    assert paste(client, a).status_code == 201
    res = paste(client, a, "Second")
    assert res.status_code == 409 and "limit" in res.json()["detail"].lower()
    assert paste(client, b).status_code == 201


def test_per_student_storage_quota(client, monkeypatch):
    monkeypatch.setattr(settings, "STUDENT_TEXT_QUOTA_KB", 3)
    a, _, _ = register_user(client)
    assert paste(client, a).status_code == 201  # the sample is ~2 KB
    res = paste(client, a, "More", HISTORY_TEXT)
    assert res.status_code == 413 and "storage" in res.json()["detail"].lower()


def test_deleting_a_document_frees_quota(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_DOCS_PER_USER", 1)
    a, _, _ = register_user(client)
    first = paste(client, a).json()
    assert paste(client, a, "Again").status_code == 409
    assert client.delete(f"/api/documents/{first['id']}", headers=a).status_code == 200
    assert paste(client, a, "Again").status_code == 201


def test_new_content_is_refused_when_the_whole_database_budget_is_nearly_used(client, monkeypatch):
    monkeypatch.setattr(settings, "GLOBAL_TEXT_QUOTA_MB", 0)
    a, _, _ = register_user(client)
    res = paste(client, a)
    assert res.status_code == 503 and "full" in res.json()["detail"].lower()


# ---- export my data ----
def test_export_contains_only_my_data_and_no_secrets(client):
    a, a_name, _ = register_user(client, display_name="Ann Export")
    b, b_name, _ = register_user(client)
    mine = paste(client, a, "Mine").json()
    paste(client, b, "Theirs")
    res = client.get("/api/auth/export", headers=a)
    assert res.status_code == 200
    assert "attachment" in res.headers["content-disposition"]
    body = res.json()
    assert body["account"]["username"] == a_name and body["account"]["display_name"] == "Ann Export"
    assert [d["title"] for d in body["documents"]] == ["Mine"]
    assert body["documents"][0]["id"] == mine["id"] and body["documents"][0]["topics"]
    text = res.text
    assert b_name not in text and "Theirs" not in text
    for secret in ("password_hash", "recovery_hash", "refresh", "subject_ref"):
        assert secret not in text


def test_export_requires_login(client):
    assert client.get("/api/auth/export").status_code == 401
