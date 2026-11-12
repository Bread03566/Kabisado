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
