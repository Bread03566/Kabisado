import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import SessionLocal, ensure_schema
from app.routers import documents, summaries, flashcards, quizzes, flags, progress, chat, auth, admin, export, consent, exam
from app.security import retention
from app.services.ai_service import ai_service
from app.web import install_web

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("kabisado")

# Fail fast if the database is not at the latest migration (or create tables in dev/test mode).
ensure_schema()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enforce the 30-day retention promised in the privacy notice. A failure here must never stop the app.
    try:
        with SessionLocal() as db:
            removed = retention.purge_expired(db)
        logger.info("Retention purge removed %s", removed)
    except Exception:
        logger.exception("Retention purge failed; continuing startup")
    yield

def docs_urls(debug: bool) -> dict:
    """Interactive API docs and the schema are for development only; production does not publish its API map."""
    if debug:
        return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}
    return {"docs_url": None, "redoc_url": None, "openapi_url": None}


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for Kabisado - AI-Powered Study App (Study today, pass tomorrow)",
    lifespan=lifespan,
    **docs_urls(settings.DEBUG),
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,  # auth uses the Authorization header, so no ambient credentials
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Kabisado-Request"],
)

# Include routers
app.include_router(documents.router)
app.include_router(summaries.router)
app.include_router(flashcards.router)
app.include_router(quizzes.router)
app.include_router(flags.router)
app.include_router(progress.router)
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(export.router)
app.include_router(consent.router)
app.include_router(exam.router)


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ai_configured": ai_service.is_api_configured(),
        "ai_provider": "gemini" if ai_service.is_api_configured() else "offline",
        "ai_model": settings.GEMINI_MODEL if ai_service.is_api_configured() else None,
        "tagline": "Study today, pass tomorrow."
    }

if not Path(settings.STATIC_DIR, "index.html").is_file():  # with a built frontend, "/" is the app
    @app.get("/")
    def root():
        return {
            "message": "Welcome to Kabisado API.",
            "tagline": "Study today, pass tomorrow.",
            "docs_url": "/docs",
            "health": "/api/health"
        }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Full details go to the server log; the browser only gets a friendly message.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Oops, something went wrong on our side. Please try again.",
            "message": "Take a deep breath. You can try again."
        }
    )


# Must be last: its catch-all route would otherwise shadow routes registered after it.
install_web(app, settings.STATIC_DIR)
