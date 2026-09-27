# backend/petchannel/routes.py -- §42: Telegram-канал ПЕТРУШКИ (О6)
#
# Mount: app.include_router(petchannel_router, prefix="/agropilot/api/v1")
#   POST /v1/telegram/webhook    — Telegram Bot API (secret-token в заголовке)
#   GET  /v1/telegram/bindcode   — код привязки (auth; показать в вебе)
#   GET  /v1/telegram/bindings   — свои привязки (?all=1 — менеджер)
#   PATCH /v1/telegram/bindings/{id} {notify_mask} — opt-in подписки
#
# Входящие тексты -- только от привязанных chat_id -> orchChat от имени
# пользователя; непривязанные -- ignore с журированием (DoD О6-2).
# Ответ на вопрос агента из TG: /ans <id> <текст> -- тот же лог
# agent_questions, что и в вебе (DoD О6-3).

import re
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.deps import get_db, get_current_user
from backend.common.errors import ForbiddenError, NotFoundError, ValidationError
from backend.petchannel.models import (
    ChannelBinding, VALID_MASKS, code_expires, gen_bind_code, parse_mask,
    render_mask, session_key,
)
from backend.petchannel.tg import bot_username, send_message
from backend.questions.models import AgentQuestion, can_answer
from backend.team.models import TeamMember

petchannel_router = APIRouter(prefix="/telegram", tags=["telegram"])

_MANAGER_ROLE_KEYS = {"manager", "admin"}


def _ok(data):
    return {"ok": True, "data": data}


async def _is_manager(db: AsyncSession, user) -> bool:
    member = await db.get(TeamMember, user.id)
    return bool(member and member.role_key in _MANAGER_ROLE_KEYS)


def _log_ignore(chat_id, reason: str):
    # журнал непривязанных/странных апдейтов (DoD О6-2) -- stdout сервиса
    print(f"[petchannel] ignore chat_id={chat_id}: {reason}", flush=True)


# ---------------------------------------------------------------------------
# Привязка (веб-сторона)
# ---------------------------------------------------------------------------

