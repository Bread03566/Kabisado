# Kabisado — Architecture & Implementation Design

Status: REVIEWED DRAFT for owner approval (independent review folded in as §21; §21 overrides earlier sections where they conflict). No application code has been written or changed.
Date: 2026-11-12. Budget: strictly ₱0/month. Free tiers only; no card on file anywhere.

## 1. Intent

Kabisado ("Aral ngayon, pasa bukas.") is an AI-assisted study companion for students. Students upload PDF/DOCX or paste notes and get summaries, flashcards, quizzes, grounded chat, adaptive review and exam prep. Kabi, a sleepy owl, is the mascot.

Today the app is a FastAPI + SQLite backend (Render Free, Docker) and a React/Vite frontend (GitHub Pages). Identity is a random `X-Client-Id` header in localStorage ("separation, not security"). Files and SQLite live on Render's ephemeral disk and are lost on restart. All Gemini-backed features already have an offline fallback (`ai_service.py`, gated by `is_api_configured()`).

The product goal: private, minimal-data student accounts without Gmail/phone; durable data; admin oversight; student content never sent to Google without explicit, enforceable consent; all at $0.

Priority order (from the owner): working functionality, data privacy, account security, reliable backend — before visual features.

## 2. Goals, non-goals, anti-goals

Goals
- Own account system (username + password + recovery code), roles `student`/`admin`, server-side enforcement.
- Durable Postgres + private file storage on free tiers, with migrations and a $0 backup routine.
- Gemini disabled by default; explicit consent, enforced on every call path, append-only tamper-evident consent log.
- Offline engine remains fully functional without Gemini.
- Admin dashboard with usage and free-quota monitoring.
- Phased delivery; each phase independently shippable and tested.

Non-goals
- Paid anything. Email/phone/OAuth login. Native apps. Real-time collaboration. Claiming legal compliance.

Anti-goals (failure even if it "works")
- Any code path that sends student content to Gemini without a current valid consent.
- Any step that can incur a charge, or that depends on a free *trial*.
- Data loss on Render sleep/redeploy or Supabase pause.
- Admins able to read passwords, recovery codes, or private study material without need.

## 3. Verified free-tier facts (checked 2026-11-12 on official pages)

| Service | Limit | Design consequence |
|---|---|---|
| Supabase Free | 500 MB DB, 1 GB storage, 50 MB max file, 5 GB egress (+5 GB cached), 2 active projects, **paused after 1 week inactivity**, **no automatic backups**; pricing page lists no pay-as-you-go on Free; behaviour when quota exceeded is NOT documented on pages I read | Cap uploads (10 MB), per-student quota, own backups, keep-alive, quota meter. Treat over-quota as degradation; owner must confirm no payment method on the org. |
| Render Free | Sleeps after 15 min idle, ~1 min cold start, 750 instance-hours/month, ephemeral FS, may restart any time, 1 instance, may be suspended for unusually high outbound traffic, SMTP ports blocked | Nothing durable on disk. "Waking up Kabi" UI. Do not keep awake 24/7 (≈720 of 750 h, no margin). No email features. |
| Gemini API free | Limits per *project*; RPD resets midnight Pacific; per-model numbers only visible in the owner's AI Studio (not verified) | Per-student and global daily budgets read from config; offline fallback on 429/exhaustion. |
| GitHub Pages / Actions | Free for the repo; **Actions scheduled-workflow and artifact limits not verified in this research** | Verify in Phase 2 spike before relying on cron for backups/keep-alive (see §13). |

Unverified (must be spiked, not assumed): Supabase pooler/IPv4 reachability from Render; Actions cron behaviour on inactive repos; Supabase over-quota behaviour.

## 4. Gemini data-use terms (verified quotes) and what they force

From Gemini API Additional Terms (aistudio.google.com/docs/terms) and usage policies:
- Unpaid services: "Google uses the content you submit to the Services and any generated responses to provide, improve, and develop" its products.
- "human reviewers may read, annotate, and process your API input and output."
- "Do not submit sensitive, confidential, or personal information to the Unpaid Services."
- No retention period is stated for unpaid content. Usage policies mention 55-day retention of prompts/context/output for misuse detection.
- "You must be 18 years of age or older to use the APIs." and API Clients may not be "directed towards or is likely to be accessed by individuals under the age of 18."
- Paid services are not used to improve products (not applicable: we never pay).

