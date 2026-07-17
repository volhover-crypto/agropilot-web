# backend/goals/routes.py -- AgroPILOT Goals router
#
# Mount: app.include_router(goals_router, prefix="/agropilot/api/v1")
# Resulting base path: /agropilot/api/v1/goals
#
# Read-only on Stage 1: список целей + одна карточка.
# Контракт ответа: {"ok": true, "data": ...} (backend/common/errors.py).

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.goals.models import Goal
from backend.common.errors import NotFoundError
from backend.common.deps import get_db, get_current_user

goals_router = APIRouter(prefix="/goals", tags=["goals"])


def _ok(data):
    return {"ok": True, "data": data}


@goals_router.get("")
async def list_goals(
    limit: int          = Query(100, le=500),
    db:    AsyncSession = Depends(get_db),
    user                = Depends(get_current_user),
):
    """Все цели (G1–G3). Без фильтров на Этапе 1."""
    q = select(Goal).order_by(Goal.id).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return _ok([r.to_dict() for r in rows])


@goals_router.get("/{goal_id}")
async def get_goal(
    goal_id: str,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    goal = await db.get(Goal, goal_id)
    if not goal:
        raise NotFoundError("Goal not found")
    return _ok(goal.to_dict())
