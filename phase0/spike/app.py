"""Phase 0 throwaway spike service. Contains NO Gemini code. Not application code."""
import os, time, resource, threading, uuid, concurrent.futures as cf
from fastapi import FastAPI, Response, Request
from argon2 import PasswordHasher
import dbconn, jobs

START = time.time()
BOOT_ID = uuid.uuid4().hex[:8]
app = FastAPI(docs_url=None, redoc_url=None)
pool = cf.ThreadPoolExecutor(max_workers=2)
sem = threading.Semaphore(2)

def rss_mb():
    try:
        for line in open("/proc/self/status"):
            if line.startswith("VmRSS"):
                return int(line.split()[1]) / 1024
    except OSError:
        return None

def have_db():
    return bool(os.getenv("SUPABASE_DB_HOST") or os.getenv("PGHOST"))

def spawn(job_id):
    def target():
        c = dbconn.connect()
        try:
            jobs.run(c, job_id, worker=f"{BOOT_ID}")
        finally:
            c.close()
    threading.Thread(target=target, daemon=True).start()

@app.on_event("startup")
def sweep_on_boot():
    if have_db():
        try:
            c = dbconn.connect(); jobs.ensure(c)
            for j in jobs.stale(c):
                spawn(j)
            c.close()
        except Exception as e:  # report, don't crash boot
            print("startup sweep failed:", repr(e))

@app.get("/health")
def health():
    return {"boot_id": BOOT_ID, "uptime_s": round(time.time() - START, 1), "rss_mb": rss_mb()}

def one_hash(m, t):
    with sem:
        ph = PasswordHasher(time_cost=t, memory_cost=m, parallelism=1)
        a = time.perf_counter(); h = ph.hash("correct horse battery"); hm = time.perf_counter() - a
        a = time.perf_counter(); ph.verify(h, "correct horse battery"); vm = time.perf_counter() - a
        return round(hm * 1000), round(vm * 1000)

@app.get("/argon2")
def argon2(m: int = 19456, t: int = 2, n: int = 3):
    m = min(m, 65536); n = min(n, 6)
    t0 = time.perf_counter()
    res = list(pool.map(lambda _: one_hash(m, t), range(n)))
    return {"memory_kib": m, "time_cost": t, "parallel": n, "per_call_ms(hash,verify)": res,
            "wall_ms": round((time.perf_counter() - t0) * 1000), "rss_mb": rss_mb(),
            "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)}

@app.get("/db")
def db():
    if not have_db():
        return {"error": "no DB env configured"}
    a = time.perf_counter()
    c = dbconn.connect(); conn_ms = (time.perf_counter() - a) * 1000
    ver = c.execute("select version()").fetchone()[0]
    lat = []
    for _ in range(10):
        a = time.perf_counter(); c.execute("select 1").fetchone(); lat.append((time.perf_counter() - a) * 1000)
    c.close()
    return {"version": ver, "connect_ms": round(conn_ms), "select1_ms_avg": round(sum(lat) / 10, 1),
            "select1_ms_max": round(max(lat), 1)}

@app.get("/cookie/set")
def cookie_set(resp: Response):
    resp.set_cookie("__Host-p0", BOOT_ID, httponly=True, secure=True, samesite="strict", path="/", max_age=3600)
    return {"set": True}

@app.get("/cookie/get")
def cookie_get(request: Request):
    return {"cookie": request.cookies.get("__Host-p0")}

@app.post("/job/start")
def job_start(key: str, total: int = 20):
    c = dbconn.connect(); jobs.ensure(c)
    jobs.submit(c, key, min(total, 200)); c.close()
    spawn(key)
    return {"key": key}

@app.get("/job/sweep")
def job_sweep():
    c = dbconn.connect(); ids = jobs.stale(c); c.close()
    for j in ids:
        spawn(j)
    return {"requeued": ids}

@app.get("/job/{key}")
def job_get(key: str):
    c = dbconn.connect(); s = jobs.state(c, key); c.close()
    return {"boot_id": BOOT_ID, **(s or {"status": "unknown"})}
