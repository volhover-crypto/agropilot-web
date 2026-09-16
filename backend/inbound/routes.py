# backend/inbound/routes.py -- входящие обращения + A4 (контракт §22)
#
# Mount: app.include_router(inbound_router, prefix="/agropilot/api/v1")
# GET   /v1/inbound                    — очередь (фильтры status/channel/assigned)
# POST  /v1/inbound                    — ручное добавление (звонок и т.п.)
# PATCH /v1/inbound/{id}               — статус/ответственный/привязка клиента
# POST  /v1/inbound/{id}/classify      — A4: LLM-классификация (тема/срочность/черновик ответа)
# POST  /v1/inbound/{id}/convert       — конвертация в лид (переиспользует схему §15.6)

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.inbound.models import Inbound
from backend.common.deps import get_db, get_current_user
from backend.common.errors import NotFoundError, ValidationError, ConflictError
from backend.common.llm import llm_chat, llm_configured, LLMError
from backend.agents.registry import get_agent_prompt
from backend.agents.runlog import llm_call_logged

inbound_router = APIRouter(prefix="/inbound", tags=["inbound"])

VALID_CHANNEL = ("telegram", "email", "site", "social", "call")
VALID_STATUS = ("new", "in_progress", "converted", "spam")

A4_SYSTEM = (
    "Ты — ассистент по обработке входящих обращений агро-компании "
    "(ирригация, виноградники, плодовые). Верни СТРОГО JSON без markdown: "
    '{"topic": "<тема одним предложением>", "urgency": "low|medium|high", '
    '"is_spam": <true|false>, "reply_draft": "<черновик вежливого ответа на русском>"}'
)


def _ok(data):
    return {"ok": True, "data": data}


class InboundCreate(BaseModel):
    channel: str
    contact: Optional[str] = None
    subject: Optional[str] = None
    body:    Optional[str] = None


class InboundPatch(BaseModel):
    status:      Optional[str] = None
    assigned_to: Optional[str] = None
    client_id:   Optional[int] = None


@inbound_router.get("")
async def list_inbound(
    status:    Optional[str]  = Query(None),
    channel:   Optional[str]  = Query(None),
    assigned:  Optional[str]  = Query(None),
    limit:     int            = Query(100, le=500),
    offset:    int            = Query(0, ge=0),
    db:        AsyncSession   = Depends(get_db),
    user                      = Depends(get_current_user),
):
    q = select(Inbound).order_by(Inbound.received_at.desc())
    if status:
        if status not in VALID_STATUS:
            raise ValidationError(f"status должен быть одним из {VALID_STATUS}")
        q = q.where(Inbound.status == status)
    if channel:
        q = q.where(Inbound.channel == channel)
    if assigned:
        q = q.where(Inbound.assigned_to == assigned)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows = (await db.execute(q.limit(limit).offset(offset))).scalars().all()
    return _ok({"items": [r.to_dict() for r in rows], "total": total,
                "limit": limit, "offset": offset})


@inbound_router.post("")
async def create_inbound(
    payload: InboundCreate,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    if payload.channel not in VALID_CHANNEL:
        raise ValidationError(f"channel должен быть одним из {VALID_CHANNEL}")
    text = " ".join(filter(None, [payload.subject, payload.body, payload.contact]))
    dedup = hashlib.sha1((payload.channel + "|" + text.strip().lower()).encode()).hexdigest()[:40] \
        if text.strip() else None
    if dedup:
        dup = await db.execute(select(Inbound.id).where(Inbound.dedup_key == dedup).limit(1))
        if dup.first() is not None:
            raise ConflictError("дубликат обращения (тот же контакт/текст)")
    item = Inbound(
        channel=payload.channel,
        contact=payload.contact,
        subject=payload.subject,
        body=payload.body,
        received_at=datetime.now(timezone.utc),
        status="new",
        dedup_key=dedup,
        a4_class={},
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@inbound_router.patch("/{inbound_id}")
async def patch_inbound(
    inbound_id: int,
    payload:    InboundPatch,
    db:         AsyncSession = Depends(get_db),
    user                     = Depends(get_current_user),
):
    item = await db.get(Inbound, inbound_id)
    if not item:
        raise NotFoundError(f"inbound {inbound_id} не найден")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        if data["status"] not in VALID_STATUS:
            raise ValidationError(f"status должен быть одним из {VALID_STATUS}")
    for f in ("status", "assigned_to", "client_id"):
        if f in data:
            setattr(item, f, data[f])
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@inbound_router.post("/{inbound_id}/classify")
async def classify_inbound(
    inbound_id: int,
    db:         AsyncSession = Depends(get_db),
    user                     = Depends(get_current_user),
):
    """A4: LLM-классификация обращения + черновик ответа. Результат в a4_class."""
    if not llm_configured():
        raise ValidationError("LLM-шлюз не настроен (OPENROUTER_API_KEY)")
    item = await db.get(Inbound, inbound_id)
    if not item:
        raise NotFoundError(f"inbound {inbound_id} не найден")
    prompt = (
        f"Канал: {item.channel}\nКонтакт: {item.contact or 'не указан'}\n"
        f"Тема: {item.subject or '—'}\nТекст обращения:\n{item.body or '(пусто)'}"
    )
    try:
        a4 = await get_agent_prompt(db, 'a4', A4_SYSTEM)
        raw = await llm_call_logged(db, 'a4', prompt, a4, max_tokens=500,
                                    meta={"inbound_id": inbound_id})
    except LLMError as e:
        raise ValidationError(f"LLM сбой: {str(e)[:150]}")
    try:
        parsed = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception:
        raise ValidationError(f"LLM вернула не-JSON: {raw[:150]}")
    item.a4_class = {
        "topic": str(parsed.get("topic", ""))[:300],
        "urgency": parsed.get("urgency") if parsed.get("urgency") in ("low", "medium", "high") else "medium",
        "is_spam": bool(parsed.get("is_spam", False)),
        "reply_draft": str(parsed.get("reply_draft", ""))[:2000],
        "classified_at": datetime.now(timezone.utc).isoformat(),
    }
    if item.a4_class["is_spam"] and item.status == "new":
        item.status = "spam"
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@inbound_router.post("/{inbound_id}/convert")
async def convert_inbound(
    inbound_id: int,
    db:         AsyncSession = Depends(get_db),
    user                     = Depends(get_current_user),
):
    """Обращение → лид (схема §15.6 B<N>, история касаний сохраняется в a4_class)."""
    from backend.leads.models import Lead
    from backend.leads.routes import _next_lead_id

    item = await db.get(Inbound, inbound_id)
    if not item:
        raise NotFoundError(f"inbound {inbound_id} не найден")
    if item.status == "converted":
        raise ConflictError(f"обращение уже конвертировано в лид {item.lead_id}")
    lead = Lead(
        id=await _next_lead_id(db),
        name=(item.contact or item.subject or f"Обращение #{item.id}")[:200],
        status="new",
        source=f"inbound:{item.channel}",
    )
    db.add(lead)
    await db.flush()
    item.status = "converted"
    item.lead_id = lead.id
    await db.commit()
    await db.refresh(lead)
    return _ok({"inbound": item.to_dict(), "lead": lead.to_dict()})
