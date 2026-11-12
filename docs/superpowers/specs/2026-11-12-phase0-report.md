# Kabisado Phase 0 — Design Answers and Test Status

Date: 2026-11-12. Scope: Phase 0 only. No application code, database or Gemini calls touched.
Gemini remains globally disabled; the spike kit contains no Gemini dependency and makes no Gemini calls.

## A. Test status (honest)

| Test | Status | Why / what is needed |
|---|---|---|
| Argon2id timing/memory on Render Free | NOT RUN | Local machine has no Python; Docker Desktop was not running, so even an emulation (0.1 CPU/512 MB container) was not run. A container is only an approximation; the real figure needs a throwaway Render service. |
| Supabase pooler from Render | NOT RUN | Needs a Supabase project (owner) and a throwaway Render service. |
| GitHub Actions cron + artifact limits | NOT RUN | Needs a workflow pushed to GitHub. Pushing is outward-facing; waiting for owner approval. A scheduled run also needs real days to observe. |
| File upload/download/backup/restore | NOT RUN | Needs the Supabase project. |
| DB backup/restore + deletion replay | NOT RUN | Can run locally in Docker Postgres once Docker is up; Actions part needs GitHub. |
| Job resume/duplicate tests | NOT RUN | Logic testable locally; Render sleep behaviour needs the throwaway service. |
| Works with no payment method | NOT VERIFIED | Only the owner can see sign-up flows. Rule: abort and report any step asking for a card or "start trial". |

Nothing below is a result; it is design to be tested.

## B. Responses to the six points

### 1. Authentication without localStorage refresh tokens

Problem: GitHub Pages (`*.github.io`) and Render (`*.onrender.com`) are different sites, so an API cookie is a third-party cookie. Safari and Firefox restrict these by default; Chrome's behaviour has changed over time. I have not tested any browser; this is a Phase 0 test, not a fact.

| Option | Security | Cost | Risk / trade-off |
|---|---|---|---|
| A. HttpOnly cookie, `SameSite=None; Secure`, cross-site | JS cannot read it; needs CSRF defence (Origin check + custom header) | $0 | May simply not work in Safari/Firefox/privacy modes; failures look like random logouts. Test before trusting. |
| **B. Same origin: FastAPI on Render serves the built React app and the API; HttpOnly `__Host-` cookies, `SameSite=Strict`** | Strongest of the free options: first-party cookies, no CORS at all, `__Host-` prefix blocks sibling-subdomain overwrite, real security headers/CSP (we control headers, unlike Pages) | $0 | Page load also waits through Render cold start (~1 min). Mitigation: keep a tiny static GitHub Pages "Gising na si Kabi…" page that pings the API and redirects. Changes the deployment shape, so needs owner approval. |
| C. Tokens in memory only | No persistent theft target | $0 | Logout on every refresh; poor UX. |
| D. Reverse proxy on another free host (e.g. a free edge worker) | Same-origin cookies, keeps Pages | $0 if no card required (unverified) | Extra moving part and vendor; verify no payment method needed. |

Recommendation: **B**. Refresh token: HttpOnly, Secure, `SameSite=Strict`, `__Host-` cookie, path-limited, 7-day lifetime with rotation and reuse detection (10 s grace). Access token held only in memory. CSRF: strict Origin check plus required custom header on state-changing routes. Fallback if the owner insists on Pages: A, only if Phase 0 browser tests pass in Chrome, Firefox and Safari (Safari test needs an Apple device; I cannot run it).
Phase 0 test: throwaway Render service serving a stub page + `Set-Cookie` endpoint; check cookie persistence after reload in available browsers; cold-start page load time.

### 2. Backups of database AND uploaded files; deletions surviving restore

Observations: free object stores that need a card on file are excluded; a nightly artifact of a 1 GB bucket is impractical; encrypted dumps of a few hundred MB blow past typical free artifact quotas (to be measured).

Recommended: **don't keep original files by default.** Extract text at upload, store text/chunks in Postgres, discard the PDF/DOCX. Benefits: far less personal data stored, no object-backup problem, Storage quota nearly unused, smaller privacy surface. Cost: no "download original" feature. Supabase Storage remains used only for short-lived upload staging (deleted after processing) and avatars/none.
If the owner wants originals kept: back them up incrementally to a **second free Supabase project** (2 free projects allowed) via a GitHub Actions job using a sha256 manifest (only new/changed objects copied), encrypted client-side with `age`; the first project's DB dump records the manifest. Must be tested for quota and Actions runtime.

