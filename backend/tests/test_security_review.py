import re

import pytest
from fastapi.testclient import TestClient

from app.main import app, docs_urls

# Routes that are meant to be reachable without a bearer token (each handles its own checks).
PUBLIC = {
    ("GET", "/api/health"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/refresh"),   # cookie + header + origin checks
    ("POST", "/api/auth/logout"),    # cookie based
    ("POST", "/api/auth/recover"),   # username + recovery code
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_interactive_api_docs_are_off_unless_debug():
    assert docs_urls(debug=False) == {"docs_url": None, "redoc_url": None, "openapi_url": None}
    assert docs_urls(debug=True) == {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


def test_every_api_route_rejects_anonymous_callers(client):
    checked = []
    for path, operations in app.openapi()["paths"].items():  # the schema lists every route, however it was included
        if not path.startswith("/api/"):
            continue
        for method in (m.upper() for m in operations):
            if (method, path) in PUBLIC:
                continue
            res = client.request(method, re.sub(r"\{[^}]+\}", "1", path))
            checked.append((method, path))
            assert res.status_code == 401, f"{method} {path} answered {res.status_code} without a login"
    assert len(checked) >= 40  # the sweep really covered the API


def test_unhandled_errors_do_not_leak_internals(client, monkeypatch):
    from app.routers import documents

    def boom(*a, **k):
        raise RuntimeError("SECRET-INTERNAL-DETAIL postgresql://user:pw@host/db")

    from tests.helpers import register_user
    headers, _, _ = register_user(client)
    monkeypatch.setattr(documents, "check_quota", boom)
    quiet = TestClient(app, raise_server_exceptions=False)
    res = quiet.post("/api/documents/text", headers=headers, json={"title": "t", "text": "x" * 60})
    assert res.status_code == 500
    assert "SECRET-INTERNAL-DETAIL" not in res.text and "postgresql://" not in res.text
