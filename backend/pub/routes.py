# backend/pub/routes.py -- §46.6 (Ф2): реестр каналов публикаций
#
# Mount: app.include_router(router, prefix="/agropilot/api/v1").
# GET /v1/pub/channels            — список (секреты не отдаются, только has_token)
# POST /v1/pub/channels           — создать канал (admin)
# PATCH /v1/pub/channels/{id}     — правка/заморозка/ротация токена (admin)
# Права: чтение — любое авторизованное; мутации — только admin (role_key,
# по образцу §45.10). Токен хранится в pub_channels.secrets по платформе
# (bot_token | vk_token), наружу никогда не возвращается. Заморозка вместо
# удаления: история pub_post_channels остаётся (FK, §46.1).

import asyncio
import json as _json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.deps import get_current_user, get_db
from backend.common.errors import (ConflictError, ForbiddenError, NotFoundError,
                                   ValidationError)
from backend.pub.models import PubChannel, PubPost, PubPostChannel
from backend.team.models import TeamMember

router = APIRouter(prefix="/pub", tags=["pub"])

# §46.7 (Ф3): публикация через n8n; файлы артефактов отдаёт nginx публично,
# относительные /agropilot/files/... достраиваем до абсолютных (для Bot API/n8n)
PUB_PUBLIC_BASE = os.getenv("PUB_PUBLIC_BASE", "https://mdked.hlab.kz").rstrip("/")
PUB_ENGINE_URL = os.getenv("PUB_ENGINE_URL",
                           "https://mdked.hlab.kz/n8n/webhook/pub-publish")
PUB_ENGINE_TOKEN = os.getenv("PUB_ENGINE_TOKEN", "")
PUBLISH_ROLES = ("admin", "manager")  # создание/правка/публикация постов

# платформы, доступные для создания в Ф2; instagram ждёт бизнес-аккаунт (Ф6)
PLATFORMS = ("telegram", "vk", "dzen")
PLATFORM_LABELS = {"telegram": "Telegram", "vk": "ВКонтакте",
                   "dzen": "Дзен", "instagram": "Instagram"}
SECRET_KEYS = {"telegram": "bot_token", "vk": "vk_token", "dzen": "bot_token"}
_HASHTAG_MODES = ("keep", "append", "strip")
_TOKEN_MIN_LEN = 20
_TOKEN_MAX_LEN = 256


def _ok(data):
    return {"ok": True, "data": data}


async def _require_admin(db: AsyncSession, user) -> None:
    m = await db.get(TeamMember, user.id)
    if m is None or (m.role_key or "") != "admin":
        raise ForbiddenError("управление каналами публикаций — только администратор (role_key=admin)")


def _validate_token(platform: str, token) -> str:
    token = (token or "").strip()
    if not _TOKEN_MIN_LEN <= len(token) <= _TOKEN_MAX_LEN:
        raise ValidationError(f"токен платформы: строка {_TOKEN_MIN_LEN}..{_TOKEN_MAX_LEN} символов")
    if re.search(r"[\s]", token):
        raise ValidationError("токен платформы не должен содержать пробелов/переносов")
    return token


def _validate_target(platform: str, target) -> str:
    target = (target or "").strip()
    if not target:
        raise ValidationError("target обязателен (chat_id канала / owner_id сообщества)")
    if len(target) > 128:
        raise ValidationError("target: до 128 символов")
    if platform == "vk" and not re.fullmatch(r"-\d+", target):
        raise ValidationError("для VK target — owner_id сообщества со знаком минус, например -12345678")
    if platform in ("telegram", "dzen") and not re.fullmatch(r"-?\d+|@\w{3,64}", target):
        raise ValidationError("для Telegram/Дзен target — числовой chat_id или @username")
    return target