Deletions surviving restores (tombstone ledger):
- On account/document deletion the app appends a tombstone `{kind, random subject_ref or document_ref, deleted_at}` to a `deletion_ledger` table **and** the nightly job copies new tombstones to a store outside the restorable database (separate branch/second project/small encrypted file). Tombstones hold only random opaque refs, no usernames.
- The restore runbook is a script that (1) restores the dump into a staging DB, (2) replays every tombstone newer than the dump's snapshot (and all older ones, idempotent) deleting those rows and any storage objects, (3) verifies with a check query, (4) only then sets `restore_complete`; the app refuses to start serving if the DB revision is flagged `restore_in_progress`.
- Backups expire (30-day retention) so a deleted person's data eventually leaves every copy; the privacy page says so.
- Test: create user+doc, dump, delete user, restore dump, run replay, assert user and document gone, assert consent chain still verifies.

### 3. Pseudonymization without breaking the hash chain

Change from the earlier draft (this replaces the SECURITY DEFINER rewrite idea): **never rewrite log rows.**
- Each user gets a random 128-bit `subject_ref` at registration, stored on the user row. `consent_log` and `audit_log` rows reference **only `subject_ref`**, never `user_id`/username. The row hash covers `subject_ref`, action, policy version, timestamp, `prev_hash`.
- Chains are per `subject_ref`. Account deletion deletes the user row (the only place linking person ↔ `subject_ref`). The log rows are byte-for-byte unchanged, so every historical hash still verifies. Erasure works by severing the link, not by editing history.
- Pseudonymisation caveat: the log still holds a pseudonymous ID plus timestamps; if the owner prefers zero retention, a user's chain can be deleted whole (verification then proves the remaining chains, and the nightly "chain head" snapshot records that a chain was removed by a tombstone). Owner decision: keep pseudonymous chain (default) or delete whole chain.
- Admin audit rows use the admin's `subject_ref` and the target's `subject_ref`; action detail never includes content.
- Test: write chain, delete user, run verifier — must pass; attempt UPDATE/DELETE as the app role — must fail.

### 4. Storage quotas for a realistic pilot (estimates to be measured)

Assumptions (owner to correct): pilot of 50–75 students, ~10 documents each. Text of a 30-page handout ≈ 60–100 KB; with chunks, tsvector, GIN index (no raw_text kept) ≈ 2× ≈ 200 KB; plus flashcards/questions/attempts ≈ 100–150 KB. ≈ 350 KB per document ⇒ ≈ 3.5 MB per student at 10 documents.

| Pilot size | DB at 3.5 MB/student | Fits 500 MB? |
|---|---|---|
| 50 | ≈ 175 MB | yes (35%) |
| 75 | ≈ 260 MB | yes (52%) |
| 100 | ≈ 350 MB | tight (70%) |
| 150 | ≈ 525 MB | no |

Rules: **database** per-student cap 4 MB of study text, global soft limit 60% of 500 MB (stop new uploads at 90%), pilot capped at 75 students. **Files:** with the recommended "discard originals" policy, Storage use is transient (≤ 10 MB × concurrent uploads). If originals are kept: per-student cap 8 MB, total cap 70% of 1 GB ⇒ ≈ 85 students at the cap; otherwise 50 MB × 20 students already fills 1 GB. Egress 5 GB/month is not the limiting factor at this size. Phase 0 measures real row/index sizes with sample documents and replaces these estimates.

### 5. Gemini
Globally disabled (`GEMINI_ENABLED=false` hard-coded default, not overridable by users). Phase 0 has no Gemini key, SDK or call. It stays off until the owner personally verifies the key's project has no billing account and we jointly review the terms (including the under-18 clause) and audience restrictions.

### 6. Background jobs: resumable, no duplicates (design to test)
- `jobs` row per document stage with `status`, `attempts`, `lease_until`, `idempotency_key = (document_id, stage)` with a UNIQUE constraint.
- Worker claims a job with `UPDATE … SET lease_until = now()+90s WHERE status IN ('queued','running') AND lease_until < now() … RETURNING` (SKIP LOCKED); renews the lease per chunk.
- Results are written in one transaction with `INSERT … ON CONFLICT DO NOTHING` keyed on (document_id, stage, chunk_index), and the status flip happens in the same transaction — a crash leaves either nothing or everything for that chunk.
- Startup sweep and a poll-triggered sweep re-claim expired leases, so Render sleep/restart, browser close or lost connection never strands or doubles work. Browser state is irrelevant: the client polls status by job id (also keeps the instance awake while the student is waiting).
- Tests: kill the process mid-job (simulating sleep/restart); close the client mid-job; submit the same upload twice; two workers racing the same job; confirm exactly one set of chunks/summaries. Render-specific: observe whether processing survives idle spin-down (expected not; resume must handle it).

