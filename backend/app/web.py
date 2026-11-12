"""Same-origin hosting: the API also serves the built React app, so the refresh cookie is first-party,
and adds the security headers every response should carry."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
NO_CSP_PATHS = ("/docs", "/redoc")  # the interactive API docs load assets from a CDN


def install_web(app: FastAPI, static_dir: str) -> bool:
    """Add security headers (always) and serve the built frontend if `static_dir/index.html` exists.
    Returns True when the frontend is mounted."""

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if response.headers.get("content-type", "").startswith("text/html") and not request.url.path.startswith(NO_CSP_PATHS):
            response.headers["Content-Security-Policy"] = CSP
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    root = Path(static_dir).resolve()
    index = root / "index.html"
    if not index.is_file():
        return False

    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root):  # favicon, manifest, ...
            return FileResponse(candidate)
        return FileResponse(index)

    return True