def _normalize_template(template) -> dict:
    """Известные ключи проверяем, прочие проходим как есть (движок §46.3)."""
    if template is None:
        return {}
    if not isinstance(template, dict):
        raise ValidationError("template должен быть JSON-объектом")
    t = dict(template)
    if "max_len" in t and t["max_len"] is not None:
        if not isinstance(t["max_len"], int) or isinstance(t["max_len"], bool) \
                or not 100 <= t["max_len"] <= 4096:
            raise ValidationError("template.max_len: целое 100..4096 или null")
    if t.get("hashtags") is not None and t["hashtags"] not in _HASHTAG_MODES:
        raise ValidationError(f"template.hashtags: {'/'.join(_HASHTAG_MODES)} или null")
    if t.get("llm_prompt") is not None:
        if not isinstance(t["llm_prompt"], str) or len(t["llm_prompt"]) > 2000:
            raise ValidationError("template.llm_prompt: строка до 2000 символов или null")
    return t


def _payload(ch: PubChannel) -> dict:
    """Канал для API: секреты не отдаём, только признак наличия."""
    return {
        "id": ch.id,
        "name": ch.name,
        "platform": ch.platform,
        "platform_label": PLATFORM_LABELS.get(ch.platform, ch.platform),
        "target": ch.target,
        "status": ch.status,
        "frozen_at": ch.frozen_at.isoformat() if ch.frozen_at else None,
        "sort_order": ch.sort_order,
        "has_token": bool((ch.secrets or {}).get(SECRET_KEYS.get(ch.platform, ""))),
        "template": ch.template or {},
        "created_at": ch.created_at.isoformat() if ch.created_at else None,
    }


@router.get("/channels")
async def list_channels(db: AsyncSession = Depends(get_db),
                        user=Depends(get_current_user)):
    rows = (await db.execute(
        select(PubChannel).order_by(PubChannel.sort_order, PubChannel.id)
    )).scalars().all()
    return _ok([_payload(ch) for ch in rows])


@router.post("/channels")
async def create_channel(payload: dict = Body(...),
                         db: AsyncSession = Depends(get_db),
                         user=Depends(get_current_user)):
    """Создать канал — только admin. Токен уходит в secrets и не возвращается."""
    await _require_admin(db, user)
    platform = (payload.get("platform") or "").strip()
    if platform == "instagram":
        raise ConflictError("Instagram подключается в Ф6: нужен бизнес/creator-аккаунт, "
                            "привязанный к странице Facebook")
    if platform not in PLATFORMS:
        raise ValidationError(f"platform: одна из {'/'.join(PLATFORMS)}")
    name = (payload.get("name") or "").strip()
    if not 1 <= len(name) <= 120:
        raise ValidationError("name: 1..120 символов")
    target = _validate_target(platform, payload.get("target"))
    token = _validate_token(platform, payload.get("token"))
    template = _normalize_template(payload.get("template"))
    sort_order = payload.get("sort_order", 0)
    if not isinstance(sort_order, int) or isinstance(sort_order, bool):
        raise ValidationError("sort_order: целое число")

    ch = PubChannel(name=name, platform=platform, target=target,
                    secrets={SECRET_KEYS[platform]: token},
                    template=template, status="active",
                    sort_order=sort_order, created_by=user.id,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc))
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    return _ok(_payload(ch))


@router.patch("/channels/{channel_id}")
async def update_channel(channel_id: int, payload: dict = Body(...),
                         db: AsyncSession = Depends(get_db),
                         user=Depends(get_current_user)):
    """Правка канала — только admin. token: передан непустой — ротация,
    не передан/пустой — не трогаем. status — заморозка/разморозка."""
    await _require_admin(db, user)
    ch = await db.get(PubChannel, channel_id)
    if ch is None:
        raise NotFoundError(f"канал {channel_id} не найден")

    if "name" in payload:
        name = (payload.get("name") or "").strip()
        if not 1 <= len(name) <= 120:
            raise ValidationError("name: 1..120 символов")
        ch.name = name
    if "target" in payload:
        ch.target = _validate_target(ch.platform, payload.get("target"))
    if "template" in payload:
        ch.template = _normalize_template(payload.get("template"))
    if "sort_order" in payload:
        sort_order = payload.get("sort_order")
        if not isinstance(sort_order, int) or isinstance(sort_order, bool):
            raise ValidationError("sort_order: целое число")
        ch.sort_order = sort_order
    token = (payload.get("token") or "").strip() if isinstance(payload.get("token"), str) \
        else (payload.get("token") if payload.get("token") is not None else "")
    if token:
        ch.secrets = {**(ch.secrets or {}),
                      SECRET_KEYS[ch.platform]: _validate_token(ch.platform, token)}
    if "status" in payload:
        status = payload.get("status")
        if status not in ("active", "frozen"):
            raise ValidationError("status: active|frozen")
        ch.status = status
        ch.frozen_at = datetime.now(timezone.utc) if status == "frozen" else None

    ch.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(ch)
    return _ok(_payload(ch))


