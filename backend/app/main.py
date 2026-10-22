import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base, init_db, SessionLocal
from app.models.models import User
from app.routers import documents, summaries, flashcards, quizzes, flags, progress, chat
from app.services.ai_service import ai_service

# Ensure DB tables exist on launch
init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Ensure default user exists
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username="iskolar").first()
        if not user:
            user = User(username="iskolar", email="iskolar@kabisado.ph")
            db.add(user)
            db.commit()
    finally:
        db.close()

    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API para sa Kabisado - AI-Powered Study App (Aral ngayon, pasa bukas)",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents.router)
app.include_router(summaries.router)
app.include_router(flashcards.router)
app.include_router(quizzes.router)
app.include_router(flags.router)
app.include_router(progress.router)
app.include_router(chat.router)


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ai_configured": ai_service.is_api_configured(),
        "tagline": "Aral ngayon, pasa bukas."
    }

@app.get("/")
def root():
    return {
        "message": "Mabuhay! Welcome to Kabisado API.",
        "tagline": "Aral ngayon, pasa bukas.",
        "docs_url": "/docs",
        "health": "/api/health"
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": f"Ay, may kaunting topak ang system: {str(exc)}",
            "message": "Huminga nang malalim. Pwede mong subukan ulit."
        }
    )
