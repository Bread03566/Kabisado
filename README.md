# Kabisado 🦉 — Aral ngayon, pasa bukas.

> **Kabisado** (Tagalog for *"memorized"* or *"mastered"*) is an AI-powered study companion designed for students. Students upload their handouts, lecture notes, or modules, and Kabisado turns them into bite-sized summaries, interactive flashcards, and multiple-choice quizzes with instant grounded feedback.

---

## 🦉 Brand & Persona
- **Tagline**: *"Aral ngayon, pasa bukas."*
- **Vibe**: Relatable, funny, and dramatic like a student best friend who roasts you gently for procrastinating, then stays up all night to help you pass.
- **Microcopy**: Light Taglish interface touches (e.g., *"Wala ka pang module. Bukas na naman?"*, *"Hala siya, Dean's Lister yarn?! 🦉✨"*), paired with crystal-clear, serious academic explanations.
- **Mascot**: **Kabi**, the sleepy, caffeine-fueled owl who wears a nightcap or study glasses.

---

## 📁 Project Architecture & Folder Structure

```
Kabisado-project/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app initialization, CORS, lifespan & error handlers
│   │   ├── config.py            # App settings (Pydantic Settings)
│   │   ├── database.py          # SQLAlchemy SQLite connection with WAL mode & foreign keys
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── models.py        # ORM models (User, Document, Topic, Flashcard, Question, etc.)
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py       # Pydantic v2 validation models
│   │   ├── services/
│   │   │   ├── parser_service.py    # PDF (PyMuPDF), DOCX (python-docx), and text parsing
│   │   │   ├── segmenter_service.py # Topic extraction and academic heading chunking
│   │   │   └── ai_service.py        # Gemini client (with model fallback), JSON validation & offline engine
│   │   └── routers/
│   │       ├── documents.py     # Upload, paste, document CRUD
│   │       ├── summaries.py     # Brief, standard, detailed summaries + key terms
│   │       ├── flashcards.py    # Flashcard generation, CRUD, and SM-2 review
│   │       ├── quizzes.py       # Question generation, single-question flow, score reporting
│   │       └── flags.py         # Student feedback / reporting for bad cards or questions
│   ├── tests/
│   │   ├── test_services.py     # Parser & segmenter unit tests
│   │   └── test_api.py          # API route integration tests
│   ├── requirements.txt         # Backend Python dependencies
│   ├── pytest.ini               # Test configuration
│   ├── .env.example             # Template for environment variables
│   └── .env                     # Local environment variables
│
├── frontend/
│   ├── src/
│   │   ├── assets/              # Logos and SVG assets
│   │   ├── components/
│   │   │   ├── Navbar.jsx       # Brand header, view navigation, engine status modal
│   │   │   ├── Mascot.jsx       # Kabi the sleepy owl SVG with reactive mood states
│   │   │   ├── Toast.jsx        # Taglish notification system
│   │   │   └── FlagModal.jsx    # Modal for flagging problematic cards or questions
│   │   ├── views/
│   │   │   ├── UploadLibraryView.jsx   # Drag-and-drop upload, text paste & module cards
│   │   │   ├── DocumentView.jsx        # Summary switcher, interactive key terms & topics
│   │   │   ├── FlashcardStudyMode.jsx  # 3D card flip animation, SM-2 ratings & CRUD
│   │   │   └── QuizMode.jsx            # One-by-one questions, instant feedback & report
│   │   ├── services/
│   │   │   └── api.js           # Fetch API client
│   │   ├── App.jsx              # Main React container and routing
│   │   ├── main.jsx             # React entry point
│   │   └── index.css            # Tailwind CSS and 3D card utilities
│   ├── package.json
│   └── vite.config.js           # Vite config with Tailwind & proxy to backend
│
└── README.md
```

---

## 🗄️ Database Schema (SQLite / SQLAlchemy)

