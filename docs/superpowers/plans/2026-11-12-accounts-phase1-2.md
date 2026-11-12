# Kabisado Phases 1–2 (Foundation + Accounts) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing FastAPI app safe to deploy on Supabase Postgres with real student accounts (username + password + recovery code), roles, rotating sessions, an admin created only by CLI, and same-origin hosting on Render, with Gemini hard-disabled.

**Architecture:** Keep the existing routers; change identity from the `X-Client-Id` header to bearer access tokens (15 min, in memory) plus a rotating HttpOnly `__Host-` refresh cookie. `app/identity.py` keeps its public names (`get_current_user`, `get_owned_document`) so routers barely change; it gains `require_student` / `require_admin`. Schema is owned by Alembic, run manually before deploy; the app only checks the revision at startup. FastAPI serves the built React app so cookies are first-party.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, psycopg 3, argon2-cffi, PyJWT, pytest; React/Vite, vitest (auth client only); Docker; GitHub Actions; Supabase Free Postgres; Render Free.

**Spec:** `docs/superpowers/specs/2026-11-12-kabisado-architecture-design.md` (§6, §7, §8 users/sessions, §12, §21, §22) and `docs/superpowers/specs/2026-11-12-phase0-report.md` (§B2). Out of scope here: Storage/uploads changes, consent log and ConsentGate, admin dashboard, retrieval, adaptive learning, gamification.

## Global Constraints

- Budget is ₱0/month. No paid service, trial, or card. Nothing here may add a dependency on one.
- **Gemini stays globally disabled.** `GEMINI_ENABLED` defaults to `false`; with it false no code path may call Gemini even if `GEMINI_API_KEY` is set.
- Passwords: Argon2id, `time_cost=2`, `memory_cost=19456` KiB, `parallelism=1`, hashing in a threadpool behind a semaphore of 2; min length 10, max 128; never log or return them.
- Username: 3–32 chars, `[a-z0-9_.]`, case-folded, unique. No email, phone, or role field at registration.
- Recovery code: 128-bit random, shown once, stored only as an Argon2id hash; recovery rotates the code and revokes all sessions. Admins can never reset passwords or read codes.
- Access token: JWT HS256, 15 min, `sub`=user id, `sid`=session id, `kid`; role is read from the DB row, not the token. Refresh token: opaque random, 7 days, only its SHA-256 stored, rotated on use, 10 s grace window, reuse after grace revokes the whole family.
- Refresh cookie: `HttpOnly; Secure; SameSite=Strict; Path=/`, name `__Host-kabisado_rt` (plain `kabisado_rt` and not Secure only when `COOKIE_SECURE=false` for local http dev).
- Non-owner access to any resource returns 404. Request schemas that touch accounts use `extra="forbid"`; no API lets a user set `role`, `is_active`, or `subject_ref`.
- CORS: explicit origin list, `allow_credentials=False`, no `*`. `DEBUG` defaults to `false`.
- DB: persistent small pool (`pool_size=3`, `max_overflow=2`, `pool_pre_ping=True`); a new connection costs ~1.4 s on Render→Supabase, so never open one per request. Keep per-request query count low.
- Migrations: Alembic only; run `alembic upgrade head` **before** deploying; the app refuses to start on a revision mismatch. `MAX_UPLOAD_MB` becomes 10.
- Logs must not contain passwords, tokens, recovery codes, or document text.
- Backend tests must pass on SQLite (fast) and on Postgres 17 in CI. Python is not installed on the dev machine; use Docker (Task 0).

## Review Focus

1. **Username collisions and Unicode**: `Ana`, `ANA`, full-width `ａｎａ`, trailing spaces → normalized or rejected, never two accounts (tested in Task 9).
2. **Huge or hostile password input**: 129-char password or multi-MB body → 422 before any hashing (Task 5, Task 9).
3. **Concurrent registration of one username**: exactly one 201, the other 409, never a 500 (Task 9).
4. **Garbage/expired/missing refresh cookie and tokens for deactivated users** → 401, never 500, never a new session (Tasks 8, 9, 12).
5. **Two tabs refreshing at once**: both succeed inside the 10 s grace window; replay after the window revokes the family (Task 8).

---

### Task 0: Test runner and branch setup

**Files:**
- Create: `backend/Dockerfile.test`, `backend/scripts/test.sh`, `backend/scripts/test_pg.sh`
- Modify: `backend/requirements.txt` (add `alembic>=1.13`, `psycopg[binary]>=3.2`, `argon2-cffi>=23.1`, `PyJWT>=2.8`)

