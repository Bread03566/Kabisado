import datetime
import secrets
import uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean, JSON, CheckConstraint, true
from sqlalchemy.orm import relationship
from app.database import Base

def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)

def new_public_id() -> str:
    return str(uuid.uuid4())

def new_subject_ref() -> str:
    return secrets.token_hex(16)

class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('student', 'admin')", name="ck_users_role"),)

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String(36), unique=True, index=True, nullable=False, default=new_public_id)
    username = Column(String(100), unique=True, index=True, nullable=False)  # lower-case by application rule
    display_name = Column(String(60), nullable=False)
    password_hash = Column(Text, nullable=True)   # NULL for legacy client-id rows: they cannot log in
    recovery_hash = Column(Text, nullable=True)
    role = Column(String(10), nullable=False, default="student", server_default="student")
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    last_login_at = Column(DateTime, nullable=True)
    # Random pseudonymous reference for the later consent/audit logs; never derived from the user id.
    subject_ref = Column(String(32), unique=True, nullable=False, default=new_subject_ref)
    created_at = Column(DateTime, default=utc_now)

    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", cascade="all, delete-orphan", passive_deletes=True)


class UserSession(Base):
    """One refresh-token generation. Rotation creates a successor in the same family."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    family_id = Column(String(36), nullable=False, index=True)
    refresh_hash = Column(String(64), unique=True, nullable=False)  # sha256 of the token; plaintext never stored
    created_at = Column(DateTime, default=utc_now)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by = Column(Integer, nullable=True)
    rotated_at = Column(DateTime, nullable=True)
    user_agent_hash = Column(String(64), nullable=True)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    key = Column(String(64), primary_key=True)  # sha256(username|ip)
    count = Column(Integer, nullable=False, default=0)
    window_start = Column(DateTime, default=utc_now)
    locked_until = Column(DateTime, nullable=True)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)  # "pdf", "docx", "text"
    file_path = Column(String(500), nullable=True)
    raw_text = Column(Text, nullable=False)
    
    # Summaries cache
    summary_brief = Column(Text, nullable=True)
    summary_standard = Column(Text, nullable=True)
    summary_detailed = Column(Text, nullable=True)
    key_terms = Column(JSON, nullable=True)  # List of {"term": "...", "definition": "..."}
    
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="documents")
    topics = relationship("Topic", back_populates="document", cascade="all, delete-orphan", order_by="Topic.order_index")
    flashcards = relationship("Flashcard", back_populates="document", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="document", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="document", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    order_index = Column(Integer, default=0)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    document = relationship("Document", back_populates="topics")
    flashcards = relationship("Flashcard", back_populates="topic", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="topic", cascade="all, delete-orphan")


class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    card_type = Column(String(30), default="term")  # "term" or "qa"
    
    # SM-2 Spaced Repetition fields
    ease_factor = Column(Float, default=2.5)
    interval = Column(Integer, default=0)  # in days
    repetitions = Column(Integer, default=0)
    next_review = Column(DateTime, default=utc_now)
    
    created_at = Column(DateTime, default=utc_now)

    document = relationship("Document", back_populates="flashcards")
    topic = relationship("Topic", back_populates="flashcards")


class ReviewLog(Base):
    """One row per flashcard review, so study streaks count flashcard practice, not just quizzes."""
    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True, index=True)
    flashcard_id = Column(Integer, ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(String(10), nullable=False)
    reviewed_at = Column(DateTime, default=utc_now, index=True)


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    
    question_text = Column(Text, nullable=False)
    choices = Column(JSON, nullable=False)  # Multiple choice: 4 strings; true/false: ["True", "False"]; otherwise []
    correct_index = Column(Integer, nullable=False)  # Index into choices (0 for types without choices)
    explanation = Column(Text, nullable=False)
    difficulty = Column(String(20), default="medium")  # "easy", "medium", "hard"
    # "multiple_choice" | "true_false" | "identification" | "matching"
    question_type = Column(String(20), nullable=False, default="multiple_choice", server_default="multiple_choice")
    style = Column(String(20), nullable=True)  # "definition" | "situational"
    # identification: {"answer": str, "accepted_answers": [str]}; matching: {"pairs": [{"term", "definition"}]}
    answer_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=utc_now)

    document = relationship("Document", back_populates="questions")
    topic = relationship("Topic", back_populates="questions")
    attempts = relationship("QuestionAttempt", back_populates="question", cascade="all, delete-orphan")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    
    score = Column(Integer, nullable=False)
    total_questions = Column(Integer, nullable=False)
    difficulty = Column(String(20), nullable=True)
    completed_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="quiz_attempts")
    document = relationship("Document", back_populates="quiz_attempts")
    question_attempts = relationship("QuestionAttempt", back_populates="attempt", cascade="all, delete-orphan")


class QuestionAttempt(Base):
    __tablename__ = "question_attempts"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    
    selected_index = Column(Integer, nullable=False)  # -1 for types answered without choices
    response = Column(JSON, nullable=True)  # Typed answer or matching order, for non-choice questions
    is_correct = Column(Boolean, nullable=False)
    answered_at = Column(DateTime, default=utc_now)

    attempt = relationship("QuizAttempt", back_populates="question_attempts")
    question = relationship("Question", back_populates="attempts")


class Flag(Base):
    __tablename__ = "flags"

    id = Column(Integer, primary_key=True, index=True)
    target_type = Column(String(20), nullable=False)  # "flashcard" or "question"
    target_id = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    reason = Column(String(100), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
