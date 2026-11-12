import pytest

from app.config import normalize_database_url
from app.database import build_engine


@pytest.mark.parametrize("raw,expected", [
    ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
    ("postgresql://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
    ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ("sqlite:///./x.db", "sqlite:///./x.db"),
])
def test_normalize_database_url(raw, expected):
    assert normalize_database_url(raw) == expected


def test_postgres_engine_uses_a_small_persistent_pool():
    # Building the engine must not connect (no server here); it only configures the pool.
    engine = build_engine("postgresql+psycopg://u:p@localhost:5432/db")
    assert engine.pool.size() == 3
    assert engine.pool._max_overflow == 2
    assert engine.pool._pre_ping is True
    assert engine.pool._recycle == 300


def test_sqlite_engine_keeps_thread_check_off(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path.as_posix()}/t.db")
    with engine.connect() as conn:
        assert conn.exec_driver_sql("pragma foreign_keys").scalar() == 1


def test_a_database_that_accepts_the_connection_but_never_answers_times_out(monkeypatch):
    """Render once sat silent for ~18 minutes at startup. A stalled database must fail fast instead."""
    import socket
    import threading
    import time

    from sqlalchemy.exc import OperationalError

    from app.config import settings

    monkeypatch.setattr(settings, "DB_CONNECT_TIMEOUT", 2)
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(5)  # accepts TCP connections in the kernel, never speaks the Postgres protocol
    port = server.getsockname()[1]
    outcome = {}

    def attempt():
        engine = build_engine(f"postgresql+psycopg://u:p@127.0.0.1:{port}/db")
        start = time.time()
        try:
            engine.connect()
        except OperationalError as err:
            outcome["error"] = err
        outcome["seconds"] = time.time() - start

    worker = threading.Thread(target=attempt, daemon=True)
    worker.start()
    worker.join(timeout=10)
    server.close()
    assert not worker.is_alive(), "connect() hung instead of timing out"
    assert "error" in outcome and outcome["seconds"] < 8
