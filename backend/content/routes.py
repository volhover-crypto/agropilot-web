# backend/content/routes.py -- AgroPILOT Content router
#
# Mount: app.include_router(content_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/content
# Контракт: {"ok": true, "data": ...} M10-3
# PATCH published_at: авто-set now() при status=published если не передан явно.

import asyncio
import json as _json
import os
import urllib.request
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.content.models import Content, ContentVersion
from backend.common.errors import NotFoundError, ValidationError
from backend.common.deps import get_db, get_current_user
from backend.team.models import TeamMember
from backend.common.llm import llm_chat, llm_configured, LLMError, A2_SYSTEM, A3_SYSTEM

content_router = APIRouter(prefix="/content", tags=["content"])

VALID_PLATFORMS = {"telegram", "instagram", "vk", "linkedin", "other"}
# §21.1: цепочка конвейера + переходы; legacy draft/published/archived совместимы
VALID_STATUSES  = {"draft", "in_review", "approved", "scheduled", "published", "rejected", "archived"}
STATUS_TRANSITIONS = {
    "draft":     {"in_review", "rejected", "archived"},
    "in_review": {"draft", "approved", "rejected"},
    "approved":  {"scheduled", "published", "rejected"},
    "scheduled": {"published", "draft"},
    "published": {"archived"},
    "rejected":  {"draft", "archived"},
    "archived":  {"draft"},
}
EDITOR_ONLY_STATUSES = {"approved", "rejected"}


async def _can_approve(db: AsyncSession, user) -> bool:
    member = await db.get(TeamMember, user.id)
    if member is None:
        return False
    if member.role_key in ("manager", "admin"):
        return True
    return any(p in (member.permissions or []) for p in ("content:approve", "*:*"))

def _ok(data):
    return {"ok": True, "data": data}


class ContentCreate(BaseModel):
    title:        str
    body:         str
    platform:     str
    status:       Optional[str]      = "draft"
    author_id:    Optional[str]      = None
    published_at: Optional[datetime] = None
    news_item_id: Optional[int]      = None
    tags:         Optional[list]     = None
    channel_ids:  Optional[list]     = None
    scheduled_at: Optional[datetime] = None


class FromNewsBody(BaseModel):
    news_id: int
    platform: str = "telegram"


class PublishBody(BaseModel):
    chat_id: Optional[str] = None  # целевой чат/канал; по умолчанию TELEGRAM_CHAT_ID


