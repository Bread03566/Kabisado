import asyncio
import threading
import time

import pytest
from argon2 import PasswordHasher

from app.security import passwords


@pytest.mark.parametrize("pw,ok", [("a" * 9, False), ("g7!kQ2mZp9", True), ("x7Kq" * 32, True), ("x7Kq" * 32 + "a", False)])
def test_length_boundaries(pw, ok):
    if ok:
        passwords.validate_password(pw, "someone")
    else:
        with pytest.raises(ValueError):
            passwords.validate_password(pw, "someone")


def test_exactly_10_and_128_are_accepted():
    passwords.validate_password("Zq7!mK2pXw", "u")           # 10
    passwords.validate_password(("Zq7!mK2pXw" * 13)[:128], "u")  # 128


def test_common_password_rejected():
    with pytest.raises(ValueError, match="common"):
        passwords.validate_password("password123", "someone")
    with pytest.raises(ValueError, match="common"):
        passwords.validate_password("PASSWORD123", "someone")


def test_password_equal_to_username_rejected():
    with pytest.raises(ValueError, match="username"):
        passwords.validate_password("kabi.owl.0001", "kabi.owl.0001")


def test_hash_round_trip_is_argon2id():
    h = asyncio.run(passwords.hash_password("correct horse battery"))
    assert h.startswith("$argon2id$")
    assert asyncio.run(passwords.verify_password(h, "correct horse battery")) is True
    assert asyncio.run(passwords.verify_password(h, "wrong horse battery")) is False


def test_verify_with_no_hash_is_false_but_still_does_work():
    start = time.perf_counter()
    assert asyncio.run(passwords.verify_password(None, "anything-at-all")) is False
    assert time.perf_counter() - start > 0  # ran the dummy verification, not an early return
    assert asyncio.run(passwords.verify_password("not-a-hash", "x")) is False


def test_needs_rehash():
    fresh = asyncio.run(passwords.hash_password("correct horse battery"))
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("correct horse battery")
    assert passwords.needs_rehash(fresh) is False
    assert passwords.needs_rehash(weak) is True


def test_hashing_concurrency_is_limited_to_two(monkeypatch):
    live, peak, lock = 0, 0, threading.Lock()

    def slow_hash(password):
        nonlocal live, peak
        with lock:
            live += 1
            peak = max(peak, live)
        time.sleep(0.05)
        with lock:
            live -= 1
        return "h"

    monkeypatch.setattr(passwords, "_hash_sync", slow_hash)

    async def run():
        return await asyncio.gather(*(passwords.hash_password("pw") for _ in range(6)))

    assert asyncio.run(run()) == ["h"] * 6
    assert 1 <= peak <= 2
