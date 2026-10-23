"""
Test isolation: point the app at a throwaway database and upload folder, and switch the AI off
so tests are fast, free, and deterministic. This must run before anything imports `app`.
"""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="kabisado-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.environ["GEMINI_API_KEY"] = ""