**Interfaces:**
- Produces: `bash backend/scripts/test.sh [pytest args]` (SQLite) and `bash backend/scripts/test_pg.sh [pytest args]` (throwaway Postgres 17 container + `alembic upgrade head`), used by every later task's "run" step.

- [ ] **Step 1:** Create branch `feat/accounts` from `main`, then `git cherry-pick d24743b` so the spec docs travel with it (docs-only commit). Commit this plan on the branch.
- [ ] **Step 2:** Write `Dockerfile.test` (python:3.12-slim, copies `requirements.txt`, pip installs), and `test.sh` that builds `kabisado-backend-test` (cached) and runs `docker run --rm -v "$PWD":/app -w /app -e MSYS_NO_PATHCONV=1 kabisado-backend-test python -m pytest "$@"`. `test_pg.sh` starts `postgres:17` on a private network, exports `DATABASE_URL`, runs `alembic upgrade head` then pytest, and removes containers on exit.
- [ ] **Step 3:** Run `bash backend/scripts/test.sh -q`. Expected: the existing suite passes unchanged (baseline).
- [ ] **Step 4: Commit** `chore: docker test runner and backend deps`.

### Task 1: Hard-disable Gemini behind `GEMINI_ENABLED`

**Files:**
- Modify: `backend/app/config.py` (add `GEMINI_ENABLED: bool = False`), `backend/app/services/ai_service.py` (`AIService.is_api_configured`, line 159)
- Test: `backend/tests/test_gemini_switch.py`

**Interfaces:**
- Produces: `settings.GEMINI_ENABLED: bool`; `AIService.is_api_configured() -> bool` returns true only if `GEMINI_ENABLED` **and** a key is present.

- [ ] **Step 1: Write failing tests.** `test_disabled_by_default_even_with_key`: construct `AIService` with `GEMINI_API_KEY="x"` and `GEMINI_ENABLED=False` → `is_api_configured() is False`. `test_no_network_when_disabled`: monkeypatch `AIService._call_model_json` to raise `AssertionError`; call `generate_summary`, `generate_flashcards`, `generate_quiz_questions`, `answer_document_question` (async, via `asyncio.run`) with a short text → all return offline results without raising. `test_enabled_requires_key`: enabled + empty key → False.
- [ ] **Step 2:** Run `bash backend/scripts/test.sh tests/test_gemini_switch.py -v`. Expected: FAIL (first test).
- [ ] **Step 3:** Implement the gate in `is_api_configured`. Also update `/api/health` in `main.py` to report `ai_provider: "offline"` unless configured.
- [ ] **Step 4:** Run the file, then the whole suite. Expected: PASS.
- [ ] **Step 5: Commit** `fix: Gemini disabled unless GEMINI_ENABLED (privacy default)`.

### Task 2: Config hardening and CORS lock-down

**Files:**
- Modify: `backend/app/config.py`, `backend/app/main.py` (CORS block), `backend/.env.example`
- Test: `backend/tests/test_config_cors.py`

**Interfaces:**
- Produces on `Settings`: `DEBUG=False`, `ALLOWED_ORIGINS: str = "http://localhost:5173"`, property `allowed_origins -> list[str]`, `JWT_SECRET: str`, `JWT_SECRET_PREVIOUS: Optional[str]`, `ACCESS_TOKEN_MINUTES=15`, `REFRESH_TOKEN_DAYS=7`, `COOKIE_SECURE=True`, `ARGON2_MEMORY_KIB=19456`, `ARGON2_TIME_COST=2`, `DB_POOL_SIZE=3`, `DB_MAX_OVERFLOW=2`, `MAX_UPLOAD_MB=10`, `AUTO_CREATE_SCHEMA=False`. `JWT_SECRET` has no default; a validator rejects values shorter than 32 chars unless `DEBUG` is true.

- [ ] **Step 1: Write failing tests.** `test_cors_rejects_unlisted_origin`: preflight `OPTIONS /api/health` with `Origin: https://evil.example` → no `access-control-allow-origin`. `test_cors_allows_listed_origin`. `test_credentials_not_allowed`: `access-control-allow-credentials` absent. `test_short_jwt_secret_rejected_when_not_debug`.
- [ ] **Step 2:** Run; Expected FAIL.
- [ ] **Step 3:** Implement; set `allow_origins=settings.allowed_origins`, `allow_credentials=False`, methods `GET POST PUT DELETE OPTIONS`, headers `Authorization, Content-Type, X-Kabisado-Request`. Update `conftest.py` to set `JWT_SECRET` (test value of 32+ chars), `ARGON2_MEMORY_KIB=1024`, `ARGON2_TIME_COST=1`, `AUTO_CREATE_SCHEMA=true`, `DEBUG=true` via `os.environ.setdefault` before importing `app`.
- [ ] **Step 4:** Full suite passes. **Step 5: Commit** `fix: explicit CORS origins, safe config defaults`.

