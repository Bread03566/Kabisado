"""Local Phase 0 tests against throwaway Postgres 16. Prints PASS/FAIL per test."""
import hashlib, json, os, random, secrets, subprocess, sys, threading, time, traceback
import psycopg
sys.path.insert(0, "/work/spike")
import dbconn, jobs

RESULTS = []


def test(fn):
    try:
        info = fn()
        RESULTS.append((fn.__name__, "PASS", info or ""))
    except Exception as e:
        traceback.print_exc()
        RESULTS.append((fn.__name__, "FAIL", repr(e)))
    return fn


def admin(dbname="postgres"):
    k = dbconn.kwargs()
    k["dbname"] = dbname
    return psycopg.connect(**k, autocommit=True)


def newdb(name):
    a = admin()
    a.execute(f"drop database if exists {name}")
    a.execute(f"create database {name}")
    return admin(name)


PGENV = {**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "")}
HOST = dbconn.kwargs()["host"]

# ---------- 3. hash chain keyed by random subject_ref ----------
CHAIN_DDL = """
create table users(id serial primary key, username text unique, subject_ref text unique not null);
create table consent_log(id bigserial primary key, subject_ref text not null, action text not null,
  policy_version text, created_at text not null, prev_hash text not null, row_hash text not null);
"""


def row_hash(prev, ref, action, pv, ts):
    return hashlib.sha256("|".join([prev, ref, action, pv or "", ts]).encode()).hexdigest()


def append(c, ref, action, pv):
    prev = c.execute("select row_hash from consent_log where subject_ref=%s order by id desc limit 1", (ref,)).fetchone()
    prev = prev[0] if prev else "0" * 64
    ts = f"{time.time():.6f}"
    c.execute("insert into consent_log(subject_ref,action,policy_version,created_at,prev_hash,row_hash) values(%s,%s,%s,%s,%s,%s)",
              (ref, action, pv, ts, prev, row_hash(prev, ref, action, pv, ts)))


def verify(c):
    bad = 0
    for (ref,) in c.execute("select distinct subject_ref from consent_log").fetchall():
        prev = "0" * 64
        for _id, action, pv, ts, ph, rh in c.execute(
                "select id,action,policy_version,created_at,prev_hash,row_hash from consent_log where subject_ref=%s order by id",
                (ref,)).fetchall():
            if ph != prev or row_hash(prev, ref, action, pv, ts) != rh:
                bad += 1
            prev = rh
    return bad


@test
def chain_survives_user_deletion_and_is_append_only():
    c = newdb("t_chain")
    c.execute(CHAIN_DDL)
    refs = {}
    for u in ("ana", "ben"):
        refs[u] = secrets.token_hex(16)
        c.execute("insert into users(username,subject_ref) values(%s,%s)", (u, refs[u]))
        for a, pv in (("grant", "v1"), ("withdraw", "v1"), ("grant", "v2")):
            append(c, refs[u], a, pv)
    assert verify(c) == 0
    c.execute("delete from users where username='ana'")  # erasure severs the link only
    assert c.execute("select count(*) from consent_log where subject_ref=%s", (refs["ana"],)).fetchone()[0] == 3
    assert verify(c) == 0, "chain broke after deletion"
    c.execute("create role kapp login password 'x'")
    c.execute("grant select,insert on consent_log to kapp")
    c.execute("grant usage on all sequences in schema public to kapp")
    k = dbconn.kwargs()
    k.update(dbname="t_chain", user="kapp", password="x")
    r = psycopg.connect(**k, autocommit=True)
    for sql in ("update consent_log set action='x'", "delete from consent_log"):
        try:
            r.execute(sql)
            raise AssertionError("app role could run: " + sql)
        except psycopg.errors.InsufficientPrivilege:
            pass
    # tamper detection (as owner, simulating a rewrite)
    c.execute("update consent_log set action='grant' where subject_ref=%s and action='withdraw'", (refs["ben"],))
    assert verify(c) > 0, "tamper not detected"
    return "chain verifies after deleting the user; app role cannot UPDATE/DELETE; owner-level tamper is detected"


