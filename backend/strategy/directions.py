# backend/strategy/directions.py -- §30: направления стратегии (CRUD)
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.strategy.direction_models import StrategyDirection
from backend.common.deps import get_db, get_current_user
from backend.common.errors import NotFoundError, ValidationError

directions_router = APIRouter(prefix="/strategy/directions", tags=["strategy"])

VALID_DIR_STATUS = ("active", "paused", "done")


def _ok(data):
    return {"ok": True, "data": data}


async def _next_id(db: AsyncSession) -> str:
    rows = (await db.execute(select(StrategyDirection.id))).scalars().all()
    mx = max((int(r[2:]) for r in rows if r.startswith("SD") and r[2:].isdigit()), default=0)
    return f"SD{mx + 1}"


class DirectionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    keywords: Optional[list] = None
    status: Optional[str] = "active"
    owner_id: Optional[str] = None


class DirectionPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[list] = None
    status: Optional[str] = None
    goal_ids: Optional[list] = None
    owner_id: Optional[str] = None


@directions_router.get("")
async def list_directions(
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    rows = (await db.execute(
        select(StrategyDirection).order_by(StrategyDirection.id))).scalars().all()
    return _ok([r.to_dict() for r in rows])


@directions_router.post("")
async def create_direction(
    payload: DirectionCreate,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    title = (payload.title or "").strip()
    if not title:
        raise ValidationError("title обязателен")
    if payload.status not in VALID_DIR_STATUS:
        raise ValidationError(f"status должен быть одним из {VALID_DIR_STATUS}")
    item = StrategyDirection(
        id=await _next_id(db),
        title=title,
        description=payload.description,
        keywords=payload.keywords or [],
        status=payload.status,
        goal_ids=[],
        owner_id=payload.owner_id or user.id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@directions_router.patch("/{dir_id}")
async def patch_direction(
    dir_id: str,
    payload: DirectionPatch,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    item = await db.get(StrategyDirection, dir_id)
    if not item:
        raise NotFoundError(f"направление {dir_id} не найдено")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in VALID_DIR_STATUS:
        raise ValidationError(f"status должен быть одним из {VALID_DIR_STATUS}")
    for f in ("title", "description", "keywords", "status", "goal_ids", "owner_id"):
        if f in data:
            setattr(item, f, data[f])
    item.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@directions_router.delete("/{dir_id}")
async def delete_direction(
    dir_id: str,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    item = await db.get(StrategyDirection, dir_id)
    if not item:
        raise NotFoundError(f"направление {dir_id} не найдено")
    await db.delete(item)
    await db.commit()
    return _ok({"deleted": dir_id})
