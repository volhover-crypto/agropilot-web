# backend/assistant/routes.py -- чат-ассистент A7 (ТЗ v1.1 п. 8.8)
#
# Mount: app.include_router(assistant_router, prefix="/agropilot/api/v1")
# POST /v1/assistant/ask {question} — ответ по контексту системы.
#
# Справочник «вопрос -> источник» (ТЗ) реализован как контекстный срез:
# агрегаты (сделки/лиды/клиенты/задачи/входящие/контент) + новости
# медиа-мониторинга, отобранные по словам вопроса. LLM отвечает только
# по этим данным; данных нет — так и говорит.

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deals.models import Deal, VALID_STAGES
from backend.clients.models import Client
from backend.leads.models import Lead
from backend.tasks.models import Task
from backend.inbound.models import Inbound
from backend.content.models import Content
from backend.news.models import NewsItem
from backend.common.deps import get_db, get_current_user
from backend.common.errors import ValidationError
from backend.common.llm import llm_chat, llm_configured, LLMError

assistant_router = APIRouter(prefix="/assistant", tags=["assistant"])

A7_SYSTEM = (
    "Ты — внутренний ассистент A7 системы AgroPILOT (агро-B2B, ирригация/"
    "виноградники/плодовые). Отвечай НА РУССКОМ, кратко и только по данным "
    "контекста ниже; цифры бери из данных, ничего не выдумывай. Если данных "
    "нет — честно скажи и предложи, где посмотреть. До 6 предложений."
)

ACTIVE_TASK = ("active", "in_progress", "открыта", "new")


def _ok(data):
    return {"ok": True, "data": data}


async def build_context(db: AsyncSession, question: str) -> dict:
    now = datetime.now(timezone.utc)

    deals = (await db.execute(select(Deal))).scalars().all()
    by_stage = {st: 0 for st in VALID_STAGES}
    for d in deals:
        if d.stage in by_stage:
            by_stage[d.stage] += 1
    hot = sorted(deals, key=lambda d: -(d.score or 0))[:5]

    clients_n = (await db.execute(select(func.count()).select_from(Client))).scalar() or 0
    leads_rows = (await db.execute(
        select(Lead.status, func.count()).group_by(Lead.status))).all()
    leads_by = {str(k): int(v) for k, v in leads_rows}

    tasks = (await db.execute(select(Task).where(Task.status.in_(ACTIVE_TASK)))).scalars().all()
    overdue = [t for t in tasks if t.due_at and t.due_at < now]
    today = [t for t in tasks if t.due_at and now <= t.due_at <= now.replace(hour=23, minute=59)]

    inb = (await db.execute(select(func.count()).select_from(Inbound)
                            .where(Inbound.status == "new"))).scalar() or 0

    content_rows = (await db.execute(
        select(Content.status, func.count()).group_by(Content.status))).all()
    content_by = {str(k): int(v) for k, v in content_rows}

    # новости: слова вопроса >= 4 символов, последние 14 дней
    words = [w.lower() for w in re.findall(r"[а-яёa-z]{4,}", question or "")]
    nq = select(NewsItem).where(
        NewsItem.fetched_at >= now - timedelta(days=14)
    ).order_by(NewsItem.fetched_at.desc()).limit(100)
    news_all = (await db.execute(nq)).scalars().all()
    news = []
    for n in news_all:
        hay = ((n.title or "") + " " + (n.summary or "")).lower()
        # усечение основы (орошению/орошение): первые 6 символов слова
        if not words or any(w[:6] in hay for w in words):
            news.append({"title": (n.title or "")[:120],
                         "status": n.status,
                         "relevance": float(n.relevance) if n.relevance is not None else None,
                         "fetched_at": n.fetched_at.isoformat() if n.fetched_at else None})
        if len(news) >= 8:
            break

    return {
        "на_момент": now.isoformat(),
        "сделки": {"всего": len(deals), "по_этапам": by_stage,
                   "горячие": [{"название": d.name, "этап": d.stage, "score": d.score} for d in hot]},
        "клиенты": {"всего": clients_n},
        "лиды": {"по_статусам": leads_by},
        "задачи": {"активных": len(tasks), "просрочено": len(overdue),
                   "просроченные_примеры": [t.title for t in overdue[:5]],
                   "на_сегодня": len(today)},
        "входящие_новые": inb,
        "контент": {"по_статусам": content_by},
        "новости_мониторинга": news,
    }


class AskBody(BaseModel):
    question: str


@assistant_router.post("/ask")
async def ask(
    payload: AskBody,
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    q = (payload.question or "").strip()
    if not q:
        raise ValidationError("question пуст")
    if not llm_configured():
        raise ValidationError("LLM-шлюз не настроен (OPENROUTER_API_KEY)")
    ctx = await build_context(db, q)
    prompt = (
        "Контекст системы (JSON):\n" + json.dumps(ctx, ensure_ascii=False, indent=1)
        + "\n\nВопрос пользователя: " + q
    )
    try:
        answer = await asyncio.to_thread(llm_chat, prompt, A7_SYSTEM, None, 500)
    except LLMError as e:
        raise ValidationError(f"LLM сбой: {str(e)[:150]}")
    return _ok({"answer": answer, "context_stats": {
        "deals": ctx["сделки"]["всего"],
        "news_matched": len(ctx["новости_мониторинга"]),
    }})