# =========================================================================
# §46.7 (Ф3): посты публикаций + публикация «сейчас» (через n8n §46.2)
# =========================================================================

async def _require_role(db: AsyncSession, user, roles) -> None:
    m = await db.get(TeamMember, user.id)
    if m is None or (m.role_key or "") not in roles:
        raise ForbiddenError(
            "публикации: требуется роль " + " или ".join(roles))


def _abs_media(media) -> list:
    """media[]: [{type:'photo', url}] ≤10; относительный /agropilot/files/…
    достраиваем до абсолютного — URL качают Bot API и n8n."""
    if media is None:
        return []
    if not isinstance(media, (list, tuple)) or len(media) > 10:
        raise ValidationError("media: список до 10 элементов")
    out = []
    for m in media:
        if not isinstance(m, dict) or m.get("type") != "photo":
            raise ValidationError("media[]: только {type:'photo', url}")
        url = (m.get("url") or "").strip()
        if url.startswith("/agropilot/files/"):
            url = PUB_PUBLIC_BASE + url
        if not re.match(r"^https?://", url) or len(url) > 1024:
            raise ValidationError("media[].url: http(s)-ссылка или /agropilot/files/…")
        out.append({"type": "photo", "url": url})
    return out


async def _load_active_channels(db: AsyncSession) -> dict:
    rows = (await db.execute(
        select(PubChannel).where(PubChannel.status == "active")
    )).scalars().all()
    return {ch.id: ch for ch in rows}


async def _sync_post_channels(db, post: PubPost, channel_ids, overrides) -> list:
    """Привязать каналы к посту (для draft: пересоздание набора;
    overrides пишем в body_override). Возвращает список активных каналов."""
    channels = await _load_active_channels(db)
    seen = set()
    for cid in channel_ids:
        if not isinstance(cid, int) or cid in seen:
            raise ValidationError("channel_ids: список id активных каналов")
        seen.add(cid)
        if cid not in channels:
            raise ValidationError(f"канал {cid} не найден или заморожен")
    # чистим привязки, которых больше нет (каскада нет: PK post+channel)
    from sqlalchemy import delete
    await db.execute(
        delete(PubPostChannel).where(
            PubPostChannel.post_id == post.id,
            PubPostChannel.channel_id.not_in(seen) if seen else True))
    if not seen:
        return []
    ov = overrides or {}
    if not isinstance(ov, dict):
        raise ValidationError("overrides: {channel_id: текст}")
    for cid in seen:
        row = await db.get(PubPostChannel, (post.id, cid))
        if row is None:
            row = PubPostChannel(post_id=post.id, channel_id=cid, status="pending")
            db.add(row)
        bo = ov.get(str(cid))
        if bo is not None:
            if not isinstance(bo, str) or len(bo) > 4096:
                raise ValidationError(f"overrides[{cid}]: строка до 4096 символов")
            row.body_override = bo or None
    return [channels[cid] for cid in sorted(seen)]


