from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.identity import require_admin
from app.models.models import AuditLog, Document, Flashcard, QuizAttempt, Question, User
from app.security.sessions import revoke_all_for_user

router = APIRouter(prefix="/api/admin", tags=["admin"])

PAGE_LIMIT = 100


@router.get("/ping")
def ping(_: User = Depends(require_admin)):
    """Proves server-side role enforcement."""
    return {"ok": True}


@router.get("/overview")
def overview(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    def count(model, *conds):
        return db.query(func.count(model.id)).filter(*conds).scalar() or 0

    return {
        "students": count(User, User.role == "student"),
        "active_students": count(User, User.role == "student", User.is_active.is_(True)),
        "disabled_students": count(User, User.role == "student", User.is_active.is_(False)),
        "admins": count(User, User.role == "admin"),
        "documents": count(Document),
        "flashcards": count(Flashcard),
        "questions": count(Question),
        "quiz_attempts": count(QuizAttempt),
    }


@router.get("/students")
def list_students(q: str = Query("", max_length=60), _: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Account metadata only: never study content, hashes or tokens."""
    docs = (db.query(Document.user_id, func.count(Document.id).label("n")).group_by(Document.user_id).subquery())
    query = db.query(User, func.coalesce(docs.c.n, 0)).outerjoin(docs, docs.c.user_id == User.id)
    term = q.strip().lower()
    if term:
        like = f"%{term.replace('%', '').replace('_', '')}%"
        query = query.filter(or_(func.lower(User.username).like(like), func.lower(User.display_name).like(like)))
    rows = query.filter(User.password_hash.isnot(None)).order_by(User.created_at.desc(), User.id.desc()).limit(PAGE_LIMIT).all()
    return {"students": [
        {
            "id": u.public_id, "username": u.username, "display_name": u.display_name, "role": u.role,
            "is_active": u.is_active, "created_at": u.created_at, "last_login_at": u.last_login_at,
            "document_count": n,
        }
        for u, n in rows
    ]}


def _target(db: Session, admin: User, public_id: str) -> User:
    user = db.query(User).filter(User.public_id == public_id).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")
    if user.id == admin.id or user.role != "student":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only student accounts can be changed here.")
    return user


def _audit(db: Session, admin: User, action: str, target: User) -> None:
    db.add(AuditLog(actor_id=admin.id, actor_username=admin.username, action=action, target_ref=target.public_id))


@router.post("/students/{public_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_student(public_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = _target(db, admin, public_id)
    user.is_active = False
    _audit(db, admin, "student.deactivate", user)
    db.commit()
    revoke_all_for_user(db, user.id)  # signs them out everywhere; the access token dies on its next DB check
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/students/{public_id}/reactivate", status_code=status.HTTP_204_NO_CONTENT)
def reactivate_student(public_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = _target(db, admin, public_id)
    user.is_active = True
    _audit(db, admin, "student.reactivate", user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/audit")
def audit_log(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(PAGE_LIMIT).all()
    return {"entries": [
        {"id": r.id, "action": r.action, "actor": r.actor_username, "target": r.target_ref, "created_at": r.created_at}
        for r in rows
    ]}
