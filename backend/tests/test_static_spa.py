from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web import install_web

CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"


def make_app(static_dir):
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "healthy"}

    install_web(app, str(static_dir))
    return app


def site(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<!doctype html><title>Kabisado</title><div id=root></div>")


def test_root_and_client_routes_serve_the_app_with_security_headers(tmp_path):
    static = tmp_path / "site"
    static.mkdir()
    site(static)
    client = TestClient(make_app(static))
    for path in ("/", "/library", "/study/12/quiz"):
        res = client.get(path)
        assert res.status_code == 200 and "<div id=root>" in res.text, path
        assert res.headers["content-security-policy"] == CSP
        assert res.headers["x-content-type-options"] == "nosniff"
        assert res.headers["referrer-policy"] == "no-referrer"


def test_assets_are_served_and_are_not_given_the_html_csp(tmp_path):
    static = tmp_path / "site"
    static.mkdir()
    site(static)
    res = TestClient(make_app(static)).get("/assets/app.js")
    assert res.status_code == 200 and "console.log" in res.text
    assert res.headers["x-content-type-options"] == "nosniff"


def test_unknown_api_paths_are_json_404_never_the_app(tmp_path):
    static = tmp_path / "site"
    static.mkdir()
    site(static)
    client = TestClient(make_app(static))
    res = client.get("/api/nope")
    assert res.status_code == 404 and res.headers["content-type"].startswith("application/json")
    assert "<div" not in res.text
    assert client.get("/api/health").json() == {"status": "healthy"}


def test_api_responses_are_never_cached(tmp_path):
    static = tmp_path / "site"
    static.mkdir()
    site(static)
    client = TestClient(make_app(static))
    assert client.get("/api/health").headers["cache-control"] == "no-store"
    assert client.get("/api/nope").headers["cache-control"] == "no-store"


def test_path_traversal_cannot_escape_the_static_directory(tmp_path):
    static = tmp_path / "site"
    static.mkdir()
    site(static)
    (tmp_path / "secret.txt").write_text("not for the web")
    client = TestClient(make_app(static))
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt", "/assets/../../secret.txt"):
        res = client.get(path)
        assert "not for the web" not in res.text, path


def test_without_a_built_frontend_nothing_is_mounted_but_headers_still_apply(tmp_path):
    client = TestClient(make_app(tmp_path / "missing"))
    assert client.get("/").status_code == 404
    assert client.get("/api/health").headers["cache-control"] == "no-store"


def test_the_real_app_marks_api_responses_no_store():
    from app.main import app
    res = TestClient(app).get("/api/health")
    assert res.headers["cache-control"] == "no-store" and res.headers["x-content-type-options"] == "nosniff"
