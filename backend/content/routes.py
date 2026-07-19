# backend/content/routes.py -- AgroPILOT Content router
#
# Mount: app.include_router(content_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/content
# Контракт: {"ok": true, "data": ...} M10-3
# PATCH published_at: авто-set now() при status=published если не передан явно.

from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.content.models import Content
from backend.common.errors import NotFoundError
from backend.common.deps import get_db, get_current_user

content_router = APIRouter(prefix="/content", tags=["content"])

VALID_PLATFORMS = {"telegram", "instagram", "vk", "linkedin", "other"}
VALID_STATUSES  = {"draft", "published", "archived"}

def _ok(data):
    return {"ok": True, "data": data}


class ContentCreate(BaseModel):
    title:        str
    body:         str
    platform:     str
    status:       Optional[str]      = "draft"
    author_id:    Optional[str]      = None
    published_at: Optional[datetime] = None


class ContentPatch(BaseModel):
    title:        Optional[str]      = None
    body:         Optional[str]      = None
    platform:     Optional[str]      = None
    status:       Optional[str]      = None
    author_id:    Optional[str]      = None
    published_at: Optional[datetime] = None


@content_router.get("")
async def list_content(
    platform: Optional[str]  = Query(None),
    status:   Optional[str]  = Query(None),
    limit:    int             = Query(100, le=500),
    db:       AsyncSession    = Depends(get_db),
    user                      = Depends(get_current_user),
):
    q = select(Content).order_by(Content.created_at.desc())
    if platform:
        q = q.where(Content.platform == platform)
    if status:
        q = q.where(Content.status == status)
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return _ok([r.to_dict() for r in rows])


@content_router.post("")
async def create_content(
    payload: ContentCreate,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    if payload.platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=422, detail=f"platform must be one of {sorted(VALID_PLATFORMS)}")
    if payload.status and payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(VALID_STATUSES)}")
    item = Content(
        title        = payload.title,
        body         = payload.body,
        platform     = payload.platform,
        status       = payload.status or "draft",
        author_id    = payload.author_id,
        published_at = payload.published_at,
        created_at   = datetime.now(timezone.utc),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@content_router.patch("/{content_id}")
async def patch_content(
    content_id: int,
    payload:    ContentPatch,
    db:         AsyncSession = Depends(get_db),
    user                     = Depends(get_current_user),
):
    item = await db.get(Content, content_id)
    if not item:
        raise NotFoundError("Content not found")
    data = payload.model_dump(exclude_unset=True)
    if "platform" in data and data["platform"] not in VALID_PLATFORMS:
        raise HTTPException(status_code=422, detail=f"platform must be one of {sorted(VALID_PLATFORMS)}")
    if "status" in data and data["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(VALID_STATUSES)}")
    for field, val in data.items():
        setattr(item, field, val)
    if data.get("status") == "published" and not data.get("published_at"):
        item.published_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@content_router.delete("/{content_id}")
async def delete_content(
    content_id: int,
    db:         AsyncSession = Depends(get_db),
    user                     = Depends(get_current_user),
):
    item = await db.get(Content, content_id)
    if not item:
        raise NotFoundError("Content not found")
    await db.delete(item)
    await db.commit()
    return _ok({"deleted": content_id})
