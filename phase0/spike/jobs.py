"""Resumable, idempotent job runner (Phase 0 prototype). Not application code."""
import time
S = "phase0"
DDL = f"""
create schema if not exists {S};
create table if not exists {S}.jobs(id text primary key, status text not null default 'queued',
  lease_until timestamptz, attempts int not null default 0, total int not null);
create table if not exists {S}.job_chunks(job_id text references {S}.jobs(id) on delete cascade,
  idx int, written_by text, primary key(job_id, idx));
"""

def ensure(conn):
    conn.execute(DDL)

def submit(conn, key, total):
    conn.execute(f"insert into {S}.jobs(id,total) values(%s,%s) on conflict do nothing", (key, total))
    return key

def claim(conn, job_id, lease=5):
    row = conn.execute(
        f"update {S}.jobs set status='running', lease_until=now()+make_interval(secs=>%s), attempts=attempts+1 "
        f"where id=%s and status in ('queued','running') and (lease_until is null or lease_until<now()) returning total",
        (lease, job_id)).fetchone()
    return row[0] if row else None

def run(conn, job_id, worker, lease=5, chunk_delay=0.4):
    total = claim(conn, job_id, lease)
    if total is None:
        return False
    done = {r[0] for r in conn.execute(f"select idx from {S}.job_chunks where job_id=%s", (job_id,))}
    for idx in range(total):
        if idx in done:
            continue
        time.sleep(chunk_delay)
        with conn.transaction():
            conn.execute(f"insert into {S}.job_chunks(job_id,idx,written_by) values(%s,%s,%s) on conflict do nothing",
                         (job_id, idx, worker))
            conn.execute(f"update {S}.jobs set lease_until=now()+make_interval(secs=>%s) where id=%s", (lease, job_id))
            if idx == total - 1:
                conn.execute(f"update {S}.jobs set status='done' where id=%s", (job_id,))
    return True

def stale(conn):
    return [r[0] for r in conn.execute(
        f"select id from {S}.jobs where status in ('queued','running') and (lease_until is null or lease_until<now())")]

def state(conn, job_id):
    j = conn.execute(f"select status,attempts,total from {S}.jobs where id=%s", (job_id,)).fetchone()
    n = conn.execute(f"select count(*), count(distinct idx) from {S}.job_chunks where job_id=%s", (job_id,)).fetchone()
    return dict(status=j[0], attempts=j[1], total=j[2], chunks=n[0], distinct=n[1]) if j else None
