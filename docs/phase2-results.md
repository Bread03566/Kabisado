# Phases 1–2 verification results

Branch `feat/accounts`. This records what was actually run, and, just as important, what was **not** run yet.

## Verified in this build (local)

| What | How | Result |
|---|---|---|
| Backend test suite | `backend/scripts/test.sh` (SQLite) and `backend/scripts/test_pg.sh` (Postgres 17 in Docker) | 147 passed on both |
| Migrations | Alembic `upgrade head` on empty SQLite and Postgres, legacy-data backfill, drift check against the models | Covered by `tests/test_migrations.py`, passing on both |
| Auth, throttling, rotation, recovery, lifecycle | `tests/test_auth_api.py`, `test_throttle.py`, `test_tokens_sessions.py`, `test_account_lifecycle.py` | Passing on both |
| Ownership and anonymous access across **every** route | `tests/test_ownership_matrix.py` (fails if a route is added without being classified) | Passing; the matrix was also confirmed to fail when the ownership filter was removed |
| Role enforcement | `tests/test_identity.py`, `tests/test_admin_roles.py` | Passing; role is read from the database, not the token |
| Retention (30 days) | `tests/test_retention.py` | Passing |
| Frontend auth client | `npm test` (vitest, 13 tests), `npm run lint` (0 errors, existing warnings only), `npm run build` | Passing |
| Docker image | `docker build -f backend/Dockerfile .` from the repo root; container serves `/`, `/library`, `/api/health`; unknown `/api/*` is JSON 404 | Passing |
| End-to-end over HTTP | `backend/scripts/e2e_check.py` against the built container (SQLite, local) | 16/16 checks passed, including admin 200 / student 403 and cookie refresh |
| Gemini off with a key present | Container started with `GEMINI_API_KEY` set | `/api/health` reports `ai_configured:false`, offline summaries, no Google traffic in the log |

Local latency (SQLite, same machine, so **not representative** of Render + Supabase): login median 94 ms, document list median 14 ms.

## NOT verified yet (needs the real deployment)

These need the Render service and the Supabase database, which are outside this branch and were left to the owner:

- [ ] Migration applied to the Supabase database (`alembic upgrade head` through the session pooler).
- [ ] `e2e_check.py` against the Render URL, with real login and list latency (expect hundreds of milliseconds to seconds, given the measured ~255 ms per query).
- [ ] Restart the Render service; accounts and documents survive.
- [ ] Page reload keeps the student signed in (cookie) on Render.
- [ ] Cold start time through the GitHub Pages wake-up page, and the redirect.
- [ ] Browser checks that cannot be automated: Chrome, Safari and Firefox `__Host-` cookie behaviour; phone width; keyboard navigation of the sign-in, register and recovery forms; copy and download of the recovery code. **No browser was available while building, so the React screens have been compiled, linted and unit-tested (client only) but never looked at.**
- [ ] **Throttle client IP on Render:** the API takes the last `X-Forwarded-For` hop (`TRUST_PROXY=true`). Log one real request header on Render and confirm that hop is the student, not Render's proxy. If it is a proxy address, every student shares one login throttle and five wrong guesses for any username lock that username for everyone.
- [ ] The first Render build of the frontend (a `lightningcss` binary error appeared once locally and did not repeat; see the runbook's troubleshooting table).

Record the results of these below when they are run, including any failures.

## Deployment results

_(to be filled in)_
