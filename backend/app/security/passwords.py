"""Password policy and Argon2id hashing.

Hashing runs on a dedicated two-thread pool: Argon2 is CPU-heavy and Render Free has ~0.1 CPU, so more
than two at once only makes every login slower, and running it on the event loop would stall all requests.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import settings

MIN_LENGTH = 10
MAX_LENGTH = 128

_COMMON = {
    line.strip().lower()
    for line in (Path(__file__).with_name("common_passwords.txt")).read_text(encoding="utf-8").splitlines()
    if line.strip()
}

_hasher = PasswordHasher(
    time_cost=settings.ARGON2_TIME_COST,
    memory_cost=settings.ARGON2_MEMORY_KIB,
    parallelism=1,
)
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="argon2")
_DUMMY_HASH = _hasher.hash("kabisado-dummy-password-for-constant-work")


def validate_password(password: str, username: str) -> None:
    """Raise ValueError with a user-facing message. Runs before any hashing."""
    if len(password) < MIN_LENGTH:
        raise ValueError(f"Password must be at least {MIN_LENGTH} characters.")
    if len(password) > MAX_LENGTH:
        raise ValueError(f"Password must be at most {MAX_LENGTH} characters.")
    if password.lower() in _COMMON:
        raise ValueError("That password is too common. Please choose a less guessable one.")
    if username and password.lower() == username.lower():
        raise ValueError("Password cannot be the same as your username.")


def _hash_sync(password: str) -> str:
    return _hasher.hash(password)


def _verify_sync(hash_: str, password: str) -> bool:
    try:
        return _hasher.verify(hash_, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


async def hash_password(password: str) -> str:
    return await asyncio.get_running_loop().run_in_executor(_pool, _hash_sync, password)


async def verify_password(hash_: str | None, password: str) -> bool:
    """With no stored hash (unknown user) still does a full verification so timing does not reveal it."""
    if not hash_:
        await asyncio.get_running_loop().run_in_executor(_pool, _verify_sync, _DUMMY_HASH, password)
        return False
    return await asyncio.get_running_loop().run_in_executor(_pool, _verify_sync, hash_, password)


def needs_rehash(hash_: str) -> bool:
    return _hasher.check_needs_rehash(hash_)