def _post_payload(post, rows, channels_by_id) -> dict:
    chans = []
    for pc, ch in rows:
        chans.append({
            "channel_id": pc.channel_id,
            "name": ch.name if ch else "?",
            "platform": ch.platform if ch else "?",
            "status": pc.status,
            "platform_post_id": pc.platform_post_id,
            "error": pc.error,
            "body_override": pc.body_override,
            "published_at": pc.published_at.isoformat() if pc.published_at else None,
        })
    return {
        "id": post.id,
        "body_md": post.body_md,
        "media": post.media or [],
        "status": post.status,
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        "last_error": post.last_error,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "channels": chans,
    }


async def _post_or_404(db, post_id: int) -> PubPost:
    post = await db.get(PubPost, post_id)
    if post is None:
        raise NotFoundError(f"пост {post_id} не найден")
    return post


async def _post_with_channels(db, post) -> dict:
    rows = (await db.execute(
        select(PubPostChannel, PubChannel)
        .outerjoin(PubChannel, PubChannel.id == PubPostChannel.channel_id)
        .where(PubPostChannel.post_id == post.id)
        .order_by(PubPostChannel.channel_id))).all()
    return _post_payload(post, rows, None)


@router.get("/posts")
async def list_posts(limit: int = 50, db: AsyncSession = Depends(get_db),
                     user=Depends(get_current_user)):
    limit = max(1, min(limit, 200))
    posts = (await db.execute(
        select(PubPost).order_by(PubPost.id.desc()).limit(limit))).scalars().all()
    out = []
    for post in posts:
        out.append(await _post_with_channels(db, post))
    return _ok(out)


