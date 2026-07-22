# backend/strategy_tasks/routes.py -- AgroPILOT Strategy Tasks router
#
# Mount: app.include_router(strategy_tasks_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/strategy/tasks
# Contract: {"ok": true, "data": {...}} -- Block C, CONTRACTS.md 12.1-12.4

import uuid
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.strategy_tasks.models import StrategyTask
from backend.common.errors import NotFoundError, ForbiddenError
from backend.common.deps import get_db, get_current_user

strategy_tasks_router = APIRouter(prefix="/strategy/tasks", tags=["strategy_tasks"])

VALID_STATUSES = {"active", "inactive"}
VALID_PRIORITIES = {"low", "medium", "high"}
WRITE_ROLES = {"manager", "admin"}


def _ok(data):
    return {"ok": True, "data": data}


def _require_write_role(user) -> None:
    # CONTRACTS 12.4: write is limited to manager|admin.
    # NOTE: get_current_user is a STUB without role yet (HANDOVER: Stage-3 JWT/RBAC).
    # When a role is present it is enforced; absent role (dev STUB) falls through.
    role = getattr(user, "role_key", None) or getattr(user, "role", None)
    if role is not None and role not in WRITE_ROLES:
        raise ForbiddenError("strategy task write requires manager or admin role")


class StrategyTaskCreate(BaseModel):
    title:            str
    description:      Optional[str]       = None
    priority:         Optional[str]       = "medium"
    status:           Optional[str]       = "active"
    monitoring_focus: Optional[List[str]] = None
    owner_id:         str
    linked_scenario:  Optional[str]       = None


class StrategyTaskPatch(BaseModel):
    title:            Optional[str]       = None
    description:      Optional[str]       = None
    priority:         Optional[str]       = None
    status:           Optional[str]       = None
    monitoring_focus: Optional[List[str]] = None
    owner_id:         Optional[str]       = None
    linked_scenario:  Optional[str]       = None


@strategy_tasks_router.get("")
async def list_strategy_tasks(
    status:   Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    limit:    int           = Query(100, le=500),
    db:       AsyncSession   = Depends(get_db),
    user                    = Depends(get_current_user),
):
    q = select(StrategyTask).order_by(StrategyTask.created_at.desc())
    if status:
        q = q.where(StrategyTask.status == status)
    if priority:
        q = q.where(StrategyTask.priority == priority)
    if owner_id:
        q = q.where(StrategyTask.owner_id == owner_id)
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return _ok([r.to_dict() for r in rows])


@strategy_tasks_router.get("/{task_id}")
async def get_strategy_task(
    task_id: str,
    db:      AsyncSession = Depends(get_db),
    user                 = Depends(get_current_user),
):
    item = await db.get(StrategyTask, task_id)
    if not item:
        raise NotFoundError("strategy task not found")
    return _ok(item.to_dict())


@strategy_tasks_router.post("")
async def create_strategy_task(
    payload: StrategyTaskCreate,
    db:      AsyncSession = Depends(get_db),
    user                 = Depends(get_current_user),
):
    _require_write_role(user)
    if payload.priority and payload.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail=f"priority must be one of {sorted(VALID_PRIORITIES)}")
    if payload.status and payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(VALID_STATUSES)}")
    now = datetime.now(timezone.utc)
    item = StrategyTask(
        id               = uuid.uuid4().hex,
        title            = payload.title,
        description      = payload.description,
        priority         = payload.priority or "medium",
        status           = payload.status or "active",
        monitoring_focus = payload.monitoring_focus or [],
        owner_id         = payload.owner_id,
        added_by         = user.id,
        linked_scenario  = payload.linked_scenario,
        created_at       = now,
        updated_at       = now,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@strategy_tasks_router.patch("/{task_id}")
async def patch_strategy_task(
    task_id: str,
    payload: StrategyTaskPatch,
    db:      AsyncSession = Depends(get_db),
    user                 = Depends(get_current_user),
):
    _require_write_role(user)
    item = await db.get(StrategyTask, task_id)
    if not item:
        raise NotFoundError("strategy task not found")
    data = payload.model_dump(exclude_unset=True)
    if "priority" in data and data["priority"] not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail=f"priority must be one of {sorted(VALID_PRIORITIES)}")
    if "status" in data and data["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(VALID_STATUSES)}")
    for field, val in data.items():
        setattr(item, field, val)
    item.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@strategy_tasks_router.delete("/{task_id}")
async def delete_strategy_task(
    task_id: str,
    db:      AsyncSession = Depends(get_db),
    user                 = Depends(get_current_user),
):
    _require_write_role(user)
    item = await db.get(StrategyTask, task_id)
    if not item:
        raise NotFoundError("strategy task not found")
    await db.delete(item)
    await db.commit()
    return _ok({"deleted": task_id})
