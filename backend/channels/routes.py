# backend/channels/routes.py -- CRUD каналов публикаций (§21.1, Этап-4 хвост)
#
# Mount: app.include_router(channels_router, prefix="/agropilot/api/v1")
# Секреты в connection НЕ хранятся: только ссылки на имена переменных .env
# (например {"chat_id": "-100...", "token_env": "TELEGRAM_BOT_TOKEN"}).

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.channels.models import Channel
from backend.common.deps import get_db, get_current_user
from backend.common.errors import NotFoundError, ValidationError

channels_router = APIRouter(prefix="/channels", tags=["channels"])

VALID_TYPE = ("telegram", "instagram", "site")


def _ok(data):
    return {"ok": True, "data": data}


class ChannelCreate(BaseModel):
    type: str
    name: str
    connection: Optional[dict] = None
    adapt_prompt: Optional[str] = None


class ChannelPatch(BaseModel):
    name: Optional[str] = None
    connection: Optional[dict] = None
    adapt_prompt: Optional[str] = None
    active: Optional[bool] = None


@channels_router.get("")
async def list_channels(
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    rows = (await db.execute(select(Channel).order_by(Channel.id))).scalars().all()
    return _ok([r.to_dict() for r in rows])


@channels_router.post("")
async def create_channel(
    payload: ChannelCreate,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    if payload.type not in VALID_TYPE:
        raise ValidationError(f"type должен быть одним из {VALID_TYPE}")
    name = (payload.name or "").strip()
    if not name:
        raise ValidationError("name обязателен")
    conn = payload.connection or {}
    if "token" in conn or "bot_token" in conn:
        raise ValidationError("токены в connection запрещены — используйте token_env")
    item = Channel(
        type=payload.type, name=name,
        connection=conn, adapt_prompt=payload.adapt_prompt,
        active=True,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@channels_router.patch("/{channel_id}")
async def patch_channel(
    channel_id: int,
    payload:    ChannelPatch,
    db:         AsyncSession = Depends(get_db),
    user                     = Depends(get_current_user),
):
    item = await db.get(Channel, channel_id)
    if not item:
        raise NotFoundError(f"channel {channel_id} не найден")
    data = payload.model_dump(exclude_unset=True)
    if "connection" in data and (
        "token" in (data["connection"] or {}) or "bot_token" in (data["connection"] or {})
    ):
        raise ValidationError("токены в connection запрещены — используйте token_env")
    for f, v in data.items():
        setattr(item, f, v)
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@channels_router.delete("/{channel_id}")
async def delete_channel(
    channel_id: int,
    db:         AsyncSession = Depends(get_db),
    user                     = Depends(get_current_user),
):
    item = await db.get(Channel, channel_id)
    if not item:
        raise NotFoundError(f"channel {channel_id} не найден")
    await db.delete(item)
    await db.commit()
    return _ok({"deleted": channel_id})
