from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import BASE_DIR, settings

def build_engine(url: str):
    """
    SQLite (dev/tests): thread check off, foreign keys on, WAL.
    Postgres: a small persistent pool. Opening a connection to Supabase from Render costs ~1.4 s, so
    connections are reused, checked before use, and recycled before the pooler drops them.
    """
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False}, echo=False)

        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        return eng
    return create_engine(
        url,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False,
        connect_args={
            # Never wait forever on a silent network: fail fast so the platform restarts us and the log says why.
            "connect_timeout": settings.DB_CONNECT_TIMEOUT,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
            "tcp_user_timeout": 30000,  # ms: drop a connection whose data goes unacknowledged
        },
    )


engine = build_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def ensure_schema(bind=None, auto_create=None):
    """
    The schema is owned by Alembic. With AUTO_CREATE_SCHEMA (local dev and tests) tables are created
    straight from the models. Otherwise the database must already be at the latest migration, and the
    app refuses to start if it is not, so code and schema can never silently drift apart.
    Deploy order: run `alembic upgrade head` first, then deploy the new code.
    """
    import app.models.models  # noqa: F401  (registers every table on Base.metadata)
    bind = bind if bind is not None else engine
    auto = settings.AUTO_CREATE_SCHEMA if auto_create is None else auto_create
    if auto:
        Base.metadata.create_all(bind=bind)
        return
    cfg = Config()
    cfg.set_main_option("script_location", str(BASE_DIR / "migrations"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    with bind.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    if current != head:
        raise RuntimeError(
            f"Database schema is at revision {current}, expected {head}. Run: alembic upgrade head"
        )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