@petchannel_router.get("/bindcode")
async def get_bindcode(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Код привязки: отправить боту команду /start <код> в течение 15 мин."""
    row = (await db.execute(select(ChannelBinding).where(
        ChannelBinding.user_id == user.id,
        ChannelBinding.channel == "telegram",
    ))).scalars().first()
    if row is None:
        row = ChannelBinding(user_id=user.id, channel="telegram")
        db.add(row)
    row.bind_code = gen_bind_code()
    row.bind_code_expires = code_expires(datetime.now(timezone.utc))
    await db.commit()
    await db.refresh(row)
    return _ok({
        "code": row.bind_code,
        "expires_at": row.bind_code_expires.isoformat(),
        "bot": f"@{bot_username()}",
        "instruction": f"Отправьте боту @{bot_username()} команду: /start {row.bind_code}",
    })


@petchannel_router.get("/bindings")
async def list_bindings(
    all: int = Query(0, ge=0, le=1),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    see_all = bool(all) and await _is_manager(db, user)
    q = select(ChannelBinding).where(ChannelBinding.channel == "telegram")
    if not see_all:
        q = q.where(ChannelBinding.user_id == user.id)
    rows = (await db.execute(q.order_by(ChannelBinding.id))).scalars().all()
    return _ok([r.to_dict() for r in rows])


class MaskPatch(BaseModel):
    notify_mask: list[str]


@petchannel_router.patch("/bindings/{binding_id}")
async def patch_binding(
    binding_id: int,
    body: MaskPatch,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    row = await db.get(ChannelBinding, binding_id)
    if row is None:
        raise NotFoundError(f"binding {binding_id} не найдена")
    if row.user_id != user.id and not await _is_manager(db, user):
        raise ForbiddenError("только владелец или менеджер")
    bad = set(body.notify_mask) - set(VALID_MASKS)
    if bad:
        raise ValidationError(f"неизвестные маски: {sorted(bad)}; допустимо {list(VALID_MASKS)}")
    row.notify_mask = render_mask(body.notify_mask)
    await db.commit()
    await db.refresh(row)
    return _ok(row.to_dict())


# ---------------------------------------------------------------------------
# Webhook (Telegram-сторона; авторизация -- secret-token в заголовке)
# ---------------------------------------------------------------------------

_ANS_RE = re.compile(r"^/ans\s+(\d+)\s+(.+)$", re.S)
_MASK_RE = re.compile(r"^/mask(?:\s+(\S+)(?:\s+(on|off))?)?\s*$", re.I)


def parse_answer_command(text: str) -> Optional[tuple[int, str]]:
    m = _ANS_RE.match((text or "").strip())
    return (int(m.group(1)), m.group(2).strip()) if m else None


def parse_mask_command(text: str) -> Optional[tuple[Optional[str], Optional[str]]]:
    m = _MASK_RE.match((text or "").strip())
    return (m.group(1), m.group(2)) if m else None


async def handle_update(db: AsyncSession, update: dict) -> str:
    """Один апдейт -> текст ответа пользователю (или '' = молча).
    Все исключения глотаются уровнем выше: webhook всегда 200 (иначе
    Telegram будет ретраить)."""
    msg = (update or {}).get("message") or {}
    chat_id = str(msg.get("chat", {}).get("id", "") or "")
    text = (msg.get("text") or "").strip()
    if not chat_id or not text:
        return ""

    binding = (await db.execute(select(ChannelBinding).where(
        ChannelBinding.channel == "telegram",
        ChannelBinding.chat_id == chat_id,
    ))).scalars().first()

    # --- привязка: /start <код> (единственная команда непривязанных) ---
    if binding is None or binding.verified_at is None:
        if text.startswith("/start"):
            code = text.split(maxsplit=1)[1].strip() if " " in text else ""
            now = datetime.now(timezone.utc)
            pending = (await db.execute(select(ChannelBinding).where(
                ChannelBinding.channel == "telegram",
                ChannelBinding.bind_code == code,
            ))).scalars().first()
            if pending is None or not pending.bind_code_expires or pending.bind_code_expires < now:
                _log_ignore(chat_id, "код привязки не найден/истёк")
                return "Код не найден или истёк. Получите свежий код в вебе (кнопка TG у чата ПЕТРУШКИ)."
            old = (await db.execute(select(ChannelBinding).where(
                ChannelBinding.channel == "telegram",
                ChannelBinding.chat_id == chat_id,
            ))).scalars().first()
            if old is not None and old.id != pending.id:
                db.delete(old)
            pending.chat_id = chat_id
            pending.verified_at = now
            pending.bind_code = None
            pending.bind_code_expires = None
            await db.commit()
            return "✅ Привязка выполнена. Теперь пишите мне — я ПЕТРУШКА. /mask — управление уведомлениями."
        _log_ignore(chat_id, "непривязанный chat_id")
        return ""  # посторонний -- игнор с журмированием (DoD О6-2)

    user_ns = SimpleNamespace(id=binding.user_id)
    skey = session_key(binding.user_id, chat_id)

    # --- команды привязанного ---
    ans = parse_answer_command(text)
    if ans is not None:
        qid, answer = ans
        q = await db.get(AgentQuestion, qid)
        now = datetime.now(timezone.utc)
        if q is None or (q.user_id != binding.user_id):
            return "Вопрос не найден."
        if not can_answer(q, now):
            q.status = "expired"
            await db.commit()
            return "Вопрос истёк (TTL) — ответ не принят."
        q.status = "answered"
        q.answer_text = answer[:4000]
        q.answered_at = now
        await db.commit()
        return "✅ Ответ записан (виден и в вебе — контур единый)."

    mask_cmd = parse_mask_command(text)
    if mask_cmd is not None:
        kind, state = mask_cmd
        masks = binding.masks()
        if kind is None:
            return "Подписки: " + (", ".join(sorted(masks)) or "нет") + \
                   f"\nУправление: /mask digest|questions|insights on|off"
        if kind not in VALID_MASKS:
            return f"Неизвестная подписка {kind}. Доступно: {', '.join(VALID_MASKS)}."
        masks = (masks | {kind}) if (state or "on").lower() != "off" else (masks - {kind})
        binding.notify_mask = render_mask(masks)
        await db.commit()
        return "Подписки обновлены: " + (", ".join(sorted(masks)) or "нет")

    if text.startswith("/"):
        return "Команды: /ans <№> <ответ> — ответ на вопрос; /mask — подписки."

    # --- обычный текст -> orchChat от имени пользователя (§41.3/§42) ---
    from backend.orchestrator.routes import orchestrator_chat

    try:
        result = await orchestrator_chat(db, user_ns, text, session_key=skey)
    except Exception as e:
        return f"Сбой ассистента: {str(e)[:120]}"
    reply = result.get("reply") or ""
    if result.get("knowledge") and result.get("citations"):
        src = "; ".join(f"[{i+1}] {c['title']}" for i, c in enumerate(result["citations"][:3]))
        reply = f"{reply}\n\n📚 Источники: {src}"
    return reply or "(пусто)"


@petchannel_router.post("/webhook")
async def webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_telegram_bot_api_secret_token: str = Header(default=""),
):
    import os

    secret = os.environ.get("PETRUSHKA_TG_WEBHOOK_SECRET", "").strip()
    if not secret or x_telegram_bot_api_secret_token != secret:
        raise ForbiddenError("bad secret-token")
    try:
        update = await request.json()
    except Exception:
        update = {}
    try:
        reply = await handle_update(db, update)
    except Exception as e:
        print(f"[petchannel] update error: {e}", flush=True)
        reply = ""
    msg = (update or {}).get("message") or {}
    chat_id = str(msg.get("chat", {}).get("id", "") or "")
    if reply and chat_id:
        send_message(chat_id, reply)  # доставка не блокирует 200
    return _ok({"handled": True})
