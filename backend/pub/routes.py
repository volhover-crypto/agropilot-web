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

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.deps import get_current_user, get_db
from backend.common.errors import (ConflictError, ForbiddenError, NotFoundError,
                                   ValidationError)
from backend.pub.models import PubChannel
from backend.team.models import TeamMember

router = APIRouter(prefix="/pub", tags=["pub"])

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
