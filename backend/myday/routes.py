# backend/myday/routes.py -- агент напоминаний A6 (ТЗ v1.1 п. 8.7)
#
# Mount: app.include_router(myday_router, prefix="/agropilot/api/v1")
# GET  /v1/myday/digest?user_id=U1  — агрегат дня (задачи/сделки/входящие/посты)
# POST /v1/myday/digest {send:true}  — то же + LLM-сводка; send=true -> Telegram
#
# Тон сводки настраивается промтом A6_TONE (по умолчанию деловой;
# «агент подвёз дел» — пример неформального, ТЗ п. 8.7).

import asyncio
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.tasks.models import Task
from backend.deals.models import Deal
from backend.inbound.models import Inbound
from backend.content.models import Content
from backend.common.deps import get_db, get_current_user
from backend.common.errors import ValidationError
from backend.common.llm import llm_chat, llm_configured, LLMError
from backend.agents.runlog import llm_call_logged

myday_router = APIRouter(prefix="/myday", tags=["myday"])

ACTIVE_TASK_STATUS = ("active", "in_progress", "открыта", "new")
ACTIVE_DEAL_STAGES = ("lead", "assess", "proposal", "deal", "won")

A6_TONE = (
    os.environ.get("A6_TONE") or
    "Деловой, краткий, по делу. Обращайся к команде на «вы»."
)


def _ok(data):
    return {"ok": True, "data": data}


async def collect_day(db: AsyncSession, user_id: Optional[str]) -> dict:
    now = datetime.now(timezone.utc)
    today_end = now.replace(hour=23, minute=59, second=59)
    week = now + timedelta(days=7)

    tq = select(Task).where(Task.status.in_(ACTIVE_TASK_STATUS))
    if user_id:
        tq = tq.where((Task.owner_id == user_id) | (Task.assignee == user_id))
    tasks = (await db.execute(tq)).scalars().all()
    overdue = [t for t in tasks if t.due_at and t.due_at < now]
    today = [t for t in tasks if t.due_at and now <= t.due_at <= today_end]
    soon = [t for t in tasks if t.due_at and today_end < t.due_at <= week]

    deals = (await db.execute(
        select(Deal).where(Deal.stage.in_(ACTIVE_DEAL_STAGES))
    )).scalars().all()
    hot = sorted(
        [d for d in deals if (d.score or 0) >= 70],
        key=lambda d: -(d.score or 0))[:5]

    inbounds_new = (await db.execute(
        select(Inbound).where(Inbound.status == "new")
    )).scalars().all()

    posts_review = (await db.execute(
        select(Content).where(Content.status == "in_review")
    )).scalars().all()

    def t_dict(t):
        return {"id": t.id, "title": t.title, "due_at": t.due_at.isoformat() if t.due_at else None}

    return {
        "generated_at": now.isoformat(),
        "user_id": user_id,
        "tasks": {"overdue": [t_dict(t) for t in overdue],
                  "today": [t_dict(t) for t in today],
                  "soon": [t_dict(t) for t in soon]},
        "deals_hot": [{"id": d.id, "name": d.name, "stage": d.stage, "score": d.score}
                      for d in hot],
        "inbounds_new": [{"id": i.id, "subject": i.subject, "channel": i.channel}
                         for i in inbounds_new[:10]],
        "posts_in_review": [{"id": c.id, "title": c.title} for c in posts_review[:10]],
    }


def _build_prompt(day: dict) -> str:
    return (
        "Составь утреннюю сводку для команды агро-компании по данным ниже. "
        "Структура: 1) просроченные задачи (срочно), 2) на сегодня, 3) горячие "
        "сделки, 4) необработанные входящие, 5) посты на правке. Кажд пункт — "
        "1-3 строки, в конце один общий совет на день.\n\nДанные:\n"
        + json.dumps(day, ensure_ascii=False, indent=1)
    )


async def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return False
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat, "text": text[:4000]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8")).get("ok", False)
    except Exception:
        return False


class DigestBody(BaseModel):
    send: bool = False          # доставить в Telegram
    user_id: Optional[str] = None  # фильтр по пользователю (None = вся команда)
    tone: Optional[str] = None  # переопределение тона на один запуск


@myday_router.get("/digest")
async def get_digest(
    user_id: Optional[str] = None,
    db:    AsyncSession = Depends(get_db),
    user                 = Depends(get_current_user),
):
    return _ok(await collect_day(db, user_id))


@myday_router.post("/digest")
async def post_digest(
    payload: DigestBody,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    day = await collect_day(db, payload.user_id)
    summary = None
    if llm_configured():
        tone = payload.tone or A6_TONE
        try:
            sys = f"Ты — ассистент напоминаний A6 системы AgroPILOT. Тон: {tone}"
            summary = await llm_call_logged(db, 'a6', _build_prompt(day), sys,
                                            max_tokens=700,
                                            meta={"send": payload.send})
        except LLMError as e:
            summary = f"LLM недоступна ({str(e)[:100]}) — агрегат без сводки."
    sent = False
    if payload.send and summary:
        sent = await send_telegram("☀️ AgroPILOT — сводка дня\n\n" + summary)
        if not sent:
            raise ValidationError("сводка сформирована, но Telegram недоступен")
    return _ok({**day, "summary": summary, "telegram_sent": sent})
