# backend/segments/routes.py -- §37: справочники сегментов аудитории и рубрик
#
# Mount: app.include_router(segments_router, prefix="/agropilot/api/v1")
# CRUD /v1/segments, /v1/rubrics — право «контент-мейкер»:
# content:edit | content:approve | agents:manage | *:* | роль manager/admin.
# Удаление сегмента: связи (sources/channels/news_items/content) отвязываются
# автоматически (SET segment_code=NULL), в ответе — счётчики (решение по
# дефолту, владелец одобряет постфактум).

from typing import Optional

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.segments.models import AudienceSegment, Rubric
from backend.common.deps import get_db, get_current_user
from backend.common.errors import NotFoundError, ValidationError
from backend.team.models import TeamMember

segments_router = APIRouter(prefix="/segments", tags=["segments"])

_CONTENT_PERMS = ("content:edit", "content:approve", "agents:manage", "*:*")


def _ok(data):
    return {"ok": True, "data": data}


async def _can_edit_content(db: AsyncSession, user) -> bool:
    m = await db.get(TeamMember, user.id)
    if m is None:
        return False
    if m.role_key in ("admin", "manager"):
        return True
    return any(p in (m.permissions or []) for p in _CONTENT_PERMS)


# ---------- сегменты ----------

class SegmentBody(BaseModel):
    code: Optional[str] = None       # только при создании
    name: str
    description: Optional[str] = None
    prompt_addon: Optional[str] = None
    active: Optional[bool] = None


@segments_router.get("")
async def list_segments(db: AsyncSession = Depends(get_db),
                        user=Depends(get_current_user)):
    rows = (await db.execute(
        select(AudienceSegment).order_by(AudienceSegment.id))).scalars().all()
    return _ok([r.to_dict() for r in rows])


@segments_router.post("")
async def create_segment(payload: SegmentBody, db: AsyncSession = Depends(get_db),
                         user=Depends(get_current_user)):
    if not await _can_edit_content(db, user):
        raise ValidationError("сегменты — право контент-мейкера (content:edit/approve)")
    code = (payload.code or "").strip().lower()
    if not code or not code.replace("_", "").isalnum():
        raise ValidationError("код: латиница/цифры/подчёркивание")
    if not (payload.name or "").strip():
        raise ValidationError("название обязательно")
    dup = (await db.execute(select(AudienceSegment).where(
        AudienceSegment.code == code))).scalars().first()
    if dup:
        raise ValidationError(f"сегмент с кодом {code} уже есть")
    seg = AudienceSegment(code=code, name=payload.name.strip(),
                          description=payload.description,
                          prompt_addon=payload.prompt_addon,
                          active=payload.active if payload.active is not None else True,
                          created_at=datetime.now(timezone.utc))
    db.add(seg)
    await db.commit()
    await db.refresh(seg)
    return _ok(seg.to_dict())


# ---------- рубрики ----------

class RubricBody(BaseModel):
    code: Optional[str] = None
    title: str
    description: Optional[str] = None
    active: Optional[bool] = None


@segments_router.get("/rubrics")
async def list_rubrics(db: AsyncSession = Depends(get_db),
                       user=Depends(get_current_user)):
    rows = (await db.execute(select(Rubric).order_by(Rubric.id))).scalars().all()
    return _ok([r.to_dict() for r in rows])


@segments_router.post("/rubrics")
async def create_rubric(payload: RubricBody, db: AsyncSession = Depends(get_db),
                        user=Depends(get_current_user)):
    if not await _can_edit_content(db, user):
        raise ValidationError("рубрики — право контент-мейкера (content:edit/approve)")
    code = (payload.code or "").strip().lower()
    if not code or not code.replace("_", "").isalnum():
        raise ValidationError("код: латиница/цифры/подчёркивание")
    if not (payload.title or "").strip():
        raise ValidationError("название обязательно")
    dup = (await db.execute(select(Rubric).where(
        Rubric.code == code))).scalars().first()
    if dup:
        raise ValidationError(f"рубрика с кодом {code} уже есть")
    r = Rubric(code=code, title=payload.title.strip(),
               description=payload.description,
               active=payload.active if payload.active is not None else True,
               created_at=datetime.now(timezone.utc))
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _ok(r.to_dict())


@segments_router.delete("/rubrics/{rubric_id}")
async def delete_rubric(rubric_id: int, db: AsyncSession = Depends(get_db),
                        user=Depends(get_current_user)):
    if not await _can_edit_content(db, user):
        raise ValidationError("рубрики — право контент-мейкера (content:edit/approve)")
    r = await db.get(Rubric, rubric_id)
    if not r:
        raise NotFoundError(f"рубрика {rubric_id} не найдена")
    from backend.content.models import Content
    res = await db.execute(update(Content).where(
        Content.rubric_code == r.code).values(rubric_code=None))
    await db.delete(r)
    await db.commit()
    return _ok({"deleted": rubric_id, "code": r.code,
                "unlinked": {"content": int(res.rowcount or 0)}})


@segments_router.patch("/{segment_id}")
async def patch_segment(segment_id: int, payload: SegmentBody,
                        db: AsyncSession = Depends(get_db),
                        user=Depends(get_current_user)):
    if not await _can_edit_content(db, user):
        raise ValidationError("сегменты — право контент-мейкера (content:edit/approve)")
    seg = await db.get(AudienceSegment, segment_id)
    if not seg:
        raise NotFoundError(f"сегмент {segment_id} не найден")
    data = payload.model_dump(exclude_unset=True)
    data.pop("code", None)  # код неизменяем
    if not data:
        raise ValidationError("нечего обновлять")
    for f, v in data.items():
        setattr(seg, f, v)
    await db.commit()
    await db.refresh(seg)
    return _ok(seg.to_dict())


@segments_router.delete("/{segment_id}")
async def delete_segment(segment_id: int, db: AsyncSession = Depends(get_db),
                         user=Depends(get_current_user)):
    """Удаление с автоотвязкой: sources/channels/news/content остаются без сегмента."""
    if not await _can_edit_content(db, user):
        raise ValidationError("сегменты — право контент-мейкера (content:edit/approve)")
    seg = await db.get(AudienceSegment, segment_id)
    if not seg:
        raise NotFoundError(f"сегмент {segment_id} не найден")
    code = seg.code
    from backend.sources.models import Source
    from backend.channels.models import Channel
    from backend.news.models import NewsItem
    from backend.content.models import Content
    counts = {}
    for model, label in ((Source, "sources"), (Channel, "channels"),
                         (NewsItem, "news"), (Content, "content")):
        res = await db.execute(update(model).where(
            model.segment_code == code).values(segment_code=None))
        counts[label] = int(res.rowcount or 0)
    await db.delete(seg)
    await db.commit()
    return _ok({"deleted": segment_id, "code": code, "unlinked": counts})