### Task 3: Postgres engine support with a persistent pool

**Files:**
- Modify: `backend/app/database.py`, `backend/app/config.py` (URL normalizer)
- Test: `backend/tests/test_database_url.py`

**Interfaces:**
- Produces: `normalize_database_url(url: str) -> str` mapping `postgres://` and `postgresql://` to `postgresql+psycopg://`, leaving `sqlite:` and already-qualified URLs unchanged. `engine` uses `QueuePool(pool_size, max_overflow, pool_pre_ping=True, pool_recycle=300)` for Postgres and SQLite args unchanged.

- [ ] **Step 1:** Write failing tests for `normalize_database_url` (four inputs) and `test_postgres_pool_settings` (build an engine from a dummy `postgresql+psycopg://u:p@h/db` URL with `create_engine` not connecting; assert `engine.pool.size() == 3`).
- [ ] **Step 2:** Run; FAIL. **Step 3:** Implement; extract an `build_engine(url) -> Engine` function so the test can call it. **Step 4:** Suite passes. **Step 5: Commit** `feat: Postgres engine with pooled connections`.

### Task 4: Alembic baseline, startup revision check, CI on Postgres

**Files:**
- Create: `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/versions/0001_baseline.py`, `.github/workflows/backend-tests.yml`
- Modify: `backend/app/database.py` (`init_db` → `ensure_schema`), `backend/app/main.py`
- Test: `backend/tests/test_migrations.py`

**Interfaces:**
- Produces: `ensure_schema() -> None`: if `settings.AUTO_CREATE_SCHEMA` then `Base.metadata.create_all`; otherwise raises `RuntimeError("Database schema is at revision X, expected Y. Run: alembic upgrade head")` when the current Alembic revision differs from head. `add_missing_columns` is deleted. Migrations read `DATABASE_URL` from `app.config.settings`.

- [ ] **Step 1: Write failing tests.** `test_upgrade_head_matches_models` (temp SQLite file; run `alembic upgrade head` via `alembic.command`; compare table and column names to `Base.metadata`; assert every model column exists), `test_ensure_schema_fails_on_empty_db_without_autocreate`, `test_ensure_schema_ok_after_upgrade`.
- [ ] **Step 2:** Run; FAIL.
- [ ] **Step 3:** Generate the baseline from the current models with `alembic revision --autogenerate -m baseline` (review the output; use batch-mode-safe operations). Implement `ensure_schema`; `main.py` calls it once (remove the duplicate import-time and lifespan `init_db`).
- [ ] **Step 4:** Write `backend-tests.yml`: `ubuntu-latest`, `postgres:17` service, `pip install -r backend/requirements.txt`, `alembic upgrade head`, `pytest` with `DATABASE_URL` and `AUTO_CREATE_SCHEMA=false`; and a second step running the same on SQLite. Run `bash backend/scripts/test_pg.sh -q`. Expected: suite passes on Postgres.
- [ ] **Step 5: Commit** `feat: Alembic baseline, fail-fast schema check, Postgres CI`.

### Task 5: Password policy and hashing service

**Files:**
- Create: `backend/app/security/__init__.py`, `backend/app/security/passwords.py`, `backend/app/security/common_passwords.txt` (~200 common passwords)
- Test: `backend/tests/test_passwords.py`

**Interfaces:**
- Produces: `validate_password(password: str, username: str) -> None` (raises `ValueError` with a user-facing message for: <10 chars, >128 chars, in common list, equals username); `async hash_password(password: str) -> str`; `async verify_password(hash_: str | None, password: str) -> bool` (when `hash_` is None, verifies against a module-level dummy hash and returns False); `needs_rehash(hash_: str) -> bool`.

