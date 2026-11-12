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
