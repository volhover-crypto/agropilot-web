# backend/strategy/routes.py -- AgroPILOT M4 FastAPI Strategy router
# Mount: app.include_router(router, prefix="/agropilot/api/v1")
# Resulting base path: /agropilot/api/v1/strategy  (matches CONTRACTS §4 /v1/strategy)
from typing import List, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Strategy, STRATEGY_ID
from backend.common.errors import NotFoundError, ForbiddenError

# -- Dependency stubs (replace with your actual db/auth deps) --
# from app.deps import get_db, current_user

router = APIRouter(prefix="/strategy", tags=["strategy"])

WRITE_ROLES = {"manager", "admin"}


class StrategyPut(BaseModel):
    scenarios: List[Any]


def _ok(data):
    return {"ok": True, "data": data}


# --------------- GET /strategy ---------------
@router.get("")
async def get_strategy(db: AsyncSession = Depends(), user = Depends()):
    row = await db.get(Strategy, STRATEGY_ID)
    if not row:
        raise NotFoundError("Strategy not found")
    return _ok(row.to_dict())


# --------------- PUT /strategy ---------------
@router.put("")
async def put_strategy(
    body: StrategyPut,
    db: AsyncSession = Depends(),
    user = Depends(),
):
    if getattr(user, "role", None) not in WRITE_ROLES:
        raise ForbiddenError("Only manager or admin can update strategy")

    row = await db.get(Strategy, STRATEGY_ID)
    if not row:
        raise NotFoundError("Strategy not found")

    row.scenarios = body.scenarios
    row.updated_by = str(getattr(user, "id", "")) or None
    await db.commit()
    await db.refresh(row)
    return _ok(row.to_dict())