- [ ] **Step 1: Write failing tests:** length boundaries (9 → error, 10 → ok, 128 → ok, 129 → error), common password rejected, equal-to-username rejected, hash round trip and `$argon2id$` prefix, wrong password False, `verify_password(None, "x")` False and takes comparable time (>0), `needs_rehash` False for a fresh hash and True for a hash made with `memory_cost=8`, and `test_semaphore_limits_concurrency` (patch the inner hasher to record concurrent entries; run 6 `hash_password` calls via `asyncio.gather`; assert max concurrent ≤ 2).
- [ ] **Step 2:** Run; FAIL. **Step 3:** Implement with `argon2.PasswordHasher` using the settings values, `asyncio.to_thread` plus a module-level `asyncio.Semaphore(2)`. **Step 4:** Pass. **Step 5: Commit** `feat: password policy and Argon2id hashing service`.

### Task 6: Recovery codes

**Files:** Create `backend/app/security/recovery.py`; Test `backend/tests/test_recovery_codes.py`

**Interfaces:**
- Consumes: `hash_password`, `verify_password` from Task 5 (same Argon2id parameters).
- Produces: `generate_recovery_code() -> str` (26 base32 chars, formatted `XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XX`), `normalize_recovery_code(code: str) -> str` (uppercase, strips spaces and dashes), `async hash_recovery_code(code: str) -> str`, `async verify_recovery_code(hash_: str | None, code: str) -> bool`.

- [ ] **Step 1: Write failing tests:** format regex; 1,000 generated codes unique; normalization accepts lowercase, spaces, missing dashes; verify True for any normalized variant; False for one changed character; False for `None` hash.
- [ ] **Step 2:** FAIL. **Step 3:** Implement using `secrets.token_bytes(16)` + `base64.b32encode`. **Step 4:** Pass. **Step 5: Commit** `feat: recovery code generation and verification`.

### Task 7: Users, sessions and login-attempt schema (migration 0002)

**Files:**
- Modify: `backend/app/models/models.py` (`User`; remove `Document.user_id default=1`), 
- Create: `backend/migrations/versions/0002_accounts.py`
- Test: extend `backend/tests/test_migrations.py`

**Interfaces:**
- Produces `User` columns: `public_id` (uuid4 str, unique, indexed), `display_name` (String 60, not null), `password_hash` (Text, null for legacy rows), `recovery_hash` (Text, null), `role` (String 10, default `student`, `CheckConstraint role IN ('student','admin')`), `is_active` (Boolean, default True), `last_login_at`, `subject_ref` (String 32, unique, random hex, not used yet; needed by the later consent log). `email` is dropped. `username` stays unique, lower-case by application rule. New models `UserSession` (table `sessions`: `id`, `user_id` FK cascade, `family_id` str, `refresh_hash` str unique, `created_at`, `expires_at`, `revoked_at`, `replaced_by` int null, `rotated_at` null, `user_agent_hash` str null) and `LoginAttempt` (table `login_attempts`: `key` str pk, `count` int, `window_start`, `locked_until` null).

- [ ] **Step 1: Write failing tests:** `test_upgrade_head_matches_models` still passes (guards drift); `test_role_check_constraint` (inserting `role='root'` raises `IntegrityError`); `test_legacy_client_users_cannot_authenticate` (a `client-…` row has `password_hash IS NULL` after migration; no data is deleted).
- [ ] **Step 2:** FAIL. **Step 3:** Hand-write the migration with `op.batch_alter_table` (SQLite-safe); existing rows get `display_name=username`, `role='student'`, generated `public_id`/`subject_ref` in a data step. **Step 4:** Run on SQLite and `bash backend/scripts/test_pg.sh tests/test_migrations.py`. **Step 5: Commit** `feat: accounts schema (users, sessions, login attempts)`.

### Task 8: Access tokens and rotating sessions

**Files:** Create `backend/app/security/tokens.py`, `backend/app/security/sessions.py`; Test `backend/tests/test_tokens_sessions.py`

**Interfaces:**
- Consumes: `UserSession` model (Task 7); settings.
- Produces: `class TokenError(Exception)`; `create_access_token(user_id: int, session_id: int) -> str`; `decode_access_token(token: str) -> dict` (keys `sub`, `sid`, `exp`; tries `JWT_SECRET` then `JWT_SECRET_PREVIOUS` by `kid`; raises `TokenError`). `class SessionError(Exception)`; `issue_session(db: Session, user_id: int, user_agent: str | None) -> tuple[str, UserSession]` (returns plaintext refresh token); `rotate_session(db: Session, refresh_token: str) -> tuple[str, UserSession]`; `revoke_session(db: Session, refresh_token: str) -> None`; `revoke_all_for_user(db: Session, user_id: int) -> None`.