## B2. ACTUAL RESULTS (2026-11-12; supersedes the NOT RUN rows in §A where listed)

Environment: Supabase Free (Mumbai, Postgres 17.11), Render Free (0.1 CPU / 512 MB confirmed on the create screen), GitHub Actions on a public repo. No payment method was requested at any step the owner reported.

| Test | Result |
|---|---|
| Pooler (session mode, :5432) from GitHub runner | PASS (IPv4 works) |
| pg_dump via pooler; restore into clean PG17 | PASS (5000/5000 rows) |
| age encrypt/decrypt of dump | PASS |
| Storage: private bucket, 3 MB upload/download sha256 | PASS (~2.5 s up / ~3.5 s down from runner) |
| Anonymous access to private object | PASS (refused, HTTP 400) |
| 60 MB upload | rejected 413 as expected (50 MB limit) |
| Storage works with Supabase Data API disabled | PASS |
| 40 MB encrypted artifact upload (public repo, 1-day retention) | PASS; NOTE public-repo artifacts are world-downloadable, so encrypt always |
| Argon2id on real Render Free, 19 MiB t=2 | hash 210-420 ms, verify 190-500 ms; 3 concurrent wall 1.2 s; RSS ~102 MB |
| Argon2id 32 MiB t=2 | hash 410-860 ms; 3 concurrent wall 2.5 s; peak 166 MB |
| Argon2id 64 MiB t=3 | hash 1.2-2.4 s; 3 concurrent wall 7.1 s; peak 230 MB (not acceptable) |
| Render -> Supabase latency | **connect 1.4 s; `select 1` avg 255 ms (max 464 ms)** per round trip |
| Set-Cookie `__Host-` HttpOnly Secure SameSite=Strict header | emitted correctly. Browser persistence NOT tested. |
| Duplicate job submit x3 | 1 worker only (attempts=1), 40/40 distinct chunks |
| Job + service restart mid-run (74/200) | **FAILED to self-resume** (startup sweep ran while the 5 s lease was unexpired; nothing re-swept). After a poll-style sweep: resumed, 200/200, 200 distinct, attempts=2, no duplicates |
| Local (Docker PG16): chain survives deletion; append-only role; restore resurrects deleted user and ledger replay removes; job kill/race; storage size | all PASS (see §B/chat) |
| Cold-start time | NOT measured (Render UI states "50 seconds or more") |
| Scheduled workflow (cron) | NOT tested (runs only from default branch) |

Design changes forced by results
1. Argon2: 19 MiB, t=2, p=1; semaphore of 2; accept login queueing under bursts. 32 MiB+ rejected.
2. **Database latency is the main performance risk.** Reverses the earlier "NullPool" advice: keep a small persistent connection pool in the app (a new connection costs ~1.4 s), minimise sequential queries per request (batch/CTEs/joins), keep job chunks coarse (several items per transaction). Check that Render is really in Singapore; consider moving Supabase to a closer region (project is empty) if the 255 ms figure persists.
3. Jobs: resumption must not rely on the startup sweep alone. Add (a) a sweep triggered by every job-status poll and (b) a periodic background sweep every ~15 s while the process is up. Lease should be longer than expected restart time or the sweep must run repeatedly after boot.
4. Public repo: backups must be encrypted before upload; consider a private backup repo.

## C. Phase 0 test kit (built on branch `phase0-spike`)
On a separate branch `phase0-spike` (never main) in new files only, no change to `backend/` or `frontend/`: a small spike FastAPI service (Argon2 endpoint reporting time and RSS; DB connectivity; storage round trip; cookie probe; job-resume probe), a GitHub Actions workflow for pooler connectivity from a runner, `pg_dump`/restore and artifact size/retention tests, and a scheduled no-op to observe cron.

## D. What I need from the owner
1. Create a free Supabase project (note: stop if any card/trial is requested) and put its pooler connection string and service key in a local, gitignored file or the Render/GitHub secrets UI — never in chat.
2. Approve creating a throwaway free Render service and pushing the `phase0-spike` branch (outward-facing; I will not do either without a yes).
3. Start Docker Desktop (or tell me to) for local Postgres restore/replay and job-race tests.
4. Confirm pilot size assumptions (50–75 students? ~10 documents each?).
5. Decide: discard originals by default (recommended) or keep them; same-origin Render deployment (Option B) or insist on Pages.
