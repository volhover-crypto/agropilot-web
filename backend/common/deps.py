# backend/common/deps.py -- AgroPILOT FastAPI dependency injection
#
# Provides:
#   get_db          — async SQLAlchemy session (AsyncSession)
#   get_current_user — stub user for pre-auth development stage
#
# Usage in routers:
#   from backend.common.deps import get_db, get_current_user
#   db:   AsyncSession = Depends(get_db)
#   user: CurrentUser  = Depends(get_current_user)
#
# NOTE: get_current_user is a stub returning a fixed dev user.
# Replace with real JWT/token validation before production.

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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


async def get_current_user() -> CurrentUser:
    """
    STUB — returns a fixed dev user.
    Replace with real JWT validation before production deployment.
    """
    return CurrentUser(id="U1", name="Екатерина")
