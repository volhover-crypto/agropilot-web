# tests/test_auth_security.py -- О7: argon2id + прозрачная миграция с bcrypt

import bcrypt

from backend.auth.security import (
    hash_password,
    is_argon2,
    needs_rehash,
    verify_password,
)


def test_hash_password_is_argon2id():
    h = hash_password("s3cret-pw")
    assert h.startswith("$argon2id$")


def test_verify_argon2_roundtrip():
    h = hash_password("s3cret-pw")
    assert verify_password("s3cret-pw", h)
    assert not verify_password("wrong", h)


def test_verify_legacy_bcrypt():
    # Старый формат (миграция 016): проверяем bcrypt-хэш без перехэша
    legacy = bcrypt.hashpw(b"s3cret-pw", bcrypt.gensalt()).decode("ascii")
    assert not is_argon2(legacy)
    assert verify_password("s3cret-pw", legacy)
    assert not verify_password("wrong", legacy)


def test_needs_rehash_bcrypt_true_argon2_false():
    legacy = bcrypt.hashpw(b"s3cret-pw", bcrypt.gensalt()).decode("ascii")
    assert needs_rehash(legacy)
    assert not needs_rehash(hash_password("s3cret-pw"))


def test_verify_garbage_hash_is_false():
    assert not verify_password("x", "")
    assert not verify_password("x", "not-a-hash")
