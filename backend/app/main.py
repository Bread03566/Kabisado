import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import ensure_schema
from app.routers import documents, summaries, flashcards, quizzes, flags, progress, chat, auth
from app.services.ai_service import ai_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("kabisado")

# Fail fast if the database is not at the latest migration (or create tables in dev/test mode).
ensure_schema()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for Kabisado - AI-Powered Study App (Study today, pass tomorrow)",
    lifespan=lifespan
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
