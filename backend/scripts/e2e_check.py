"""End-to-end check against a running Kabisado deployment (standard library only).

    python backend/scripts/e2e_check.py https://your-service.onrender.com
    # optional, to also verify the admin role: set E2E_ADMIN_USERNAME and E2E_ADMIN_PASSWORD
    # (create that admin first with `python -m app.cli create-admin`)

It registers two throwaway students, checks isolation, role enforcement, cookie refresh and latency,
then deletes both accounts again. It prints a Markdown report you can paste into docs/phase2-results.md.
Exit code 1 if any check failed.
"""
import http.cookiejar
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid

PASSWORD = "E2e-Check-Pass-" + uuid.uuid4().hex[:8]
results = []


class Session:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.token = None

    def call(self, method, path, body=None, auth=True, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Kabisado-Request", "1")
        if auth and self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        start = time.perf_counter()
        try:
            with self.opener.open(req, timeout=120) as res:
                raw, status = res.read(), res.status
        except urllib.error.HTTPError as err:
            raw, status = err.read(), err.code
        ms = (time.perf_counter() - start) * 1000
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = None
        return status, parsed, ms


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)
    return ok


def register(base, label):
    s = Session(base)
    username = f"e2e{label}{uuid.uuid4().hex[:8]}"
    status, body, ms = s.call("POST", "/api/auth/register", {
        "display_name": f"E2E {label}", "username": username, "password": PASSWORD, "confirm_password": PASSWORD}, auth=False)
    check(f"register student {label}", status == 201, f"{status}, {ms:.0f} ms")
    if status == 201:
        s.token = body["access_token"]
    s.username = username
    return s


def median_ms(fn, n=5):
    samples = [fn() for _ in range(n)]
    return statistics.median(samples), max(samples)


def main(base):
    status, health, _ = Session(base).call("GET", "/api/health", auth=False)
    check("health reachable", status == 200)
    check("Gemini is off (no AI configured)", health and health.get("ai_configured") is False, str(health and health.get("ai_provider")))

    alice, bob = register(base, "a"), register(base, "b")
    try:
        doc = alice.call("POST", "/api/documents/text", {
            "title": "E2E private notes", "text": "The Katipunan was founded in 1892. " * 20})[1]
        check("alice created a document", bool(doc and doc.get("id")))
        bob_docs = bob.call("GET", "/api/documents")[1] or []
        check("bob does not see alice's document", all(d["id"] != doc["id"] for d in bob_docs))
        check("bob gets 404 for alice's document", bob.call("GET", f"/api/documents/{doc['id']}")[0] == 404)
        check("anonymous request is 401", Session(base).call("GET", "/api/documents", auth=False)[0] == 401)
        check("student cannot reach /api/admin/ping (403)", alice.call("GET", "/api/admin/ping")[0] == 403)

        admin_user, admin_pw = os.environ.get("E2E_ADMIN_USERNAME"), os.environ.get("E2E_ADMIN_PASSWORD")
        if admin_user and admin_pw:
            adm = Session(base)
            status, body, _ = adm.call("POST", "/api/auth/login", {"username": admin_user, "password": admin_pw}, auth=False)
            adm.token = body and body.get("access_token")
            check("admin can reach /api/admin/ping (200)", status == 200 and adm.call("GET", "/api/admin/ping")[0] == 200)
        else:
            check("admin role check", True, "skipped: E2E_ADMIN_USERNAME/PASSWORD not set")

        # A page reload keeps you signed in: the browser sends the refresh cookie, no access token is available.
        alice.token = None
        status, body, _ = alice.call("POST", "/api/auth/refresh", auth=False)
        check("refresh via cookie survives a 'reload'", status == 200 and body and body.get("access_token"), str(status))
        alice.token = body and body.get("access_token")

        login_med, login_max = median_ms(lambda: alice.call("POST", "/api/auth/login", {
            "username": alice.username, "password": PASSWORD}, auth=False)[2])
        list_med, list_max = median_ms(lambda: alice.call("GET", "/api/documents")[2])
        check("login latency measured", True, f"median {login_med:.0f} ms, max {login_max:.0f} ms (Argon2id + DB round trips)")
        check("documents list latency measured", True, f"median {list_med:.0f} ms, max {list_max:.0f} ms")

        summary = alice.call("POST", f"/api/documents/{doc['id']}/summarize", {"length": "brief"})
        check("summary is the offline version (Gemini disabled)", summary[0] == 200 and bool(summary[1] and summary[1].get("summary")), str(summary[0]))
    finally:
        for s in (alice, bob):
            _, body, _ = s.call("POST", "/api/auth/login", {"username": s.username, "password": PASSWORD}, auth=False)
            s.token = body and body.get("access_token")
            status = s.call("DELETE", "/api/auth/account", {"password": PASSWORD})[0]
            check(f"cleanup: deleted {s.username}", status == 204, str(status))

    print("\n| Check | Result | Detail |\n|---|---|---|")
    for name, ok, detail in results:
        print(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |")
    print("\nStill to do by hand: restart the Render service and re-run with an existing account to confirm data survives.")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].startswith(("http://", "https://")):
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
