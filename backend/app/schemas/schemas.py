from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any, Dict
from datetime import datetime

# ==================== Common / Microcopy ====================
class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None

# ==================== Topic Schemas ====================
class TopicBase(BaseModel):
    title: str
    content: str
    order_index: int = 0
    summary: Optional[str] = None

class TopicCreate(TopicBase):
    pass

class TopicResponse(TopicBase):
    id: int
    document_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ==================== Document Schemas ====================
class KeyTermItem(BaseModel):
    term: str
    definition: str

class DocumentCreateText(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    text: str = Field(..., min_length=20)

class DocumentListItem(BaseModel):
    id: int
    title: str
    file_type: str
    created_at: datetime
    topics_count: int = 0
    flashcards_count: int = 0
    questions_count: int = 0
    word_count: int = 0

    model_config = ConfigDict(from_attributes=True)

class DocumentDetailResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    title: str
    file_type: str
    raw_text: str
    summary_brief: Optional[str] = None
    summary_standard: Optional[str] = None
    summary_detailed: Optional[str] = None
    key_terms: Optional[List[KeyTermItem]] = None
    created_at: datetime
    topics: List[TopicResponse] = []

    model_config = ConfigDict(from_attributes=True)

# ==================== Summary Schemas ====================
class SummaryGenerateRequest(BaseModel):
    length: str = Field(default="standard", pattern="^(brief|standard|detailed)$")
    topic_id: Optional[int] = None

class SummaryResponse(BaseModel):
    summary: str
    length: str
    key_terms: List[KeyTermItem] = []

# ==================== Flashcard Schemas ====================
class FlashcardGenerateRequest(BaseModel):
    topic_id: Optional[int] = None
    count: int = Field(default=8, ge=1, le=30)
    card_type: Optional[str] = Field(default="mixed", pattern="^(term|qa|mixed)$")

class FlashcardCreate(BaseModel):
    document_id: int
    topic_id: Optional[int] = None
    front: str = Field(..., min_length=1)
    back: str = Field(..., min_length=1)
    card_type: str = "term"

class FlashcardUpdate(BaseModel):
    front: Optional[str] = None
    back: Optional[str] = None
    topic_id: Optional[int] = None
    card_type: Optional[str] = None

class FlashcardResponse(BaseModel):
    id: int
    document_id: int
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None
    front: str
    back: str
    card_type: str
    ease_factor: float
    interval: int
    repetitions: int
    next_review: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SM2ReviewRequest(BaseModel):
    rating: str = Field(..., pattern="^(again|hard|good|easy)$")

# ==================== Quiz Schemas ====================
class QuestionChoice(BaseModel):
    index: int
    text: str

class QuestionResponse(BaseModel):
    id: int
    document_id: int
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None
    question_text: str
    choices: List[str]
    correct_index: int
    explanation: str
    difficulty: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class QuizGenerateRequest(BaseModel):
    topic_id: Optional[int] = None
    count: int = Field(default=5, ge=1, le=25)
    difficulty: Optional[str] = Field(default="mixed", pattern="^(easy|medium|hard|mixed)$")

class QuestionAttemptInput(BaseModel):
    question_id: int
    selected_index: int

class QuizSubmitRequest(BaseModel):
    document_id: int
    topic_id: Optional[int] = None
    difficulty: Optional[str] = "mixed"
    answers: List[QuestionAttemptInput]

class QuestionResultDetail(BaseModel):
    question_id: int
    question_text: str
    choices: List[str]
    selected_index: int
    correct_index: int
    is_correct: bool
    explanation: str
    topic_title: Optional[str] = None

class QuizResultResponse(BaseModel):
    attempt_id: int
    score: int
    total_questions: int
    percentage: float
    grade_message: str
    roast_or_praise: str
    results: List[QuestionResultDetail]

# ==================== Flag Schemas ====================
class FlagCreate(BaseModel):
    target_type: str = Field(..., pattern="^(flashcard|question)$")
    target_id: int
    reason: str = Field(..., min_length=2, max_length=100)
    notes: Optional[str] = None

class FlagResponse(BaseModel):
    id: int
    target_type: str
    target_id: int
    reason: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
