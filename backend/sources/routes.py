# backend/sources/routes.py -- AgroPILOT Sources router
#
# Mount: app.include_router(sources_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/sources
# Контракт: {"ok": true, "data": ...} / {"ok": false, "error": {code,message}}  (CONTRACTS.md §13)

from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.sources.models import Source
from backend.strategy_tasks.models import StrategyTask
from backend.team.models import TeamMember
from backend.common.errors import NotFoundError, ForbiddenError, ConflictError, ValidationError
from backend.common.deps import get_db, get_current_user

sources_router = APIRouter(prefix="/sources", tags=["sources"])

VALID_TYPES = {"news", "supplier", "competitor", "market", "tech"}
VALID_STATUS = {"active", "proposed", "disabled", "rejected"}
_MANAGER_ROLE_KEYS = {"manager", "admin"}

def _ok(data):
    return {"ok": True, "data": data}

async def _current_member(db: AsyncSession, user):
    """TeamMember текущего юзера (get_current_user — STUB до Stage-3 JWT)."""
    return await db.get(TeamMember, user.id)

async def _is_manager(db: AsyncSession, user) -> bool:
    """Enforcement по конвенции: менеджер/админ по role_key."""
    member = await _current_member(db, user)
    return bool(member and member.role_key in _MANAGER_ROLE_KEYS)

def _validate_type(t):
    if t not in VALID_TYPES:
        raise ValidationError(f"type must be one of {sorted(VALID_TYPES)}")

def _validate_status(s):
    if s not in VALID_STATUS:
        raise ValidationError(f"status must be one of {sorted(VALID_STATUS)}")

def _validate_url(u):
    if not u or not str(u).strip():
        raise ValidationError("url must be non-empty")

def _validate_keywords(kw):
    if kw is None:
        return []
    if not isinstance(kw, list):
        raise ValidationError("keywords must be a list")
    for k in kw:
        if not isinstance(k, str) or not k.strip():
            raise ValidationError("each keyword must be a non-empty string")
    return kw

async def _active_member(db: AsyncSession, uid):
    if uid is None:
        return None
    m = await db.get(TeamMember, uid)
    if not m or m.status != "active":
        raise ValidationError(f"team member {uid} not found or not active")
    return m

async def _route_proposed(db: AsyncSession, src: Source):
    """D-5 маршрутизация proposed: added_by -> либо по компетенции."""
    # 1. added_by активе�� -> ему
    if src.added_by:
        m = await db.get(TeamMember, src.added_by)
        if m and m.status == "active":
            src.receiver_user_id = src.added_by
            src.routing_reason = "added_by"
            return
    # 2/3. по компетенции: пересечение competencies[] с keywords[] + monitoring_focus
    focus = set(src.keywords or [])
    if src.linked_strategy_task:
        st = await db.get(StrategyTask, src.linked_strategy_task)
        if st and st.monitoring_focus:
            focus |= set(st.monitoring_focus)
    res = await db.execute(select(TeamMember).where(TeamMember.status == "active"))
    for m in res.scalars().all():
        comps = set(m.competencies or [])
        if comps & focus:
            src.receiver_user_id = m.id
            src.routing_reason = "competency"
            return
    src.receiver_user_id = None
    src.routing_reason = "competency"


class SourceCreate(BaseModel):
    type: str
    url: str
    handle: Optional[str] = None
    keywords: Optional[List[str]] = None
    status: Optional[str] = "proposed"
    added_by: Optional[str] = None
    linked_strategy_task: Optional[str] = None


class SourceUpdate(BaseModel):
    type: Optional[str] = None
    url: Optional[str] = None
    handle: Optional[str] = None
    keywords: Optional[List[str]] = None
    status: Optional[str] = None
    linked_strategy_task: Optional[str] = None


@sources_router.get("")
async def list_sources(
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    q = select(Source)
    if type is not None:
        _validate_type(type)
        q = q.where(Source.type == type)
    if status is not None:
        _validate_status(status)
        q = q.where(Source.status == status)
    res = await db.execute(q.order_by(Source.id.desc()))
    rows = res.scalars().all()
    return _ok([r.to_dict() for r in rows])


@sources_router.get("/{source_id}")
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    src = await db.get(Source, source_id)
    if not src:
        raise NotFoundError(f"source {source_id} not found")
    return _ok(src.to_dict())


@sources_router.post("")
async def create_source(
    payload: SourceCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    _validate_type(payload.type)
    _validate_url(payload.url)
    status = payload.status or "proposed"
    _validate_status(status)
    if status == "active" and not await _is_manager(db, user):
        raise ForbiddenError("only manager/admin can create an active source")
    # proposed — разрешён (путь любого автора задания)
    keywords = _validate_keywords(payload.keywords)
    await _active_member(db, payload.added_by)

    src = Source(
        type=payload.type,
        url=str(payload.url).strip(),
        handle=payload.handle,
        keywords=keywords,
        status=status,
        added_by=payload.added_by,
        linked_strategy_task=payload.linked_strategy_task,
    )
    if status == "proposed":
        await _route_proposed(db, src)
    db.add(src)
    await db.commit()
    await db.refresh(src)
    return _ok(src.to_dict())


@sources_router.post("/{source_id}/approve")
async def approve_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    src = await db.get(Source, source_id)
    if not src:
        raise NotFoundError(f"source {source_id} not found")
    if src.status != "proposed":
        raise ConflictError(f"source {source_id} is not proposed (status={src.status})")
    if src.receiver_user_id != user.id:
        raise ForbiddenError("only the proposal receiver can approve")
    src.status = "active"
    await db.commit()
    await db.refresh(src)
    return _ok(src.to_dict())

@sources_router.post("/{source_id}/reject")
async def reject_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    src = await db.get(Source, source_id)
    if not src:
        raise NotFoundError(f"source {source_id} not found")
    if src.status != "proposed":
        raise ConflictError(f"source {source_id} is not proposed (status={src.status})")
    if src.receiver_user_id != user.id:
        raise ForbiddenError("only the proposal receiver can reject")
    src.status = "rejected"
    await db.commit()
    await db.refresh(src)
    return _ok(src.to_dict())

@sources_router.patch("/{source_id}")
async def update_source(
    source_id: int,
    payload: SourceUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    src = await db.get(Source, source_id)
    if not src:
        raise NotFoundError(f"source {source_id} not found")
    if not await _is_manager(db, user):
        raise ForbiddenError("only manager/admin can modify sources")

    if payload.type is not None:
        _validate_type(payload.type)
        src.type = payload.type
    if payload.url is not None:
        _validate_url(payload.url)
        src.url = str(payload.url).strip()
    if payload.handle is not None:
        src.handle = payload.handle
    if payload.keywords is not None:
        src.keywords = _validate_keywords(payload.keywords)
    if payload.linked_strategy_task is not None:
        src.linked_strategy_task = payload.linked_strategy_task
    if payload.status is not None:
        _validate_status(payload.status)
        src.status = payload.status
        if payload.status == "proposed":
            await _route_proposed(db, src)
    await db.commit()
    await db.refresh(src)
    return _ok(src.to_dict())


@sources_router.delete("/{source_id}")
async def disable_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    src = await db.get(Source, source_id)
    if not src:
        raise NotFoundError(f"source {source_id} not found")
    if not await _is_manager(db, user):
        raise ForbiddenError("only manager/admin can disable sources")
    src.status = "disabled"
    await db.commit()
    await db.refresh(src)
    return _ok(src.to_dict())