# ---------- 2. backup / restore / deletion replay ----------
@test
def restore_resurrects_then_ledger_replay_deletes():
    c = newdb("t_src")
    c.execute(CHAIN_DDL + "create table documents(id serial primary key, user_id int references users(id) on delete cascade, body text);")
    refs = {}
    for u in ("ana", "ben"):
        refs[u] = secrets.token_hex(16)
        c.execute("insert into users(username,subject_ref) values(%s,%s)", (u, refs[u]))
        uid = c.execute("select id from users where username=%s", (u,)).fetchone()[0]
        c.execute("insert into documents(user_id,body) values(%s,%s)", (uid, f"{u} notes"))
        append(c, refs[u], "grant", "v1")
    subprocess.run(["pg_dump", "-Fc", "-h", HOST, "-U", "postgres", "-d", "t_src", "-f", "/tmp/old.dump"], check=True, env=PGENV)
    uid = c.execute("select id from users where username='ana'").fetchone()[0]
    c.execute("delete from users where id=%s", (uid,))  # ana deletes her account after the backup
    json.dump([{"ref": refs["ana"]}], open("/tmp/ledger.json", "w"))  # tombstone kept OUTSIDE the db
    a = admin()
    a.execute("drop database if exists t_restored")
    a.execute("create database t_restored")
    subprocess.run(["pg_restore", "-h", HOST, "-U", "postgres", "-d", "t_restored", "/tmp/old.dump"], check=True, env=PGENV)
    r = admin("t_restored")
    assert r.execute("select count(*) from users where username='ana'").fetchone()[0] == 1, "expected resurrection"
    for _ in range(2):  # replay must be idempotent
        for t in json.load(open("/tmp/ledger.json")):
            r.execute("delete from users where subject_ref=%s", (t["ref"],))
    assert r.execute("select count(*) from users where username='ana'").fetchone()[0] == 0
    assert r.execute("select count(*) from documents d join users u on u.id=d.user_id where u.username='ana'").fetchone()[0] == 0
    assert r.execute("select count(*) from users where username='ben'").fetchone()[0] == 1
    assert verify(r) == 0
    return "old backup RESURRECTED the deleted user (confirms the risk); ledger replay removed her and her docs (idempotent); ben intact; chain verifies"


# ---------- 6. jobs ----------
def fresh_jobs_db(name):
    c = newdb(name)
    jobs.ensure(c)
    k = dbconn.kwargs()
    k["dbname"] = name
    return c, k


@test
def job_resumes_after_process_kill_without_duplicates():
    c, k = fresh_jobs_db("t_jobs1")
    jobs.submit(c, "doc-1", 12)
    code = ("import sys,psycopg;sys.path.insert(0,'/work/spike');import jobs;"
            f"c=psycopg.connect(**{k!r},autocommit=True);jobs.run(c,'doc-1','proc-A',lease=2,chunk_delay=0.3)")
    p = subprocess.Popen([sys.executable, "-c", code])
    time.sleep(2.0)
    p.kill()
    p.wait()  # simulates Render spin-down / restart mid-job
    mid = jobs.state(c, "doc-1")
    assert mid["status"] == "running" and 0 < mid["chunks"] < 12, mid
    assert jobs.run(c, "doc-1", "proc-B", lease=2) is False, "claimed while the lease was still valid"
    time.sleep(2.3)
    assert "doc-1" in jobs.stale(c)
    assert jobs.run(c, "doc-1", "proc-B", lease=2, chunk_delay=0.05)
    fin = jobs.state(c, "doc-1")
    assert fin["status"] == "done" and fin["chunks"] == 12 == fin["distinct"], fin
    return f"killed after {mid['chunks']}/12 chunks; second worker resumed only after lease expiry; final {fin}"