**Top-level risk (owner decision required, §17-Q1):** Kabisado's audience is students, many of whom are minors. Google's terms prohibit API clients likely to be accessed by under-18s. Per-user consent does not cure that at the client level. Therefore:
1. A server-side global switch `GEMINI_ENABLED` defaults to **false**. Even with user consent, nothing is sent unless the owner enables it.
2. Even when enabled, Gemini consent is offered only to users who self-declare 18+ at consent time; under-18 or unknown age ⇒ never offered, always offline.
3. The disclosure states these facts accurately and nothing more (no claims about retention beyond "not stated"). It is a draft from published terms, not legal advice; the owner should review it.
4. The recommended launch posture is **offline-only**, with the consent system built and tested but the switch off, until the owner decides after reading the terms.

## 5. Architecture

```
GitHub Pages (React, static)  --HTTPS, CORS: Pages origin only-->  Render Free (FastAPI)
                                                                     |-- Supabase Postgres (SQLAlchemy+Alembic, via pooler)
                                                                     |-- Supabase Storage (private bucket, service key, server-side only)
                                                                     `-- Gemini API (only through ConsentGate)
GitHub Actions (cron): nightly pg_dump -> encrypted artifact; twice-weekly keep-alive query
```
- Supabase is used as plain Postgres and object storage only. Not Supabase Auth. The service-role key and DB URL exist only as Render env vars; RLS enabled with no policies on all tables and the bucket private, so the public anon key can read nothing even if leaked.
- Existing routers/services are kept and extended; no rewrite.

## 6. Authentication & sessions (own implementation)

- Registration: display name, username (3–32, `[a-z0-9_.]`, case-folded unique), password (min 10 chars, max 128, checked against a small bundled common-password list), confirm. No email/phone. Role is never accepted from the client.
- Hashing: Argon2id via `argon2-cffi` with parameters tuned to Render Free's small CPU/RAM (target ≈100–200 ms; verify memory ≤ 64 MiB). Rehash-on-login when params change.
- Recovery code: 128-bit random, shown once as grouped base32, stored only as an Argon2id hash. Recovery = username + code + new password; success rotates the code and revokes all sessions. Copy says plainly that loss of both password and code means the account is unrecoverable. An admin cannot reset passwords or view codes (anti-goal).
- Sessions: **short-lived access token (15 min, JWT HS256, `sub`, `role`, `sid`, `exp`) kept in memory; rotating refresh token (30 days, opaque random, only its SHA-256 stored in `sessions`) in localStorage.** Chosen because Pages (github.io) and Render (onrender.com) are cross-site and third-party cookies are increasingly blocked. Trade-off acknowledged: refresh token in localStorage is XSS-exposed, so XSS defenses (§12) are mandatory; refresh reuse detection revokes the whole session family. This is my call, not previously agreed.
- Authorization header means no ambient credentials ⇒ CSRF not applicable; still verify `Origin`/CORS strictly.
- Every request re-loads the user and checks `is_active`; deactivation takes effect immediately regardless of token expiry. Role comes from the DB row, not the token claim.
- Login throttling: DB-backed counters per username and per IP (survive Render restarts), exponential delay/lockout, generic error messages, constant-time-ish handling for unknown usernames (dummy hash).
- Initial admin: one-time CLI `python -m app.cli create-admin` run by the owner against the production DB, or a bootstrap token env var valid only while zero admins exist and consumed on use. No hardcoded credentials; no public admin registration endpoint. Role changes only via admin CLI/audited admin action; no API lets a user set their own role (schemas use `extra="forbid"`).
- Account lifecycle: self-deactivate; admin deactivate/reactivate (audited); self-delete (password-confirmed) hard-deletes all user data and storage objects.

## 7. Authorization

- FastAPI dependencies: `current_user` (active, valid token), `require_student`, `require_admin`. Admin routes under `/api/admin/*` all depend on `require_admin`.
- Ownership: generalize `get_owned_document` to every resource lookup (topic, flashcard, question, attempt, summary, flag, job). Non-owner ⇒ 404. Every query that touches user data filters by `user_id` (directly or through an owned document). A test enumerates all routes and asserts a second student gets 404/403 on each ID-bearing route.
- Admins get aggregates and account metadata only; no endpoint returns document text, chat history, or recovery material.

## 8. Data model (Postgres, Alembic)

Existing tables kept: documents, topics, flashcards, review_logs, questions, quiz_attempts, question_attempts, flags. Changes/additions:

- `users`: id (uuid), username (unique, citext/lowercased), display_name, password_hash, recovery_hash, role (`student|admin`, CHECK), is_active, created_at, last_login_at, age_band (`unknown|under18|adult`), gemini_consent (bool, default false), consent_policy_version, consent_updated_at, storage_bytes_used. Drop `email`.
- `sessions`: id, user_id, refresh_hash, family_id, created_at, expires_at, revoked_at, replaced_by, user_agent_hash.
- `login_attempts`: key (username/IP hash), count, window_start, locked_until.
- `consent_log` (append-only, §9): id, user_id, action (`grant|withdraw|policy_reask|age_declare`), policy_version, age_band, created_at, prev_hash, row_hash.
- `documents`: add storage_key (not a URL), file_size, content_sha256, status (`processing|ready|failed`), error_message. Existing `file_path` retired.
- `chunks`: id, document_id, topic_id, ordinal, text, tsv (tsvector, GIN index) — for retrieval (§11).
- `summaries`: split cached summary columns into rows (document_id/topic_id, length, text, engine `offline|gemini`, created_at).
- `flashcards`: add difficulty counters (lapses, last_rating), `mastered` derived from interval ≥ 21 d.
- `topic_mastery`: user_id, topic_id, score, updated_at (derived from attempts + reviews).
- `study_days`, `xp_events`, `achievements`/`user_achievements`, `pet_choice` for gamification.
- `exam_plans`: user_id, document ids, plan JSON, created_at; `exam_attempts`.
- `ai_usage`: user_id, feature, engine, model, tokens_in/out (if returned), status, created_at. No prompt text stored.
- `jobs`: id, user_id, kind, payload (ids only, no content), status (`queued|running|done|failed|cancelled`), attempts, run_after, created_at.
- `audit_log` (append-only, same protections as consent_log): admin_id, action, target_user_id, detail JSON, created_at, prev_hash, row_hash.
- `system_events`: recent errors for the admin monitor.

Integer PKs may stay for existing tables; new user-facing identifiers use UUIDs.

Migrations: Alembic with a baseline revision matching the current models, then incremental revisions; `add_missing_columns` and `create_all` are removed from startup. Migrations run via a manual/CI step (`alembic upgrade head`) rather than silently at every boot on a cold-starting free instance.
Legacy data: current client-id users live on an ephemeral disk and are already lost on every restart, so there is no production data to migrate. `X-Client-Id` auth is removed at cutover; local dev DBs are recreated.

## 9. Gemini consent system

### 9.1 Single chokepoint
All Gemini traffic goes through one `ConsentGate` in front of `_call_gemini_json`/`_call_model_json` (the only place the `google-genai` client is invoked; a unit test greps the codebase that no other module imports the client).

`ConsentGate.authorize(user_id)` reads **fresh from the database** (never from a request object, token, cache, or job payload) and requires all of:
1. `settings.GEMINI_ENABLED` is true (global kill switch, default false);
2. `users.is_active` and `users.age_band == 'adult'`;
3. `users.gemini_consent` is true **and** `consent_policy_version == CURRENT_POLICY_VERSION`;
4. the per-user and global daily AI budget are not exhausted.

Any failure ⇒ the caller receives `Engine.OFFLINE` and uses the existing fallback; the response and UI say so.

### 9.2 Every call path
- Interactive requests, background jobs, **each retry attempt**, and **each model-fallback attempt** call `authorize()` immediately before the network call (not once per job).
- Queued jobs store only IDs/parameters, never content or a consent snapshot. At execution the job re-checks consent; on failure it either completes with the offline engine (feature supports it) or ends `cancelled` with reason `consent_withdrawn`.
- Withdrawal, in one transaction: sets `gemini_consent=false`, appends a `withdraw` log row, and marks the user's `queued`/`running` AI jobs `cancelled`. Because the gate re-reads the DB at call time, even a request already past the HTTP layer cannot send afterward, apart from a call whose network request has already left (§9.5).
- Dev/test: a fake-Gemini transport asserts zero calls when consent is off; a CI test fails if any code path reaches the client without the gate (call-graph test via a patched client that raises).

### 9.3 Consent log integrity
- Append-only table. The app connects as a restricted DB role (`kabisado_app`) granted only `INSERT, SELECT` on `consent_log` and `audit_log`; no `UPDATE/DELETE/TRUNCATE`. A trigger also raises on UPDATE/DELETE as defense in depth. Migrations run as a separate owner role.
- Tamper evidence: `row_hash = SHA256(prev_hash || canonical row)`; chain per user; an admin-run verification endpoint/CLI reports breaks.
- Honest limit: the Supabase project owner (the operator) can always alter the DB. These controls protect against app bugs, SQL injection and non-owner admins, not against the infrastructure owner. State this in docs.
- Account deletion: consent/audit rows are retained only as pseudonymous (`user_id` becomes a one-way token) for dispute purposes, or deleted entirely if the owner prefers (§17-Q4). Default: delete with the account, because collecting less is the stated principle.

### 9.4 Student experience
- Settings → "Gemini AI (optional)". Off by default; shown only when `GEMINI_ENABLED`; ineligible users see "Not available" with the reason.
- Before enabling: plain-language disclosure (Filipino/English), 18+ self-declaration, explicit checkbox + confirm. Content: what may be sent (the text of the sections being processed, your chat questions and recent chat turns, generation settings; never username/display name/password, other documents or other users' data); that Google's terms say unpaid-service content is used to "provide, improve, and develop" its products and that human reviewers may read it; that Google tells users not to submit sensitive/confidential/personal information; that retention for unpaid use is not stated in the terms; that content cannot be recalled by us after sending.
- Withdraw: one click, immediately effective, queued work cancelled.
- Existing generated materials are kept on withdrawal (they are the student's own study data), each labelled with its engine. The UI explains that already-transmitted content may not be recoverable or deletable by Kabisado or Google, and that deleting a document here does not delete anything Google received.
- Features needing Gemini show "Needs Gemini AI (off)" instead of failing; supported features fall back with a visible "Offline mode" badge. Capability map (initial): summaries, flashcards, quizzes, chat = offline-capable; richer exam-plan narratives, simplified-explanation rewrites = Gemini-only.
- Policy version bump ⇒ consent lapses until re-accepted (logged `policy_reask`).
- Admin sees only the aggregate count of users with consent.

### 9.5 Known limits (disclosed)
A request already in flight when consent is withdrawn may complete; content previously transmitted cannot be recalled. Maximum window: one HTTP call (timeout 60 s).

## 10. Minors and applicable law (not legal advice)

- Google's terms (§4) are the binding constraint for Gemini.
- Philippine Data Privacy Act context: NPC's 2024 child-oriented transparency advisory applies to services accessible to children regardless of legal basis; sources disagree on any digital-consent age and parental consent applies when consent is the legal basis. Treat age threshold as unsettled; owner/counsel should verify against the statute, IRR and NPC texts.
- Design response: collect minimal data; no email/phone/location; no ads/analytics trackers; child-friendly plain-language privacy notice (Taglish) at registration; age band self-declared at the point of the Gemini consent only (not collected otherwise); Gemini never offered to under-18/unknown; offline features need no parental consent since no third-party sharing of content occurs; leaderboard/social features are out of scope. If the owner later wants minors to use Gemini, that requires a different provider/terms, not a consent tweak (§17-Q1).
- A "What we store and why" page lists every field in §8, retention, deletion, and the Supabase/Render/Google processors involved.

## 11. Document processing and grounded chat (all free, no embeddings API)

- Upload: server-side checks — extension and magic bytes (`%PDF-`, ZIP/DOCX structure), 10 MB cap, page/char caps, per-student storage quota (default 50 MB; global usage tracked against the 1 GB meter), reject encrypted/zip-bomb DOCX (uncompressed-size cap), no macro formats. Stored under `users/<user_id>/<uuid>` in a private bucket; the filename is never trusted. Retrieval via backend-streamed download or a ≤60 s signed URL after an ownership check; permanent URLs are never exposed.
- Processing runs as a DB-tracked job (status `processing→ready|failed`, error message). The existing parser/segmenter are reused; add concept/definition and keyword extraction (existing offline heuristics), de-duplication of near-identical sentences. In-process worker only: Render Free can sleep mid-job, so jobs are resumable (a startup sweep requeues `running` jobs older than N minutes).
- Chunks stored with a Postgres `tsvector` GIN index. Chat retrieves top-k chunks via full-text ranking (`websearch_to_tsquery`), cites document title + topic + chunk ordinal, and answers "not found in your material" when the best rank is below a threshold. This is the offline path; Gemini (if permitted) only rewrites an answer from the retrieved chunks with a prompt forbidding outside facts. Free-tier compatible (runs inside the existing DB).

## 12. Security controls

- CORS: explicit origin list from env (Pages origin + localhost in dev), `allow_credentials=False` (token header auth), restricted methods/headers. Replaces `allow_origins=["*"]` now.
- Security headers on the API (HSTS via Render's TLS, `X-Content-Type-Options`, `Referrer-Policy: no-referrer`, API `Cache-Control: no-store`); strict CSP on the Pages build.
- XSS: render AI/user text through the existing Markdown component with a sanitizer (DOMPurify or equivalent) and no `dangerouslySetInnerHTML` of raw content; audit all components.
- SQL injection: SQLAlchemy parameterization only; no string-built SQL (the current `add_missing_columns` DDL is deleted).
- Rate limiting: app-level limits per user/IP for login, register, recovery, upload, AI endpoints (DB-backed for auth; in-memory token bucket acceptable for the rest because Render Free is a single instance and counters resetting on sleep is harmless). Global free-quota guards: refuse new uploads when storage > 90% of the meter.
- Secrets only in Render env vars (`DATABASE_URL`, `SUPABASE_SERVICE_KEY`, `JWT_SECRET`, `GEMINI_API_KEY`); never in frontend, never logged. `/docs` and verbose errors disabled in production.
- Logging: no passwords, tokens, recovery codes, or document text in logs.
- Honest status: nothing here is claimed "completely secure". Phase 7 includes a checklist review and tests; an external audit is out of budget.

## 13. Backups, keep-alive, recovery ($0)

- Nightly GitHub Actions workflow: `pg_dump` (custom format) using a read-only DB role → encrypt with `age` (public key in the repo, private key held by the owner offline) → upload as a private workflow artifact with max retention; the last N dumps are kept. Storage-object manifest (keys + sha256) dumped alongside; files themselves are re-uploadable by students, with an owner-run script for full bucket export.
- Manual: documented `pg_dump`/restore runbook; admin dashboard "Export database" is NOT provided (would expose all data); per-student "Export my data" (JSON + originals zip) is provided.
- Keep-alive: workflow runs a trivial query against Supabase twice a week so the project does not pause after a week idle. **Spike required**: confirm schedule behaviour on an inactive repo (GitHub disables scheduled workflows on inactive public repos after a period) and Actions/artifact free limits; if unreliable, the fallback is the owner's manual weekly visit plus the admin dashboard "days since last DB activity" warning. Do not market this as a guarantee.
- Recovery truth: free Supabase has no managed backups; the dump is the only recovery path, with up to 24 h data loss. Documented in the admin README.

## 14. AI usage control

- `ai_usage` rows for every engine decision (offline or Gemini). Per-student daily Gemini budget (default 30 calls) and a global daily cap below the owner's AI Studio limits (configured via env). On 429/exhaustion: fall back offline, record `quota_exhausted`, show the student a friendly state.
- Model names from config; the existing fallback-model list is kept. Do not hard-code model names in logic.

## 15. Admin dashboard

Separate `/admin` area (frontend route guard is cosmetic; backend enforces). Pages: Overview (counts of students, active/disabled, documents, summaries, flashcards, quizzes, AI calls, recent activity), Students (search by username/display name; metadata only; deactivate/reactivate; reported items), AI & System (request counts, failures, tokens when returned, backend health, DB size and storage vs free limits, recent errors, Supabase "days since activity"), Audit log viewer, Settings (rate/limits, quotas; **not** the Gemini switch — that is an env var only the infrastructure owner controls). All admin writes append to `audit_log`.

## 16. Learning features (phases 5–6, spec'd lightly here; each gets its own short design before building)

- Flashcards: SM-2 retained; add lapses, difficulty, mastered/unmastered, review schedule view.
- Quizzes: existing four formats kept; add per-topic scoring, weak-topic detection (rolling accuracy per topic with minimum sample size), regeneration from mistakes, de-duplication by normalized question text.
- Adaptive: `topic_mastery`, recommended next actions, streaks (existing review-log based), in-app review reminders (no push/email).
- Exam Prep: select documents → topic importance (offline heuristics) → current understanding from mastery → plan → practice exam → final report; works offline, Gemini only for optional narrative.
- Gamification: XP/levels, badges, pets (existing `pets.jsx`), Taglish encouragement; calm by default, no dark patterns.
- UI: keep identity; responsive, accessible (labels, contrast, focus, reduced motion), loading/empty/error states, cold-start banner.

## 17. Phases and acceptance

0. Spikes (no product code): Supabase pooler from Render; Argon2 timing on Render Free; Actions cron/artifact limits; storage upload round-trip.
1. Audit fixes + CORS lock-down + Alembic baseline on Postgres.
2. Accounts/roles/sessions/recovery + admin bootstrap + ownership tests + cutover from client-ID.
3. Storage + upload validation + quotas + backup workflow + export.
4. ConsentGate + consent log + settings UI + offline-parity tests.
5. Admin dashboard + audit log + monitors.
6. Grounded retrieval + chat + processing jobs.
7. Adaptive learning + Exam Prep.
8. Gamification/UI polish.
9. Security review, load/persistence verification (restart + redeploy keeps data), deployment docs.

Done = all existing tests still pass, new tests per feature, a restart/redeploy persistence check, and a role/ownership matrix test green.

## 18. Testing
Pytest against a Postgres test DB (local Docker/CI service; production DB never used for tests). Coverage: registration/login/logout/refresh reuse, recovery, throttling, role enforcement on every route, cross-student isolation on every ID route, upload validation (spoofed types, oversized, zip bombs), consent matrix (every combination of flag/consent/age/policy/budget × every AI feature × retry/queue/withdraw-in-flight), consent-log immutability and chain verification, offline parity, admin endpoints, quota guards. Frontend: component tests for consent flow, manual mobile checks.

## 19. Calls made by me (not yet agreed)
Token-based sessions over cookies; Argon2 params; 10 MB file / 50 MB per-student caps; Alembic run as an explicit step; Postgres FTS instead of embeddings; GitHub Actions for backup/keep-alive; deleting consent rows with the account; Gemini hard-off via env flag and 18+ gating; age asked only at consent time.

## 20. Open questions for the owner
Q1. Given Google's under-18 clause, keep Gemini off at launch (recommended), or enable it for self-declared adults only despite audience risk?
Q2. Is the repo public or private (affects backup artifact handling)?
Q3. Expected user count (affects whether 500 MB / 1 GB suffice)?
Q4. On account deletion, delete consent/audit rows too (default) or keep pseudonymized? (superseded by §21-C4: pseudonymize, never delete)

## 21. Independent review: findings and revisions (supersede earlier text)

Reviewer checked the doc against `backend/app`; web claims about Supabase/GitHub/Render were NOT independently verified and stay Phase-0 spike gates.

Critical
- **C1 Gate placement.** `ai_service.py` loops over models (`_call_gemini_json`) and retries (`_call_model_json`) and `AIService` is a global singleton gated by global `is_api_configured()`. Revised: every `AIService` method takes an explicit `AIContext(user_id, db)`; `ConsentGate.authorize()` runs **inside the innermost loop, immediately before `generate_content`**, so each retry and each model attempt is checked. `is_api_configured()` is replaced by `gate.engine_for(user)`. Add a runtime test that fails if `generate_content` executes without a gate token, in addition to the single-importer test.
- **C2 Billing trap.** The Gemini key must come from an AI Studio/Cloud project with **no billing account linked**; a billing-enabled project silently moves to paid usage. Hard rule plus pre-launch checklist item (owner confirms in Cloud console). `GEMINI_ENABLED` stays false until ticked.
- **C3 RLS vs restricted role.** "RLS on, no policies" would block `kabisado_app` too. Revised: RLS stays on; `kabisado_app` gets explicit permissive policies `TO kabisado_app`; `anon`/`authenticated` get `REVOKE ALL` (and the Supabase Data API is disabled where possible). Phase-0 spike: custom role through the pooler (username format `role.projectref`).
- **C4 Append-only vs deletion.** Account deletion never DELETEs log rows. It calls a `SECURITY DEFINER` function owned by the owner role that rewrites `user_id` to a one-way pseudonym. "Tamper-evident" means detection only; an INSERT-capable app role could still forge rows after a bug/SQLi. Chain updates take a per-user advisory lock; chain head hashes are written into each nightly backup so rewrites are detectable. (Q4 default changes to pseudonymize.)
- **C5 Token storage on github.io.** Pages cannot set headers, so CSP is only a `<meta>` tag (no `frame-ancestors`, weaker). All project sites under one `<user>.github.io` share an origin. Revised: refresh token lifetime 7 days (not 30); requirement that Kabisado is the **sole project served from its Pages origin** (or the owner accepts the risk); XSS defenses remain mandatory. Custom domain is not free, so not planned.

Important
- **I1 Argon2id on Render Free (~0.1 CPU/512 MB).** Use OWASP minimum profile (19–32 MiB), run hashing in a threadpool behind a semaphore (max 2), never on the event loop. Phase-0 spike has a pass/fail threshold (≤ 500 ms, no OOM under 3 parallel logins). The 100–200 ms target is withdrawn.
- **I2 Connectivity.** Direct DB host is IPv6-only; Render and Actions are IPv4 ⇒ **pooler required**. Session mode for Alembic and `pg_dump`; app uses `NullPool`/small pool and no prepared statements (transaction mode). Named requirement, plus spike confirmation.
- **I3 Refresh races.** 10 s grace window on rotation (or single-flight refresh via Web Locks/BroadcastChannel). Throttle logins by (username, IP) with backoff instead of hard per-username lockout (avoids victim lockout). Client IP taken only from the trusted `X-Forwarded-For` hop behind Render.
- **I4 Backup/keep-alive reliability.** Scheduled workflows can be disabled after ~60 days of repo inactivity and run late; private-repo artifacts count against a small quota. Revised: the dump job writes a heartbeat row; admin dashboard shows "last successful backup age" and warns past 36 h; keep-alive is activity-based (any DB use counts), dashboard warns at 4 days idle. Backups that silently stop are treated as a defect, not a note. pg_dump client version ≥ server version. Document age private-key loss risk.
- **I5 Jobs on a sleeping instance.** Render stops the instance 15 min after the last inbound request even mid-job. Revised: jobs progress only while the browser polls (polling keeps it awake); jobs are idempotent and chunked; startup sweep kept. PDF parsing runs under page/char caps in a bounded worker to avoid OOM on 512 MB.
- **I6 Storage math.** `raw_text + chunks.text + tsvector + GIN` ≈ 3× text size. Revised: do not store `raw_text` once chunked (chunks are the source); per-user text cap; the 90% guard applies to **DB size as well as storage**. Over-quota behaviour is unverified (spike/owner check); until verified assume read-only or errors.
- **I7 Claims corrected.** (a) "Hard-deletes all data" excludes encrypted backups until they expire and anything sent to Google; the privacy page states the backup retention window. (b) Offline mode still involves Render, Supabase and GitHub Actions (encrypted dumps) as processors; wording is "no content goes to Google/AI providers", not "no third party". (c) Admins do not see study content; **reports/flags store only IDs, reason and the student's short note, never document text** (unless owner decides otherwise, Q below). (d) The 18+ checkbox is self-declaration, not age verification, and lowers but does not remove the Google-terms risk.
- **I8 Misc.** Admin bootstrap is CLI-only (no env bootstrap token left behind). `JWT_SECRET` rotation: support two active secrets (`kid`), documented procedure. Uploads: content-sniffed type check and decompression-ratio cap for DOCX/PDF. `MAX_UPLOAD_MB` changes from 20 to 10 (deliberate).

Minor
- `user_agent_hash`, IP hashes, `login_attempts` are collected data: listed on the "what we store" page; retention 30 days.
- Migration order: **migrate first, then deploy**; app fails fast on a schema-revision mismatch (Render auto-deploys, migrations are manual).
- Migration defaults must not grant consent to any existing rows (`gemini_consent` default false, policy version null).
- §3's unverified items and §13's reliance on them are both Phase-0 gates.

Added owner decisions (beyond §20)
- Q5. Confirm the Gemini key's project has no billing account (required before ever enabling Gemini).
- Q6. Backup/login-metadata retention periods (proposed: dumps 30 days, metadata 30 days).
- Q7. Accept up to 24 h data loss on a Supabase failure, and who checks the backup heartbeat (proposed: the owner, via the admin dashboard).
- Q8. Whether the recovery-code-only model (lost password + code = unrecoverable) is acceptable for student accounts, including minors.
- Q9. Whether admins may ever see reported content (proposed: no).

## 22. Decisions after Phase 0 (made by me on the owner's instruction "do whatever you think is good"; owner may override any)

Phase 0 results are in `2026-11-12-phase0-report.md` §B2 and override earlier assumptions where they conflict.

1. **Deployment shape: same-origin on Render.** FastAPI serves the built React app and the API from one origin; HttpOnly `__Host-` `SameSite=Strict` refresh cookie, access token in memory, strict Origin check plus custom header for CSRF. GitHub Pages is reduced to a tiny static "waking up Kabi" page that pings the API and redirects. Browser cookie persistence (Chrome/Firefox/Safari) still needs a manual check before Phase 2 ships; fallback is memory-only access tokens with a re-login.
2. **Uploaded originals are discarded after text extraction** (Storage used only for transient upload staging). Removes the file-backup problem and shrinks stored personal data. "Download original" is not offered. Revisit only if the pilot demands it.
3. **Region:** keep Supabase in Mumbai for now. Render region must be confirmed as Singapore by the owner. If measured query latency stays near 255 ms, recreate the (empty) Supabase project closer before Phase 1 data exists.
4. **Database access pattern:** persistent small connection pool (opening a connection costs ~1.4 s), few sequential queries per request, coarse job chunks. This reverses the earlier NullPool suggestion.
5. **Argon2id:** 19 MiB, t=2, p=1, concurrency semaphore of 2.
6. **Jobs:** lease-based, idempotent; sweep on every status poll plus a periodic ~15 s background sweep (the startup-only sweep failed in the Render restart test).
7. **Consent/audit logs:** random `subject_ref`, never rewritten; deletion removes only the user row (pseudonymous chain retained by default; owner may choose whole-chain deletion). Deletion tombstones copied outside the database and replayed by the restore script.
8. **Backups on a public repo:** encrypt with `age` before any upload; prefer a separate private backup repo (free). Keep-alive/backup cron needs a heartbeat workflow on `main`; requires owner approval.
9. **Pilot cap:** 75 students; 4 MB study-text cap per student; global soft limit 60% of the 500 MB database; new uploads stop at 90%. Per-document cost to be re-measured with real documents (synthetic estimate ~210 KB, planning figure stays 350 KB).
10. **Gemini:** globally disabled and unchanged. Nothing in Phase 0 or the plan enables it. Enabling requires the owner to verify the key's project has no billing account and to review the terms and under-18 restriction.
11. **Phase 0 status:** complete from my side, with open items: cold-start time, browser cookie behaviour, cron on `main`, Render region check. Implementation has NOT started and needs the owner's explicit approval.
