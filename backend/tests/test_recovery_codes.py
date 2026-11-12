import asyncio
import re

from app.security import recovery

FORMAT = re.compile(r"^[A-Z2-7]{4}(-[A-Z2-7]{4}){5}-[A-Z2-7]{2}$")


def test_format():
    assert FORMAT.match(recovery.generate_recovery_code())


def test_codes_are_unique_and_long_enough():
    codes = {recovery.generate_recovery_code() for _ in range(1000)}
    assert len(codes) == 1000
    assert len(recovery.normalize_recovery_code(next(iter(codes)))) == 26  # 26 base32 chars = 130 bits


def test_normalize_accepts_common_variations():
    code = recovery.generate_recovery_code()
    flat = code.replace("-", "")
    assert recovery.normalize_recovery_code(code.lower()) == flat
    assert recovery.normalize_recovery_code(" " + code.replace("-", " ") + " ") == flat
    assert recovery.normalize_recovery_code(flat) == flat


def test_verify_accepts_every_variant_and_rejects_changes():
    code = recovery.generate_recovery_code()
    hashed = asyncio.run(recovery.hash_recovery_code(code))
    assert hashed.startswith("$argon2id$")
    for variant in (code, code.lower(), code.replace("-", ""), code.replace("-", " ")):
        assert asyncio.run(recovery.verify_recovery_code(hashed, variant)) is True
    flipped = ("A" if code[0] != "A" else "B") + code[1:]
    assert asyncio.run(recovery.verify_recovery_code(hashed, flipped)) is False


def test_verify_with_no_hash_is_false():
    assert asyncio.run(recovery.verify_recovery_code(None, recovery.generate_recovery_code())) is False