@test
def duplicate_submit_and_worker_race_yield_single_result():
    c, k = fresh_jobs_db("t_jobs2")
    for _ in range(5):
        jobs.submit(c, "doc-2", 10)
    assert c.execute("select count(*) from phase0.jobs").fetchone()[0] == 1
    wins = []

    def w(name):
        cc = psycopg.connect(**k, autocommit=True)
        wins.append((name, jobs.run(cc, "doc-2", name, lease=30, chunk_delay=0.05)))

    ts = [threading.Thread(target=w, args=(f"w{i}",)) for i in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    fin = jobs.state(c, "doc-2")
    assert sum(1 for _, ok in wins if ok) == 1, wins
    assert fin["chunks"] == 10 == fin["distinct"] and fin["status"] == "done", fin
    return f"5 submits -> 1 job; 4 racing workers -> 1 winner; {fin}"


@test
def lost_client_is_irrelevant_server_finishes():
    c, k = fresh_jobs_db("t_jobs3")
    jobs.submit(c, "doc-3", 6)
    t = threading.Thread(target=lambda: jobs.run(psycopg.connect(**k, autocommit=True), "doc-3", "srv", chunk_delay=0.05))
    t.start()
    t.join()  # no client ever polls
    assert jobs.state(c, "doc-3")["status"] == "done"
    return "job completes with no client attached"


# ---------- 4. storage measurement ----------
WORDS = ("cell membrane protein energy mitochondria nucleus enzyme substrate reaction catalyst structure function "
         "photosynthesis chlorophyll light glucose oxygen carbon dioxide respiration atp molecule bond ionic covalent "
         "electron proton neutron atom element compound mixture solution acid base buffer equilibrium rate temperature "
         "pressure volume gas liquid solid law theory hypothesis variable control experiment data analysis result "
         "conclusion the of and to in is that for it as with be by this are on or an which from at can each these between").split()


def fake_text(n_chars):
    out, n = [], 0
    while n < n_chars:
        s = " ".join(random.choice(WORDS) for _ in range(random.randint(8, 22))).capitalize() + ". "
        out.append(s)
        n += len(s)
    return "".join(out)


@test
def measure_storage_per_document():
    random.seed(1)
    c = newdb("t_size")
    c.execute("""create table chunks(id serial primary key, doc int, ord int, body text, tsv tsvector);
                 create index chunks_tsv on chunks using gin(tsv);
                 create table cards(id serial primary key, doc int, front text, back text, ease float, ivl int, due timestamptz);
                 create table questions(id serial primary key, doc int, q text, choices jsonb, expl text);""")
    docs, text_len = 60, 80_000
    for d in range(docs):
        text = fake_text(text_len)
        for i in range(0, len(text), 1500):
            part = text[i:i + 1500]
            c.execute("insert into chunks(doc,ord,body,tsv) values(%s,%s,%s,to_tsvector('english',%s))", (d, i, part, part))
        for _ in range(25):
            c.execute("insert into cards(doc,front,back,ease,ivl,due) values(%s,%s,%s,2.5,0,now())", (d, fake_text(90), fake_text(160)))
        for _ in range(20):
            c.execute("insert into questions(doc,q,choices,expl) values(%s,%s,%s,%s)",
                      (d, fake_text(120), json.dumps([fake_text(40) for _ in range(4)]), fake_text(200)))
    c.execute("analyze")
    tot = {t: c.execute("select pg_total_relation_size(%s)", (t,)).fetchone()[0] for t in ("chunks", "cards", "questions")}
    per_doc = sum(tot.values()) / docs
    return (f"{docs} docs x {text_len // 1000}KB text -> {per_doc / 1e3:.0f} KB/doc "
            f"(chunks+fts+gin {tot['chunks'] / docs / 1e3:.0f}, cards {tot['cards'] / docs / 1e3:.0f}, "
            f"questions {tot['questions'] / docs / 1e3:.0f} KB/doc); 10 docs/student = {per_doc * 10 / 1e6:.1f} MB")


print("\n==== RESULTS ====")
for n, s, i in RESULTS:
    print(f"[{s}] {n}\n      {i}")
sys.exit(0 if all(s == "PASS" for _, s, _ in RESULTS) else 1)
