# backend/common/deps.py -- AgroPILOT FastAPI dependency injection
#
# Provides:
#   get_db           — async SQLAlchemy session (AsyncSession)
#   get_current_user — JWT-валидация Bearer-токена (контракт §19)
#
# Usage in routers:
#   from backend.common.deps import get_db, get_current_user
#   db:   AsyncSession = Depends(get_db)
#   user: CurrentUser  = Depends(get_current_user)

import os
from typing import AsyncGenerator

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.auth.security import decode_token
from backend.common.errors import UnauthorizedError

# ---------------------------------------------------------------------------
# Database engine
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/agropilot",
)

_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

_AsyncSessionLocal = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, roll back on error, always close."""
    async with _AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


class CurrentUser:
    """Minimal user object expected by routers: .id (str) and .name (str)."""

    def __init__(self, id: str, name: str) -> None:
        self.id   = id
        self.name = name


# auto_error=False: без заголовка Authorization отдаём свой 401 по контракту §0,
# а не дефолтный 403 от HTTPBearer.
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """Валидирует access-JWT из заголовка Authorization: Bearer <token>.

    401 (UnauthorizedError) при отсутствии/просрочке/подделке токена,
    а также если это refresh-токен.
    """
    if credentials is None:
        raise UnauthorizedError("Требуется заголовок Authorization: Bearer <token>")
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except jwt.PyJWTError as e:
        raise UnauthorizedError(f"Недействительный токен: {e}")
    user_id = payload.get("sub")
    name = payload.get("name")
    if not user_id or not name:
        raise UnauthorizedError("Токен не содержит данных пользователя")
    return CurrentUser(id=str(user_id), name=str(name))