| Table | Description | Key Fields |
|---|---|---|
| `users` | Account (no email or phone) | `id`, `public_id`, `username`, `display_name`, `password_hash` (Argon2id), `recovery_hash`, `role` (`student`/`admin`), `is_active`, `last_login_at`, `subject_ref`, `created_at` |
| `sessions` | Refresh-token sessions (only a SHA-256 of the token is stored) | `id`, `user_id`, `family_id`, `refresh_hash`, `created_at`, `expires_at`, `revoked_at`, `rotated_at` |
| `login_attempts` | Login/recovery throttling | `key` (hash of username + IP), `count`, `window_start`, `locked_until` |
| `documents` | Uploaded modules / handouts | `id`, `user_id`, `title`, `file_type`, `file_path`, `raw_text`, `summary_brief`, `summary_standard`, `summary_detailed`, `key_terms`, `created_at` |
| `topics` | Topic sections of a document | `id`, `document_id`, `title`, `content`, `order_index`, `summary`, `created_at` |
| `flashcards` | Memory cards | `id`, `document_id`, `topic_id`, `front`, `back`, `card_type`, `ease_factor`, `interval`, `repetitions`, `next_review`, `created_at` |
| `questions` | Multiple-choice questions | `id`, `document_id`, `topic_id`, `question_text`, `choices` (JSON array of 4), `correct_index`, `explanation`, `difficulty`, `created_at` |
| `quiz_attempts` | Quiz submission record | `id`, `user_id`, `document_id`, `topic_id`, `score`, `total_questions`, `difficulty`, `completed_at` |
| `question_attempts`| Per-question answer history | `id`, `attempt_id`, `question_id`, `selected_index`, `is_correct`, `answered_at` |
| `flags` | Student reports on bad cards/questions | `id`, `target_type` (flashcard/question), `target_id`, `reason`, `notes`, `created_at` |
| `review_logs` | One row per flashcard review (feeds the study streak) | `id`, `flashcard_id`, `rating`, `reviewed_at` |

---

## 🔐 Accounts, Hosting & Operations

- **Accounts:** username + password (Argon2id) with a one-time recovery code. No email, phone or Gmail. Roles are `student` and `admin`, enforced on the server on every request. Admins are created only from the command line (`python -m app.cli create-admin`), never through the website.
- **Sessions:** a 15-minute access token kept in memory, plus a 7-day rotating refresh token in an HttpOnly, Secure, SameSite=Strict cookie.
- **Hosting (₱0):** one Render Free web service runs the API **and** serves the built React app (same origin, so the cookie is first-party). The database is Supabase Free Postgres. GitHub Pages only hosts a small wake-up page for the sleeping free instance.
- **Local development:** the Vite dev server proxies `/api` to the backend, and with `AUTO_CREATE_SCHEMA=true` and `COOKIE_SECURE=false` in `backend/.env` the backend creates its tables itself. Production uses Alembic migrations.
- **Runbook:** deploy order, secrets, creating the admin, rotating the signing key, retention and known limits are in [`docs/operations.md`](docs/operations.md).

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.12+**
- **Node.js 18+** and **npm**

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
copy .env.example .env

# Run backend development server
uvicorn app.main:app --reload --port 8000
```
> The API will be running at `http://localhost:8000` with Swagger docs available at `http://localhost:8000/docs`.

#### Setting Gemini API Key
> **Gemini is globally disabled by default** (`GEMINI_ENABLED=false`). Even with a key present, no request is sent to Google and every feature uses the offline engine. Do not enable it until the owner has verified the Google billing setup and reviewed Google's terms and age restrictions for the audience.

To enable it later, open `backend/.env`, set `GEMINI_ENABLED=true` and insert your Gemini API key (free from Google AI Studio):
```env
GEMINI_API_KEY="your-gemini-api-key"
GEMINI_MODEL="gemini-3.5-flash-lite"          # fast default
GEMINI_FALLBACK_MODELS="gemini-3.8-flash"     # tried when the main model is busy or slow
```
Each model gets `GEMINI_TIMEOUT_SECONDS` (default 60) before Kabisado moves to the next one. If no key is set, or every model fails, Kabisado uses its built-in offline engine, which builds summaries, flashcards, and quizzes straight from the module's own sentences.

