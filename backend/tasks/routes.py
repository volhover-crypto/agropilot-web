# backend/tasks/routes.py -- AgroPILOT M9 Tasks router
#
# Mount: app.include_router(tasks_router, prefix="/agropilot/api/v1")
# Resulting base path: /agropilot/api/v1/tasks
#
# Политика фильтрации:
#   GET /tasks       — все задачи команды (без фильтра по owner)
#   GET /tasks/:id   — одна задача
#   PATCH /tasks/:id — обновить status/priority/due_at

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.tasks.models import Task
from backend.common.errors import NotFoundError
from backend.common.deps import get_db, get_current_user

tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TaskPatch(BaseModel):
    status:   Optional[str]      = None
    priority: Optional[str]      = None
    due_at:   Optional[datetime] = None


def _ok(data):
    return {"ok": True, "data": data}


# ---------------------------------------------------------------------------
# GET /tasks
# ---------------------------------------------------------------------------

@tasks_router.get("")
async def list_tasks(
    status:  Optional[str] = Query(None),
    goal_id: Optional[str] = Query(None),
    deal_id: Optional[str] = Query(None),
    limit:   int           = Query(200, le=500),
    db:      AsyncSession  = Depends(get_db),
    user                   = Depends(get_current_user),
):
    """Все задачи команды. Опциональные фильтры: status, goal_id, deal_id."""
    q = select(Task).order_by(Task.due_at.asc())
    if status:
        q = q.where(Task.status == status)
    if goal_id:
        q = q.where(Task.goal_id == goal_id)
    if deal_id:
        q = q.where(Task.deal_id == deal_id)
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return _ok([r.to_dict() for r in rows])


# ---------------------------------------------------------------------------
# GET /tasks/:id
# ---------------------------------------------------------------------------

@tasks_router.get("/{task_id}")
async def get_task(
    task_id: str,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise NotFoundError("Task not found")
    return _ok(task.to_dict())


# ---------------------------------------------------------------------------
# PATCH /tasks/:id
# ---------------------------------------------------------------------------

@tasks_router.patch("/{task_id}")
async def patch_task(
    task_id: str,
    body:    TaskPatch,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise NotFoundError("Task not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(task, field, val)
    task.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(task)
    return _ok(task.to_dict())
