"""Owner-only maintenance commands. There is deliberately no web endpoint that creates an admin.

    python -m app.cli create-admin --username <name> [--display-name "Name"]
    python -m app.cli purge-legacy --yes

Run these on your own machine with DATABASE_URL pointing at the target database (and any JWT_SECRET value,
which is only needed to load the settings). The Render free tier has no shell.
"""
import argparse
import asyncio
import getpass
import sys

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.account_cleanup import delete_user_files
from app.models.models import User
from app.schemas.auth import USERNAME_RE, normalize_username
from app.security.passwords import hash_password, validate_password
from app.security import retention
from app.security.recovery import generate_recovery_code, hash_recovery_code


class CliError(Exception):
    pass


def create_admin(db: Session, username: str, display_name: str, password: str) -> str:
    """Create an admin account and return its recovery code (shown once, never stored in plaintext)."""
    username = normalize_username(username)
    if not USERNAME_RE.match(username):
        raise CliError("Username must be 3 to 32 characters: letters, numbers, underscore or dot.")
    try:
        validate_password(password, username)
    except ValueError as err:
        raise CliError(str(err)) from err
    if db.query(User.id).filter(User.username == username).first():
        raise CliError(f"A user named '{username}' already exists.")

    code = generate_recovery_code()
    user = User(
        username=username,
        display_name=(display_name or username).strip()[:60] or username,
        password_hash=asyncio.run(hash_password(password)),
        recovery_hash=asyncio.run(hash_recovery_code(code)),
        role="admin",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as err:
        db.rollback()
        raise CliError(f"A user named '{username}' already exists.") from err
    return code


def reactivate(db: Session, username: str) -> None:
    """Undo a deactivation (the student cannot do this themselves because they cannot log in)."""
    user = db.query(User).filter(User.username == normalize_username(username)).first()
    if user is None:
        raise CliError(f"No user named '{username}'.")
    user.is_active = True
    db.commit()


def purge_legacy(db: Session) -> int:
    """Delete accounts that cannot log in (the old per-browser client-id users). Returns how many."""
    legacy = db.query(User).filter(User.password_hash.is_(None)).all()
    for user in legacy:
        delete_user_files(db, user)
        db.delete(user)  # ORM cascade removes their documents, attempts and sessions
    db.commit()
    return len(legacy)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p_admin = sub.add_parser("create-admin", help="create an administrator account")
    p_admin.add_argument("--username", required=True)
    p_admin.add_argument("--display-name", default="")
    p_react = sub.add_parser("reactivate", help="re-enable a deactivated account")
    p_react.add_argument("--username", required=True)
    sub.add_parser("purge-expired", help="delete login/session metadata older than 30 days")
    p_purge = sub.add_parser("purge-legacy", help="delete old client-id accounts that cannot log in")
    p_purge.add_argument("--yes", action="store_true", help="confirm the deletion")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        try:
            if args.command == "create-admin":
                password = getpass.getpass("Password: ")
                if password != getpass.getpass("Confirm password: "):
                    raise CliError("Passwords do not match.")
                code = create_admin(db, args.username, args.display_name, password)
                print("\nAdmin created. Save this recovery code now; it will not be shown again:\n")
                print(f"    {code}\n")
            elif args.command == "reactivate":
                reactivate(db, args.username)
                print(f"Account '{args.username}' is active again.")
            elif args.command == "purge-expired":
                removed = retention.purge_expired(db)
                print(f"Deleted {removed['sessions']} session record(s) and {removed['login_attempts']} login-attempt record(s).")
            else:
                count = db.query(User).filter(User.password_hash.is_(None)).count()
                if not args.yes:
                    raise CliError(f"{count} legacy account(s) would be deleted. Re-run with --yes to confirm.")
                print(f"Deleted {purge_legacy(db)} legacy account(s).")
        except CliError as err:
            print(f"error: {err}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