- [ ] **Step 1: Write failing tests:** access token round trip; expired token (freeze `exp` in the past) raises `TokenError`; tampered signature raises; token signed with `JWT_SECRET_PREVIOUS` still decodes after rotation of secrets; `rotate_session` returns a new token and marks the old one rotated; **two rotations of the same old token within 10 s both succeed** (second returns the successor session without minting a third family branch); replay after 11 s (`rotated_at` set back) raises `SessionError` and revokes every session in the family; expired and unknown tokens raise `SessionError`; refresh token stored only as SHA-256 (plaintext not present in DB).
- [ ] **Step 2:** FAIL. **Step 3:** Implement with PyJWT; rotation inside one transaction using `SELECT … FOR UPDATE` on Postgres (plain select on SQLite). **Step 4:** Pass (SQLite and Postgres). **Step 5: Commit** `feat: access tokens and rotating refresh sessions`.

### Task 9: Auth router (register, login, refresh, logout, recover, me)

**Files:**
- Create: `backend/app/routers/auth.py`, `backend/app/schemas/auth.py`, `backend/app/security/throttle.py`, `backend/tests/helpers.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_auth_api.py`, `backend/tests/test_throttle.py`

**Interfaces:**
- Consumes: Tasks 5–8.
- Produces schemas: `RegisterRequest(display_name, username, password, confirm_password)`, `LoginRequest(username, password)`, `RecoverRequest(username, recovery_code, new_password, confirm_password)` — all `extra="forbid"`; `UserOut(public_id, display_name, username, role)`; `TokenResponse(access_token, user)`; `RegisterResponse(TokenResponse, recovery_code)`. Throttle: `check_allowed(db, username: str, ip: str) -> None` (raises `HTTPException 429` with `Retry-After`), `record_failure(db, username, ip)`, `record_success(db, username, ip)`; key is `sha256(username|ip)`; backoff 0 s for 4 failures then 2^n seconds capped at 15 min; per-(username, IP), never a hard per-username lockout. Endpoints: `POST /api/auth/register` (201), `/login`, `/refresh` (cookie only), `/logout` (204), `/recover`, `GET /api/auth/me`. Cookie endpoints (`/refresh`, `/logout`) require header `X-Kabisado-Request: 1` and an `Origin` in `allowed_origins` (or absent for same-origin), else 403. Client IP is taken from the last `X-Forwarded-For` hop only when behind the proxy setting `TRUST_PROXY=true`. `tests/helpers.py` provides `register_user(client, username=None) -> tuple[dict, str, str]` returning `(auth_headers, username, recovery_code)` with a unique random username.

- [ ] **Step 1: Write failing tests:** register returns 201 with `access_token`, `recovery_code`, a `Set-Cookie` with `HttpOnly; Secure; SameSite=Strict`, and role `student`; body containing `"role": "admin"` → 422; duplicate username (also `ANA` vs `ana`, trailing space, full-width `ａｎａ`) → 409 or 422, never two rows; **concurrent duplicate registration** (two threads) → one 201 and one 409; 129-char password → 422 and `hash_password` is never called (monkeypatch spy); mismatched confirm → 422; login success/failure messages are identical for unknown user and wrong password; 5 failures trigger 429 with `Retry-After`; success resets; deactivated user cannot log in (403 generic message); refresh without cookie / garbage cookie → 401; refresh without `X-Kabisado-Request` → 403; refresh with bad `Origin` → 403; logout revokes the session (refresh afterward → 401); recover with lowercase/spaced code works, rotates the code (old code fails), revokes every session, and returns the new code once; recover for unknown user is indistinguishable (same status and shape as wrong code) and burns similar time; `/me` needs a valid bearer token.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. Registration catches `IntegrityError` → 409; normalize username with `unicodedata.normalize("NFKC", u).strip().lower()` then validate `^[a-z0-9_.]{3,32}$`; set `subject_ref=secrets.token_hex(16)`, `public_id=uuid4()`. **Step 4:** Pass on SQLite and Postgres. **Step 5: Commit** `feat: auth endpoints with throttling, rotation and recovery`.

### Task 10: Bearer authentication in `identity.py`, replacing `X-Client-Id`

**Files:**
- Modify: `backend/app/identity.py`, `backend/tests/conftest.py`, `backend/tests/test_api.py` (replace `ALICE`/`BOB` headers with `register_user`)
- Test: `backend/tests/test_identity.py`

