# backend/sources/routes.py -- AgroPILOT Sources router
#
# Mount: app.include_router(sources_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/sources
# Контракт: {"ok": true, "data": ...} M10-2

from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.sources.models import Source
from backend.common.errors import NotFoundError
from backend.common.deps import get_db, get_current_user

sources_router = APIRouter(prefix="/sources", tags=["sources"])
VALID_TYPES = {"site", "rss", "telegram", "tender"}

def _ok(data):
    return {"ok": True, "data": data}

class SourceCreate(BaseModel):
    type:     str
    url:      str
    handle:   Optional[str]       = None
    keywords: Optional[List[str]] = None
    active:   Optional[bool]      = True

class SourcePatch(BaseModel):
    type:     Optional[str]       = None
    url:      Optional[str]       = None
    handle:   Optional[str]       = None
    keywords: Optional[List[str]] = None
    active:   Optional[bool]      = None

@sources_router.get("")
async def list_sources(
    active: Optional[bool] = Query(None),
    limit:  int            = Query(100, le=500),
    db:     AsyncSession   = Depends(get_db),
    user                   = Depends(get_current_user),
):
    q = select(Source).order_by(Source.id)
    if active is not None:
        q = q.where(Source.active == active)
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return _ok([r.to_dict() for r in rows])

@sources_router.post("")
async def create_source(
    payload: SourceCreate,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    source = Source(
        type     = payload.type,
        url      = payload.url,
        handle   = payload.handle,
        keywords = payload.keywords or [],
        active   = payload.active if payload.active is not None else True,
    )
    if payload.type not in VALID_TYPES:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"type must be one of {sorted(VALID_TYPES)}")
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return _ok(source.to_dict())

@sources_router.patch("/{source_id}")
async def patch_source(
    source_id: int,
    payload:   SourcePatch,
    db:        AsyncSession = Depends(get_db),
    user                    = Depends(get_current_user),
):
    source = await db.get(Source, source_id)
    if not source:
        raise NotFoundError("Source not found")
    for field, val in payload.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(source, field, val)
    await db.commit()
    await db.refresh(source)
    return _ok(source.to_dict())

@sources_router.delete("/{source_id}")
async def delete_source(
    source_id: int,
    db:        AsyncSession = Depends(get_db),
    user                    = Depends(get_current_user),
):
    source = await db.get(Source, source_id)
    if not source:
        raise NotFoundError("Source not found")
    await db.delete(source)
    await db.commit()
    return _ok({"deleted": source_id})
