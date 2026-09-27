# backend/auth/security.py -- JWT-токены и хэширование паролей (контракт §19)
#
# Переменные окружения (см. .env.example):
#   SECRET_KEY  -- подпись JWT (обязательна, без заглушек)
#   ALGORITHM   -- HS256 по умолчанию
#   ACCESS_TOKEN_EXPIRE_MINUTES   -- время жизни access-токена (60)
#   REFRESH_TOKEN_EXPIRE_DAYS     -- время жизни refresh-токена (14)

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

# ---------------------------------------------------------------------------
# Пароли: argon2id (новые хэши); legacy-bcrypt проверяется и прозрачно
# перехэшируется при успешном логине (О7 ТЗ_ИНТЕГРАЦИЯ_OCTOP).
# bcrypt напрямую, без passlib (у passlib 1.7.4 конфликт с bcrypt >= 4.1).
# ---------------------------------------------------------------------------

_ph = PasswordHasher()  # argon2id, параметры по умолчанию argon2-cffi


def hash_password(password: str) -> str:
    return _ph.hash(password)


def is_argon2(password_hash: str) -> bool:
    return bool(password_hash) and password_hash.startswith("$argon2")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    if is_argon2(password_hash):
        try:
            return _ph.verify(password_hash, password)
        except Argon2Error:
            return False
        except Exception:
            return False
    # legacy bcrypt
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except Exception:
        return False


def needs_rehash(password_hash: str) -> bool:
    """True, если хэш надо обновить до текущих параметров argon2id
    (старый bcrypt-хэш или устаревшие параметры argon2)."""
    if not password_hash:
        return False
    if not is_argon2(password_hash):
        return True
    try:
        return _ph.check_needs_rehash(password_hash)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def _secret() -> str:
    secret = os.environ.get("SECRET_KEY", "")
    if not secret or secret == "CHANGEME_replace_with_long_random_string":
        # Разворачиваться без секретной подписи нельзя: все запросы станут 401.
        raise RuntimeError(
            "SECRET_KEY is not set (or is the .env.example placeholder). "
            "Set a long random value in the service environment."
        )
    return secret


def _algorithm() -> str:
    return os.environ.get("ALGORITHM", "HS256")


def create_access_token(user_id: str, name: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    )
    payload = {
        "sub": user_id,
        "name": name,
        "type": "access",
        "exp": exp,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _secret(), algorithm=_algorithm())


def create_refresh_token(user_id: str, name: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(
        days=int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "14"))
    )
    payload = {
        "sub": user_id,
        "name": name,
        "type": "refresh",
        "exp": exp,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _secret(), algorithm=_algorithm())


def decode_token(token: str, expected_type: Optional[str] = None) -> dict:
    """Декодирует и проверяет JWT.

    Бросает jwt.PyJWTError при любой проблеме (просрочен, плохая подпись,
    неверный тип токена). Вызывающий код переводит это в UnauthorizedError.
    """
    payload = jwt.decode(token, _secret(), algorithms=[_algorithm()])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"expected {expected_type} token, got {payload.get('type')}"
        )
    return payload