**Interfaces:**
- Consumes: `decode_access_token`, `UserSession`, `User`.
- Produces: `get_current_user(request, db) -> User` (401 if the header is missing/malformed, token invalid, session revoked/expired, or user missing/inactive); `require_student(user = Depends(get_current_user)) -> User`; `require_admin(user = Depends(get_current_user)) -> User` (403 otherwise); `get_owned_document` unchanged. The `X-Client-Id` code path and `client-` user creation are removed.

- [ ] **Step 1: Write failing tests:** no header → 401; garbage token → 401; valid token → 200 on `/api/documents`; **deactivating the user (DB update) makes the same unexpired token 401 on the next request**; revoking the session makes it 401; an old `X-Client-Id` header alone → 401; role read from DB (change `role` in DB → `require_admin` reflects it without a new token).
- [ ] **Step 2:** FAIL. **Step 3:** Implement; each request loads the user and session in at most two queries (single joined query preferred). **Step 4:** Update the existing API tests to authenticate through `register_user`; the full suite passes on SQLite and Postgres. **Step 5: Commit** `feat: bearer auth replaces client-id identity`.

### Task 11: Admin bootstrap CLI and role-enforcement placeholder

**Files:** Create `backend/app/cli.py`, `backend/app/routers/admin.py`; Modify `backend/app/main.py`; Test `backend/tests/test_admin_roles.py`

**Interfaces:**
- Produces: `python -m app.cli create-admin --username U [--display-name N]` (password read with `getpass`, validated with `validate_password`, creates `role='admin'`, prints the recovery code once, exits non-zero if the username exists); `python -m app.cli purge-legacy` (deletes users whose `password_hash IS NULL` after printing the count and requiring `--yes`); `GET /api/admin/ping` → `{"ok": true}` guarded by `require_admin` (placeholder until the dashboard phase). Public registration can never produce an admin.

- [ ] **Step 1: Write failing tests:** a student token on `/api/admin/ping` → 403; no token → 401; an admin created through the CLI function `create_admin(db, username, display_name, password) -> str` returns a recovery code and the admin token gets 200; `create_admin` on an existing username raises; `purge-legacy` leaves real accounts untouched.
- [ ] **Step 2:** FAIL. **Step 3:** Implement `create_admin` as a plain function so tests do not need `getpass`; the CLI wraps it. **Step 4:** Pass. **Step 5: Commit** `feat: admin created by CLI only, role guard`.

### Task 12: Self-service account lifecycle

**Files:** Modify `backend/app/routers/auth.py`; Test `backend/tests/test_account_lifecycle.py`

**Interfaces:**
- Produces: `POST /api/auth/password` (current password + new password; revokes every other session), `POST /api/auth/deactivate` (password-confirmed; sets `is_active=false`, revokes all sessions), `DELETE /api/auth/account` (password-confirmed; deletes the user and cascades all owned rows).

- [ ] **Step 1: Write failing tests:** changing the password with a wrong current password → 403; after change, other sessions' refresh → 401 and the old password fails; deactivate → next request with the old access token → 401 and login → 403; delete removes the user plus documents, topics, flashcards, questions, quiz attempts, flags and sessions (assert row counts zero for that user, other user's rows intact); delete needs the password.
- [ ] **Step 2:** FAIL. **Step 3:** Implement (SQLite needs `PRAGMA foreign_keys=ON`, already set). **Step 4:** Pass. **Step 5: Commit** `feat: password change, deactivate and delete account`.

### Task 13: Ownership matrix across every route

**Files:** Test only: `backend/tests/test_ownership_matrix.py`

**Interfaces:** Consumes the whole app and `register_user`.

- [ ] **Step 1: Write the test.** Alice creates a document, generates flashcards and a quiz, submits a flag. For every route in `app.routes` whose path contains an ID parameter (`document_id`, `card_id`, `question_id`, `topic_id`, or body fields `document_id` / `target_id`), Bob (a second registered student) calls it with Alice's IDs; assert the status is 404 (or 403 for admin-only) and **never 200/201/204**; assert Alice's data is unchanged afterward. Also assert every route not in an allowlist (`/api/health`, `/api/auth/register|login|refresh|recover`, docs/openapi when enabled) returns 401 with no token. The test fails if a new route appears that is neither covered nor allowlisted.
- [ ] **Step 2:** Run. Expected: PASS if ownership holds; any failure is a real bug to fix in the owning router (keep the fix inside this task, with the failing assertion as its test). **Step 3: Commit** `test: cross-student ownership and anonymous access matrix`.

### Task 14: Same-origin hosting (FastAPI serves the built frontend)

