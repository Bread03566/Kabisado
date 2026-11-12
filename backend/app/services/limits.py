"""Upload validation and storage limits.

Originals are never kept: the text is extracted and the file is discarded. Limits therefore apply to the
extracted text, which is what actually takes space in the free database.
"""
import io
import zipfile

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import Document, User

MAX_ZIP_ENTRIES = 2000


def check_file_content(ext: str, contents: bytes) -> None:
    """The bytes must really be what the extension says; a renamed file is rejected, not parsed."""
    if ext == "pdf":
        if not contents.lstrip(b"\x00\r\n ")[:5] == b"%PDF-":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "That file is not a real PDF.")
        return
    try:
        archive = zipfile.ZipFile(io.BytesIO(contents))
        entries = archive.infolist()
    except zipfile.BadZipFile:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That file is not a real Word (.docx) document.")
    names = {e.filename for e in entries}
    if "[Content_Types].xml" not in names or "word/document.xml" not in names:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That file is not a real Word (.docx) document.")
    if any(n.endswith("vbaProject.bin") for n in names):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Documents with macros are not accepted.")
    limit = settings.DOCX_MAX_UNCOMPRESSED_MB * 1024 * 1024
    if len(entries) > MAX_ZIP_ENTRIES or sum(e.file_size for e in entries) > limit:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That document is too large once unpacked.")


def check_text_length(text: str) -> None:
    if len(text) > settings.MAX_TEXT_CHARS:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"That module is too long ({settings.MAX_TEXT_CHARS:,} characters at most). Try splitting it.",
        )


def check_quota(db: Session, user: User, new_chars: int) -> None:
    """Refuse when this student, or the whole free database, would go over budget."""
    docs, used = db.query(func.count(Document.id), func.coalesce(func.sum(func.length(Document.raw_text)), 0)) \
        .filter(Document.user_id == user.id).one()
    if docs >= settings.MAX_DOCS_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"You have reached the limit of {settings.MAX_DOCS_PER_USER} modules. Delete one to add another.",
        )
    if used + new_chars > settings.STUDENT_TEXT_QUOTA_KB * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "You have used up your storage. Delete a module you no longer need to make room.",
        )
    total = db.query(func.coalesce(func.sum(func.length(Document.raw_text)), 0)).scalar()
    if total + new_chars >= settings.GLOBAL_TEXT_QUOTA_MB * 1024 * 1024 * 0.9:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Kabisado's storage is full right now, so new modules cannot be added. Please try again later.",
        )
