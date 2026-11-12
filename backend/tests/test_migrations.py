from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.database import Base, ensure_schema

BACKEND = Path(__file__).resolve().parent.parent


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture
def sqlite_url(tmp_path):
    return f"sqlite:///{(tmp_path / 'm.db').as_posix()}"


def test_upgrade_head_matches_models(sqlite_url):
    import app.models.models  # noqa: F401  (registers every table on Base.metadata)

    command.upgrade(alembic_config(sqlite_url), "head")
    insp = inspect(create_engine(sqlite_url))
    assert insp.has_table("alembic_version")
    for table in Base.metadata.sorted_tables:
        assert insp.has_table(table.name), f"migration is missing table {table.name}"
        actual = {c["name"] for c in insp.get_columns(table.name)}
        expected = {c.name for c in table.columns}
        assert expected <= actual, f"{table.name} is missing columns {expected - actual}"
        assert actual <= expected, f"{table.name} has columns the models do not: {actual - expected}"


def test_ensure_schema_fails_on_empty_db_without_autocreate(sqlite_url):
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        ensure_schema(bind=create_engine(sqlite_url), auto_create=False)


def test_ensure_schema_ok_after_upgrade(sqlite_url):
    command.upgrade(alembic_config(sqlite_url), "head")
    ensure_schema(bind=create_engine(sqlite_url), auto_create=False)  # must not raise


def test_ensure_schema_autocreate_builds_tables(sqlite_url):
    engine = create_engine(sqlite_url)
    ensure_schema(bind=engine, auto_create=True)
    assert inspect(engine).has_table("users")


def _insert_user(conn, username, role="student"):
    conn.exec_driver_sql(
        "INSERT INTO users (public_id, display_name, username, role, subject_ref) VALUES (?, ?, ?, ?, ?)",
        (f"pid-{username}", username, username, role, f"ref-{username}"),
    )


def test_role_check_constraint(sqlite_url):
    from sqlalchemy.exc import IntegrityError

    command.upgrade(alembic_config(sqlite_url), "head")
    engine = create_engine(sqlite_url)
    with engine.begin() as conn:
        _insert_user(conn, "ok-student")
        _insert_user(conn, "ok-admin", role="admin")
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            _insert_user(conn, "rooty", role="root")


def test_legacy_client_users_survive_but_cannot_authenticate(sqlite_url):
    cfg = alembic_config(sqlite_url)
    command.upgrade(cfg, "0001")
    engine = create_engine(sqlite_url)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO users (username, email, created_at) VALUES ('client-0123456789abcdef', 'x@y.z', '2026-01-01 00:00:00')"
        )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT username, display_name, password_hash, recovery_hash, role, is_active, public_id, subject_ref FROM users"
        ).one()
    assert row.username == "client-0123456789abcdef"      # nothing deleted
    assert row.password_hash is None and row.recovery_hash is None  # cannot log in
    assert row.display_name == row.username
    assert row.role == "student" and bool(row.is_active)
    assert row.public_id and row.subject_ref and len(row.subject_ref) == 32


def test_users_email_column_is_gone(sqlite_url):
    command.upgrade(alembic_config(sqlite_url), "head")
    assert "email" not in {c["name"] for c in inspect(create_engine(sqlite_url)).get_columns("users")}
    insp = inspect(create_engine(sqlite_url))
    assert insp.has_table("sessions") and insp.has_table("login_attempts")
