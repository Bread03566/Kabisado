from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

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
    )


engine = build_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    import app.models.models
    Base.metadata.create_all(bind=engine)
    add_missing_columns()

def add_missing_columns():
    """
    create_all() only creates missing tables. Columns added to an existing model later
    (e.g. questions.question_type) are added here, so existing databases keep working.
    New columns must be nullable or have a server_default.
    """
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(engine.dialect)}'
                if column.server_default is not None:
                    ddl += f" DEFAULT '{column.server_default.arg}'"
                conn.execute(text(ddl))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