class ContentPatch(BaseModel):
    title:        Optional[str]      = None
    body:         Optional[str]      = None
    platform:     Optional[str]      = None
    status:       Optional[str]      = None
    author_id:    Optional[str]      = None
    published_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    tags:         Optional[list]     = None
    channel_ids:  Optional[list]     = None
    comment:      Optional[str]      = None


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
    if payload.status in EDITOR_ONLY_STATUSES and not await _can_approve(db, user):
        raise ValidationError("создавать сразу в approved/rejected может только редактор")
    now = datetime.now(timezone.utc)
    item = Content(
        title        = payload.title,
        body         = payload.body,
        platform     = payload.platform,
        status       = payload.status or "draft",
        author_id    = payload.author_id or user.id,
        published_at = payload.published_at,
        created_at   = now,
        news_item_id = payload.news_item_id,
        scheduled_at = payload.scheduled_at,
        tags         = payload.tags or [],
        channel_ids  = payload.channel_ids or [],
        updated_at   = now,
    )
    db.add(item)
    await db.flush()
    db.add(ContentVersion(content_id=item.id, title=item.title, body=item.body,
                          author_id=user.id, comment="создание", created_at=now))
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@content_router.post("/from_news")
async def create_from_news(
    payload: FromNewsBody,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    # A2-MVP: черновик поста из NewsItem (LLM-генерация подключается позже
    # без смены контракта). NewsItem помечается used.
    from backend.news.models import NewsItem

    if payload.platform not in VALID_PLATFORMS:
        raise ValidationError(f"platform must be one of {sorted(VALID_PLATFORMS)}")
    news = await db.get(NewsItem, payload.news_id)
    if not news:
        raise NotFoundError(f"news_item {payload.news_id} не найден")
    now = datetime.now(timezone.utc)
    # A2: LLM-генерация черновика из материала; при сбое/отсутствии ключа — копия
    title = (news.title or "Черновик поста")[:300]
    body = news.summary or news.title or ""
    gen_note = "копия материала (LLM недоступна)"
    if llm_configured():
        try:
            prompt = (
                f"Напиши пост для Telegram на основе материала мониторинга.\n\n"
                f"Материал: {news.title}\n{news.summary or ''}\n\n"
                f"Ссылка на первоисточник: {news.url or 'нет'}"
            )
            body = await asyncio.to_thread(llm_chat, prompt, A2_SYSTEM, None, 1000)
            title = (body.splitlines()[0][:200] if body else title)
            gen_note = f"сгенерировано LLM из news_item {news.id}"
        except LLMError as e:
            gen_note = f"копия материала (LLM сбой: {str(e)[:100]})"
    item = Content(
        title        = title,
        body         = body,
        platform     = payload.platform,
        status       = "draft",
        author_id    = user.id,
        created_at   = now,
        news_item_id = news.id,
        tags         = [],
        channel_ids  = [],
        updated_at   = now,
    )
    db.add(item)
    await db.flush()
    db.add(ContentVersion(content_id=item.id, title=item.title, body=item.body,
                          author_id=user.id, comment=gen_note, created_at=now))
    news.status = "used"
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@content_router.get("/{content_id}/versions")
async def list_versions(
    content_id: int,
    db:         AsyncSession = Depends(get_db),
    user                      = Depends(get_current_user),
):
    item = await db.get(Content, content_id)
    if not item:
        raise NotFoundError("Content not found")
    rows = (await db.execute(
        select(ContentVersion).where(ContentVersion.content_id == content_id)
        .order_by(ContentVersion.created_at.desc())
    )).scalars().all()
    return _ok([r.to_dict() for r in rows])


@content_router.post("/{content_id}/publish")
async def publish_content(
    content_id: int,
    payload:    PublishBody,
    db:         AsyncSession = Depends(get_db),
    user                     = Depends(get_current_user),
):
    """A3: публикация approved/scheduled поста в Telegram.

    Human-in-the-loop (п. 6.6 ТЗ): эндпоинт вызывается только явным действием
    человека с правом content:approve. Отправка через Bot API бота
    JARVIS_MONITOR (TELEGRAM_BOT_TOKEN). При успехе status=published,
    фиксируются время и ссылка/идентификатор сообщения.
    """
    item = await db.get(Content, content_id)
    if not item:
        raise NotFoundError("Content not found")
    if item.status not in ("approved", "scheduled"):
        raise ValidationError(
            f"публиковать можно только approved/scheduled (сейчас: {item.status})")
    if not await _can_approve(db, user):
        raise ValidationError("публикация требует права content:approve")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = (payload.chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
    if not token or not chat_id:
        raise ValidationError("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID не настроены")

    text = (item.title + "\n\n" + (item.body or "")).strip()[:4000]
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=_json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = _json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise ValidationError(f"Telegram отклонил отправку: {str(e)[:200]}")
    if not resp.get("ok"):
        raise ValidationError(f"Telegram error: {str(resp.get('description'))[:200]}")

    msg = resp.get("result") or {}
    item.status = "published"
    item.published_at = datetime.now(timezone.utc)
    item.updated_at = item.published_at
    item.editor_id = user.id
    item.published_url = (msg.get("link") or
                          f"tg://message?chat={chat_id}&message={msg.get('message_id')}")
    db.add(ContentVersion(content_id=item.id, title=item.title, body=item.body,
                          author_id=user.id, comment=f"опубликовано (msg {msg.get('message_id')})",
                          created_at=item.published_at))
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


class AdaptBody(BaseModel):
    prompt: Optional[str] = None   # указания канала; иначе общий промт A3


@content_router.post("/{content_id}/adapt")
async def adapt_content(
    content_id: int,
    payload:    AdaptBody,
    db:         AsyncSession = Depends(get_db),
    user                     = Depends(get_current_user),
):
    """A3: LLM-адаптация текста под канал. Старый текст сохраняется версией."""
    if not llm_configured():
        raise ValidationError("LLM-шлюз не настроен (OPENROUTER_API_KEY)")
    item = await db.get(Content, content_id)
    if not item:
        raise NotFoundError("Content not found")
    if item.status == "published":
        raise ValidationError("адаптировать опубликованный пост нельзя")
    channel_hint = payload.prompt or f"канал {item.platform}"
    prompt = (
        f"Адаптируй пост под {channel_hint}. Оригинал:\n\n"
        f"Заголовок: {item.title}\nТекст: {item.body}"
    )
    try:
        new_body = await asyncio.to_thread(llm_chat, prompt, A3_SYSTEM, None, 1000)
    except LLMError as e:
        raise ValidationError(f"LLM сбой: {str(e)[:150]}")
    if not new_body:
        raise ValidationError("LLM вернула пустой текст")
    db.add(ContentVersion(content_id=item.id, title=item.title, body=item.body,
                          author_id=user.id, comment=f"версия до адаптации ({channel_hint})",
                          created_at=datetime.now(timezone.utc)))
    item.body = new_body
    item.title = new_body.splitlines()[0][:200] or item.title
    item.updated_at = datetime.now(timezone.utc)
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
        raise ValidationError(f"platform must be one of {sorted(VALID_PLATFORMS)}")
    if "status" in data and data["status"] not in VALID_STATUSES:
        raise ValidationError(f"status must be one of {sorted(VALID_STATUSES)}")
    if "status" in data and data["status"] != item.status:
        new_status = data["status"]
        allowed = STATUS_TRANSITIONS.get(item.status, set())
        if new_status not in allowed:
            raise ValidationError(
                f"переход {item.status} -> {new_status} не разрешён (допустимо: {sorted(allowed)})")
        if new_status in EDITOR_ONLY_STATUSES and not await _can_approve(db, user):
            raise ValidationError("утверждение/отклонение требует права content:approve")
        if new_status == "approved":
            item.editor_id = user.id

    old_title, old_body = item.title, item.body
    for field in ("title", "body", "platform", "status", "author_id",
                  "published_at", "scheduled_at", "tags", "channel_ids"):
        if field in data:
            setattr(item, field, data[field])
    item.updated_at = datetime.now(timezone.utc)
    if data.get("status") == "published" and not data.get("published_at"):
        item.published_at = item.updated_at
    if old_title != item.title or old_body != item.body:
        db.add(ContentVersion(content_id=item.id, title=old_title, body=old_body,
                              author_id=user.id,
                              comment=data.get("comment") or "версия до правки",
                              created_at=item.updated_at))
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