**Files:**
- Modify: `backend/app/main.py`, `backend/Dockerfile` (multi-stage: Node 22 builds `frontend/`, copies `dist` to `/app/static`), `render.yaml` (`rootDir` becomes the repo root with `dockerfilePath: backend/Dockerfile`, env vars `DATABASE_URL`, `JWT_SECRET`, `ALLOWED_ORIGINS`, `COOKIE_SECURE=true`, `GEMINI_ENABLED=false`), `backend/docker-compose.yml`
- Test: `backend/tests/test_static_spa.py`

**Interfaces:**
- Produces: when `backend/static/index.html` exists (`STATIC_DIR` setting), `GET /` and unknown non-`/api` paths return `index.html`; `/assets/*` are served as static files; `/api/*` unknown paths still return JSON 404 (never the SPA). Security headers middleware: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'` on HTML responses, `Cache-Control: no-store` on `/api/*`.

- [ ] **Step 1: Write failing tests:** with a temp `STATIC_DIR` containing `index.html`: `GET /` → 200 HTML with the CSP header; `GET /library` → index; `GET /api/nope` → 404 JSON; `GET /api/health` still JSON; `/api/*` responses carry `no-store`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement; mount static only if the directory exists so tests and dev (`vite` proxy) are unaffected. **Step 4:** Pass; `docker build -f backend/Dockerfile .` succeeds from the repo root and the container serves `/` and `/api/health`. **Step 5: Commit** `feat: serve frontend from the API for first-party cookies`.

### Task 15: Frontend auth client (vitest) and API wiring

**Files:**
- Create: `frontend/src/services/authClient.js`, `frontend/src/services/authClient.test.js`
- Modify: `frontend/src/services/api.js` (replace `getClientId`/`X-Client-Id` with bearer + 401 retry), `frontend/package.json` (add `vitest` dev dependency and `"test": "vitest run"`)

**Interfaces:**
- Produces: `authClient`: `register({displayName, username, password, confirmPassword}) -> {user, recoveryCode}`, `login({username, password}) -> user`, `recover({username, recoveryCode, newPassword, confirmPassword}) -> {user, recoveryCode}`, `logout() -> void`, `restoreSession() -> user | null` (calls `/api/auth/refresh`), `getAccessToken() -> string | null`, `onAuthChange(cb) -> unsubscribe`, `authFetch(url, options) -> Response`. The access token lives only in a module variable. `authFetch` adds `Authorization`, and on a 401 performs **one** refresh (single-flight: concurrent 401s share one in-flight refresh promise, using `navigator.locks` when available) and retries once; a failed refresh clears state and notifies `onAuthChange(null)`. Refresh and logout calls send `X-Kabisado-Request: 1` with `credentials: "same-origin"`.

- [ ] **Step 1: Write failing vitest tests with a mocked `fetch`:** token not written to `localStorage`/`sessionStorage`; 401 → refresh → retry succeeds; **five concurrent 401s cause exactly one `/api/auth/refresh` call**; a failed refresh calls `onAuthChange(null)` and does not loop; `logout` clears the token even if the network fails.
- [ ] **Step 2:** `cd frontend && npm install && npm test`. Expected FAIL. **Step 3:** Implement and switch every `apiFetch` call in `api.js` to `authFetch`. **Step 4:** `npm test`, `npm run lint`, `npm run build` all pass. **Step 5: Commit** `feat: frontend auth client with single-flight refresh`.

### Task 16: Auth screens, recovery-code handoff, privacy notice

**Files:**
- Create: `frontend/src/views/AuthView.jsx` (login / register tabs), `frontend/src/views/RecoverView.jsx`, `frontend/src/components/RecoveryCodeScreen.jsx`, `frontend/src/views/PrivacyView.jsx`, `frontend/src/components/AuthGate.jsx`
- Modify: `frontend/src/App.jsx` (render `AuthGate`; show app only when signed in), `frontend/src/components/Navbar.jsx` (display name, Logout), `frontend/src/main.jsx`

**Interfaces:** Consumes `authClient` (Task 15). `AuthGate({ children })` calls `restoreSession()` on mount, shows a "Gising na si Kabi… (waking up, this can take up to a minute)" state while the first request is pending, then children or `AuthView`.

