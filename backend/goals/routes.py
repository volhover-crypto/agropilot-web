# backend/goals/routes.py -- AgroPILOT Goals router
#
# Mount: app.include_router(goals_router, prefix="/agropilot/api/v1")
# Resulting base path: /agropilot/api/v1/goals
#
# Read-only on Stage 1: список целей + одна карточка.
# Контракт ответа: {"ok": true, "data": ...} (backend/common/errors.py).

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
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


class GoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    kind: Optional[str] = None
    direction_id: Optional[str] = None
    target: Optional[float] = None
    unit: Optional[str] = None
    owner_id: Optional[str] = None


class GoalPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None
    direction_id: Optional[str] = None
    target: Optional[float] = None
    unit: Optional[str] = None
    current: Optional[float] = None


def _next_goal_id(existing) -> str:
    mx = 0
    for g in existing:
        if g and g.startswith("G") and g[1:].isdigit():
            mx = max(mx, int(g[1:]))
    return f"G{mx + 1}"


@goals_router.post("")
async def create_goal(
    payload: GoalCreate,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    ids = (await db.execute(select(Goal.id))).scalars().all()
    g = Goal(
        id=_next_goal_id(ids),
        title=payload.title,
        description=payload.description,
        kind=payload.kind or "revenue",
        direction_id=payload.direction_id,
        target=payload.target,
        unit=payload.unit,
        status="active", progress=0, current=0,
        owner_id=payload.owner_id or user.id,
        metric={},
    )
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return _ok(g.to_dict())


@goals_router.patch("/{goal_id}")
async def patch_goal(
    goal_id: str,
    payload: GoalPatch,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    g = await db.get(Goal, goal_id)
    if not g:
        raise NotFoundError("Goal not found")
    data = payload.model_dump(exclude_unset=True)
    for f, v in data.items():
        setattr(g, f, v)
    # прогресс пересчитывается из current/target, если оба заданы
    if g.target:
        g.progress = max(0, min(100, round(float(g.current or 0) / float(g.target) * 100)))
    await db.commit()
    await db.refresh(g)
    return _ok(g.to_dict())


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