> Google retires older models over time. If AI features stop working, check the backend log for a `404 NOT_FOUND` model error and update `GEMINI_MODEL`.

#### Running the backend in Docker (optional)
```bash
cd backend
docker compose up -d --build   # API on http://localhost:8000
docker compose logs -f         # watch logs
docker compose down            # stop (data is kept; `down -v` deletes it)
```
The database and uploads live in the `kabisado-data` Docker volume. `.env` is read when the container starts and is never copied into the image.

### 3. Frontend Setup
```bash
# In a new terminal, navigate to frontend directory
cd frontend

# Install packages
npm install

# Start Vite development server
npm run dev
```
> Open `http://localhost:5173` in your browser.

---

## 🧪 Running Tests

### Backend Tests
```bash
cd backend
.\.venv\Scripts\pytest -v
```
All unit tests and integration tests will run, verifying text extraction, topic segmentation, summary caching, flashcard generation, quiz submission, and error handling. Tests use a temporary database and upload folder with the AI switched off (see `tests/conftest.py`), so they never touch your real data or spend API quota.

### Frontend Build Verification
```bash
cd frontend
npm run build
```

---

## 📋 Roadmap & Completed Phases

- [x] **Phase 1 (MVP)**:
  - Project setup (React + Vite + Tailwind CSS + Python FastAPI + SQLite).
  - File upload & parsing: PDF (PyMuPDF), DOCX (python-docx), and plain text paste.
  - Automatic topic segmentation based on academic headings and structure.
  - Summarizer with length selector (*Mabilisan / Standard / Detalyado*) and key terms extraction.
  - Flashcard generator with interactive 3D flip card, full CRUD, and SM-2 spaced repetition rating.
  - Multiple-choice quiz generator (4 options, grounded explanations, difficulty selection).
  - Interactive quiz mode with instant feedback, explanation citing source, and humorous Taglish score reports.
  - Student flagging system for problematic cards or questions.
  - Grounded offline fallback engine ensuring 100% testability before entering API keys.

- [x] **Phase 2 (Topic Tagging & Progress Dashboard)**:
  - Computed per-topic mastery metrics (`mastery_percent = (correct / total) * 100`).
  - Study streak tracking (consecutive daily study activity).
  - Cards due today queue for SM-2 spaced repetition review.
  - Dynamic Weak Topics list highlighting subjects with < 70% mastery.
  - Progress dashboard UI with interactive topic mastery progress bars and quiz attempt history timeline.

- [x] **Phase 3 (Spaced Repetition Queue, Explainer Chat & Weak-Spot Quizzes)**:
  - Spaced Repetition Due Queue (`/api/flashcards/due`) with dedicated review mode.
  - **"Ask Kabisado" Explainer Chat**: Grounded Q&A with direct section citations, refusal to guess outside material, and "Explain like I'm new to this" (ELI5) analogy mode.
  - **Weak-Spot Quiz Generator**: 1-click button on dashboard and modules to automatically generate a targeted quiz focusing on the student's lowest-mastery topics.

- [x] **Phase 4 (Voice Mode, Study Plan & Timed Exam Mode)**:
  - **Voice Mode**: Web Speech API Text-to-Speech (reads flashcard fronts/backs and quiz questions aloud) and Speech Recognition (voice input for chat queries).
  - **Study Plan by Exam Date**: Interactive countdown calculator that builds a personalized day-by-day study roadmap based on target exam date and daily available hours.
  - **Exam Mode with Timer**: Timed quiz simulation (5m, 10m, 15m) with live countdown warning and automatic auto-submit on timeout.

