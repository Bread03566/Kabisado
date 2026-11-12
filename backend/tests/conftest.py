"""
Test isolation: point the app at a throwaway database and upload folder, and switch the AI off
so tests are fast, free, and deterministic. This must run before anything imports `app`.

By default tests use a temporary SQLite file whose schema is created from the models. CI also runs the
suite against Postgres by exporting DATABASE_URL and AUTO_CREATE_SCHEMA=false (schema from Alembic).
"""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="kabisado-tests-")
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
    os.environ.setdefault("AUTO_CREATE_SCHEMA", "true")
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.environ["GEMINI_API_KEY"] = ""
os.environ["GEMINI_ENABLED"] = "false"
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-0123456789")
os.environ.setdefault("ARGON2_MEMORY_KIB", "1024")  # fast hashing in tests; production uses 19456
os.environ.setdefault("ARGON2_TIME_COST", "1")
os.environ.setdefault("COOKIE_SECURE", "true")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173")
os.environ.setdefault("DEBUG", "true")
