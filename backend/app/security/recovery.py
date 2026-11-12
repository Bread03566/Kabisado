"""Recovery codes: 128 random bits, shown once, stored only as an Argon2id hash."""
import base64
import secrets

from app.security.passwords import hash_password, hash_password_sync, verify_password, verify_password_sync


def generate_recovery_code() -> str:
    """26 base32 characters formatted XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XX."""
    raw = base64.b32encode(secrets.token_bytes(16)).decode("ascii").rstrip("=")
    return "-".join([raw[i:i + 4] for i in range(0, 24, 4)] + [raw[24:]])


def normalize_recovery_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch not in " -\t\r\n")


async def hash_recovery_code(code: str) -> str:
    return await hash_password(normalize_recovery_code(code))


async def verify_recovery_code(hash_: str | None, code: str) -> bool:
    return await verify_password(hash_, normalize_recovery_code(code))


def hash_recovery_code_sync(code: str) -> str:
    return hash_password_sync(normalize_recovery_code(code))


def verify_recovery_code_sync(hash_: str | None, code: str) -> bool:
    return verify_password_sync(hash_, normalize_recovery_code(code))