def _parse_scheduled(value) -> Optional[datetime]:
    """scheduled_at: ISO 8601 (naive = DEFAULT_TZ, конвенция §таймзон);
    null/отсутствие = нет. Прошедшее время — ошибка (планируем только вперёд)."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("scheduled_at: ISO 8601 строка или null")
    from backend.common.tz import parse_dt
    try:
        dt = parse_dt(value.strip())
    except Exception:
        raise ValidationError("scheduled_at: некорректное время (ISO 8601)")
    if dt <= datetime.now(timezone.utc):
        raise ValidationError("scheduled_at: только будущее время")
    return dt


@router.post("/posts")
async def create_post(payload: dict = Body(...),
                      db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    """Черновик публикации (admin|manager); с scheduled_at — сразу
    запланированный (status=scheduled, публикует scheduler §46.8)."""
    await _require_role(db, user, PUBLISH_ROLES)
    body_md = payload.get("body_md")
    if not isinstance(body_md, str) or not 1 <= len(body_md.strip()) <= 20000:
        raise ValidationError("body_md: 1..20000 символов")
    media = _abs_media(payload.get("media"))
    scheduled_at = _parse_scheduled(payload.get("scheduled_at"))
    post = PubPost(body_md=body_md, media=media,
                   status="scheduled" if scheduled_at else "draft",
                   scheduled_at=scheduled_at,
                   created_by=user.id,
                   created_at=datetime.now(timezone.utc),
                   updated_at=datetime.now(timezone.utc))
    db.add(post)
    await db.flush()
    channels = await _sync_post_channels(db, post, payload.get("channel_ids") or [],
                                         payload.get("overrides"))
    if not channels:
        # пост без каналов хранить можно (дозаполнится в PATCH), но предупреждаем
        pass
    await db.commit()
    await db.refresh(post)
    return _ok(await _post_with_channels(db, post))


@router.get("/posts/{post_id}")
async def get_post(post_id: int, db: AsyncSession = Depends(get_db),
                   user=Depends(get_current_user)):
    post = await _post_or_404(db, post_id)
    return _ok(await _post_with_channels(db, post))


@router.patch("/posts/{post_id}")
async def update_post(post_id: int, payload: dict = Body(...),
                      db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    """Правка черновика/запланированного (draft|scheduled): текст/медиа/каналы/
    overrides/scheduled_at (null → снять расписание, вернуть в draft)."""
    await _require_role(db, user, PUBLISH_ROLES)
    post = await _post_or_404(db, post_id)
    if post.status not in ("draft", "scheduled"):
        raise ConflictError(f"правка доступна черновику и запланированному (статус {post.status})")
    if "body_md" in payload:
        body_md = payload.get("body_md")
        if not isinstance(body_md, str) or not 1 <= len(body_md.strip()) <= 20000:
            raise ValidationError("body_md: 1..20000 символов")
        post.body_md = body_md
    if "media" in payload:
        post.media = _abs_media(payload.get("media"))
    if "channel_ids" in payload:
        await _sync_post_channels(db, post, payload.get("channel_ids") or [],
                                  payload.get("overrides"))
    if "scheduled_at" in payload:
        scheduled_at = _parse_scheduled(payload.get("scheduled_at"))
        post.scheduled_at = scheduled_at
        post.status = "scheduled" if scheduled_at else "draft"
        post.last_error = None
    elif "overrides" in payload:
        bound = (await db.execute(
            select(PubPostChannel).where(PubPostChannel.post_id == post.id))
            ).scalars().all()
        await _sync_post_channels(db, post,
                                  [pc.channel_id for pc in bound],
                                  payload.get("overrides"))
    post.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(post)
    return _ok(await _post_with_channels(db, post))


@router.delete("/posts/{post_id}")
async def delete_post(post_id: int, db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    """Удаление непубликованного (draft|scheduled; строки — каскадом)."""
    await _require_role(db, user, PUBLISH_ROLES)
    post = await _post_or_404(db, post_id)
    if post.status not in ("draft", "scheduled"):
        raise ConflictError(f"удаление доступно черновику и запланированному (статус {post.status})")
    await db.delete(post)
    await db.commit()
    return _ok({"deleted": post_id})


@router.post("/posts/{post_id}/publish")
async def publish_post(post_id: int, payload: dict = Body(default={}),
                       db: AsyncSession = Depends(get_db),
                       user=Depends(get_current_user)):
    """Публиковать «сейчас»: каналы → pending, затем синхронный вызов n8n
    (§46.2) с проксированием его ответа. Повтор для failed/partial."""
    await _require_role(db, user, PUBLISH_ROLES)
    post = await _post_or_404(db, post_id)
    # защита от двойного клика: свежий publishing блокирует повтор; зависший
    # дольше 3 минут (движок умер) — разрешаем повторную публикацию
    if post.status == "publishing" and post.updated_at:
        ua = post.updated_at
        if ua.tzinfo is None:
            ua = ua.replace(tzinfo=timezone.utc)  # sqlite-совместимость
        if (datetime.now(timezone.utc) - ua).total_seconds() < 180:
            raise ConflictError("пост уже публикуется")
    channel_ids = payload.get("channel_ids")
    if channel_ids is None:
        bound = (await db.execute(
            select(PubPostChannel).where(PubPostChannel.post_id == post.id))
            ).scalars().all()
        channel_ids = [pc.channel_id for pc in bound]
    channels = await _sync_post_channels(db, post, channel_ids or [],
                                         payload.get("overrides"))
    if not channels:
        raise ValidationError("нет активных каналов: выберите каналы или разморозьте")
    post.scheduled_at = None  # ручная публикация снимает расписание (§46.8)
    post.status = "publishing"
    await db.commit()

    body = _json.dumps({"post_id": post.id}).encode()
    req = urllib.request.Request(
        PUB_ENGINE_URL, data=body, method="POST",
        headers={"Content-Type": "application/json", "X-PUB-TOKEN": PUB_ENGINE_TOKEN})
    try:
        # to_thread: urllib синхронный, не блокируем event loop
        with await asyncio.to_thread(urllib.request.urlopen, req, timeout=150) as resp:
            return _json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return _json.loads(e.read())  # 400/404 от webhook — проксируем телом
        except Exception:
            raise ConflictError(f"движок публикаций вернул HTTP {e.code}")
    except urllib.error.URLError as e:
        post = await _post_or_404(db, post_id)
        post.status = "failed"
        post.last_error = f"движок недоступен: {e.reason}"
        post.updated_at = datetime.now(timezone.utc)
        await db.commit()
        raise ConflictError(f"движок публикаций недоступен: {e.reason}")
