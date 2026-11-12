from fastapi import APIRouter, Depends

from app.identity import require_admin
from app.models.models import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/ping")
def ping(_: User = Depends(require_admin)):
    """Placeholder that proves server-side role enforcement; the real dashboard replaces it in a later phase."""
    return {"ok": True}
