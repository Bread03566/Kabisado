# Security review (Phase 9)

Done by the author, not an outside auditor. Nothing here is a claim that Kabisado is "completely secure".
What was checked, what was found, and what is still open.

## Checked, with evidence

| Area | Result |
|---|---|
| Every `/api/*` route rejects an anonymous caller | A test walks the API schema and calls all 40 protected routes without a login; each returns 401. A new unprotected route fails the suite. Only health, register, login, refresh, logout and recover are public. |
| One student cannot read another's data | Ownership matrix tests (documents, topics, flashcards, quizzes, chat, progress, flags, exam prep, export). Another student's id returns 404, so ids cannot be probed. |
| Admin routes | Server enforces the role on every `/api/admin/*` route; students get 403. Admins cannot deactivate themselves or other admins. Every admin change is audit-logged. |
| Passwords and recovery | Argon2id (t=2, 19 MiB), per-account and per-IP throttling with backoff, one-time recovery code stored only as a hash. |
| Sessions | 15-minute access token held in memory; refresh token in an `HttpOnly`, `Secure`, `SameSite=Strict`, `__Host-` cookie, rotated, reuse detected; deactivation revokes everything. |
| CORS | Explicit origin list, no wildcard; a random origin gets no CORS headers (checked on the live site). |
| Response headers | Live HTML has a CSP (`default-src 'self'`, `frame-ancestors 'none'`), `Referrer-Policy: no-referrer`, `nosniff`; API responses are `no-store`. |
| API docs | **Found open in production and fixed:** `/docs`, `/redoc` and `/openapi.json` were public. They are now disabled unless `DEBUG=true` (test: `test_interactive_api_docs_are_off_unless_debug`). |
| Error handling | A test forces an internal error and confirms no internal detail or connection string reaches the response. |
| Uploads | Magic-byte check, macro and zip-bomb rejection, size and length caps, per-student and global quotas, originals discarded. |
| Gemini | Off. Gate re-checks consent from the database before every request; fails closed; tests prove zero requests without consent. |
| Secrets in logs | No log call mentions passwords, tokens, recovery codes or secrets. |
| Frontend | No `dangerouslySetInnerHTML`, `innerHTML` or `eval`. |
| Dependencies | `npm audit --omit=dev`: 0 vulnerabilities. `pip-audit` on `requirements.txt`: none known (on the review date). |

## Still open (owner or later work)

- **Client IP behind Render's proxy.** The throttle trusts the *last* `X-Forwarded-For` hop (`TRUST_PROXY=true`). This has not been confirmed on Render. If it is wrong, all students share one throttle bucket or an attacker can pick their own. Verify by logging in from two networks and checking that failures on one do not throttle the other.
- **No second factor and no email recovery.** By design (no email or phone). Losing the password and the recovery code loses the account.
- **Login takes about 4 s on Render** (Argon2id on a 0.1 CPU instance plus distant database). Safe, but slow.
- **The infrastructure owner can read and edit everything** in Supabase. The consent log's hash chain detects edits; it does not stop the project owner.
- **Backups are only as good as their first restore test.** Set up the two GitHub secrets and run a restore once.
- **Gemini billing and terms** must be reviewed by the owner before it is ever enabled.
- **Browser matrix not run** (Safari/Firefox cookie behaviour, phone layouts, keyboard and screen-reader use).
- **No rate limit on uploads or chat** beyond the quotas; a signed-in student can still make many requests.
- **No external penetration test** (out of budget).