- [ ] **Step 1:** Build the screens with password show/hide, field-level error messages (from API 422/409), confirm-password, and a Taglish microcopy tone consistent with the app. `RecoveryCodeScreen` displays the code once with Copy/Download buttons, the plain statement that losing both password and code means the account cannot be recovered, and a required "I saved my code" checkbox before continuing. `PrivacyView` lists exactly what is stored (username, display name, password hash, recovery-code hash, session metadata, study content), why, retention (login metadata 30 days), the processors (Render, Supabase, GitHub), that Gemini is off, and the deletion procedure; it is linked from the register form.
- [ ] **Step 2:** `npm run lint && npm run build`. Expected: no errors.
- [ ] **Step 3: Manual verification** (record results in the PR): run `uvicorn` + `npm run dev`; register → code screen → app loads; reload → still signed in; logout → sign-in screen; wrong password shows the generic error; recover with the code → new code shown; check mobile width and keyboard navigation of the forms.
- [ ] **Step 4: Commit** `feat: login, register, recovery and privacy screens`.

### Task 17: Pages wake-up page

**Files:** Create `wake/index.html`; Modify `.github/workflows/deploy.yml`

**Interfaces:** Produces a static page published to GitHub Pages that shows "Gigising na si Kabi…", polls `https://<API_ORIGIN>/api/health` every 3 s with a 90 s ceiling, then redirects to the API origin; shows a friendly retry message on timeout. The API origin comes from the repo variable `VITE_API_BASE`, substituted at build time in the workflow (`sed`). The Pages deploy no longer builds the React app.

- [ ] **Step 1:** Write `wake/index.html` (no external scripts, no tracking). **Step 2:** Update `deploy.yml` to substitute the origin and publish `wake/`. **Step 3:** After the first deploy, open the Pages URL with the API asleep; expected: wake message, then redirect. Record the observed cold-start time. **Step 4: Commit** `feat: GitHub Pages wake-up page for the free Render instance`.

### Task 18: Operations runbook and end-to-end verification on Supabase

**Files:** Create `docs/operations.md`; Modify `README.md` (architecture and setup sections)

- [ ] **Step 1:** Document: the migrate-then-deploy order (`DATABASE_URL=<session pooler URL> alembic upgrade head`), Render env vars (no secrets in the repo), creating the admin (`python -m app.cli create-admin` run locally against the production URL), rotating `JWT_SECRET` via `JWT_SECRET_PREVIOUS`, and the explicit limits: free-tier sleep, no managed Supabase backups yet (backups are a later phase), Gemini off.
- [ ] **Step 2: Verify on a real deploy** (owner creates the Render service from `feat/accounts`; Supabase DB migrated first): register two students and one admin; confirm each student sees only their own documents; confirm `/api/admin/ping` is 403 for a student and 200 for the admin; **restart the Render service and confirm accounts and documents survive**; confirm refresh survives a page reload; measure and record `/api/auth/login` latency and a documents list latency (expect hundreds of ms, report the numbers); confirm `GEMINI_ENABLED=false` produces offline summaries even with a key set.
- [ ] **Step 3:** Record every result (including failures) in the Phase 0 report appendix or a new `docs/phase2-results.md`. **Step 4: Commit** `docs: operations runbook and Phase 2 verification results`.

---

## Self-review notes

- **Spec coverage:** §6 (accounts, hashing, recovery, sessions, throttling, admin bootstrap, lifecycle) → Tasks 5–12; §7 authorization and ownership → Tasks 10, 13; §8 users/sessions/login_attempts and Alembic → Tasks 4, 7; §12 CORS, headers, DB pool → Tasks 2, 3, 14; §21 C1-partial (Gemini hard-off), I1 (Argon2 profile and semaphore), I2 (pooler/pool), I3 (grace window, no hard lockout), I8 (CLI-only bootstrap, JWT secret rotation, MAX_UPLOAD_MB 10); §22 decisions 1, 4, 5, 10 → Tasks 1, 3, 5, 14, 17. Deferred to later plans: Storage and discard-originals (Phase 3), backups and keep-alive (Phase 3), ConsentGate and consent log (Phase 4), admin dashboard (Phase 5), job runner (Phase 6; the Phase 0 sweep findings are carried into that plan).
- **Known gaps accepted:** the browser behaviour of `__Host-` cookies in Safari/Firefox is verified manually in Task 16/18 (cannot be unit-tested); `subject_ref` is created now but unused until the consent log.
- **Type consistency:** `UserSession` is the model name everywhere (table `sessions`); `register_user` returns `(headers, username, recovery_code)` in Tasks 9–13; `get_current_user`/`get_owned_document` keep their import path `app.identity` so routers do not change.
