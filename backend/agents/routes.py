# backend/agents/routes.py -- управление агентами и промтами (§29, ТЗ п. 6.4/8.9)
#
# Mount: app.include_router(agents_router, prefix="/agropilot/api/v1")
# GET   /v1/agents                      — карточки + текущие промты
# PATCH /v1/agents/{code}               — карточка (name/model/limits/active)
# GET   /v1/agents/{code}/prompts       — история версий промта
# PUT   /v1/agents/{code}/prompt        — новая версия промта (откат = PUT
#                                          со старым текстом, версия растёт)

from typing import Optional

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.models import AgentCard, Prompt
from backend.agents.registry import next_version, invalidate_cache
from backend.common.deps import get_db, get_current_user
from backend.common.errors import NotFoundError, ValidationError, ForbiddenError
from backend.team.models import TeamMember

agents_router = APIRouter(prefix="/agents", tags=["agents"])

# Изменение карточек/промтов — только админ или agents:manage
_MANAGE_PERMS = ("agents:manage", "*:*")


def _ok(data):
    return {"ok": True, "data": data}


async def _can_manage(db: AsyncSession, user) -> bool:
    member = await db.get(TeamMember, user.id)
    if member is None:
        return False
    if member.role_key == "admin":
        return True
    return any(p in (member.permissions or []) for p in _MANAGE_PERMS)


class CardPatch(BaseModel):
    name:   Optional[str] = None
    role:   Optional[str] = None
    model:  Optional[str] = None
    limits: Optional[dict] = None
    active: Optional[bool] = None


class PromptPut(BaseModel):
    text: str
    note: Optional[str] = None


@agents_router.get("")
async def list_agents(
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    cards = (await db.execute(select(AgentCard).order_by(AgentCard.code))).scalars().all()
    out = []
    for c in cards:
        p = (await db.execute(
            select(Prompt).where(Prompt.agent_code == c.code)
            .order_by(Prompt.version.desc()).limit(1)
        )).scalars().first()
        out.append(c.to_dict(
            current_prompt=p.text if p else None,
            prompt_version=p.version if p else None))
    return _ok(out)


@agents_router.get("/runs/all")
async def list_runs(
    agent_code: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    from sqlalchemy import func
    from backend.agents.runlog_models import RunLog
    q = select(RunLog).order_by(RunLog.started_at.desc()).limit(min(limit, 200))
    if agent_code:
        q = q.where(RunLog.agent_code == agent_code)
    if status:
        q = q.where(RunLog.status == status)
    rows = (await db.execute(q)).scalars().all()
    return _ok([r.to_dict() for r in rows])


@agents_router.get("/dashboard/summary")
async def dashboard_summary(
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    """Агрегаты по агентам за 24ч/7д + лента последних запусков (§32)."""
    from datetime import timedelta
    from sqlalchemy import func, case
    from backend.agents.runlog_models import RunLog

    now = datetime.now(timezone.utc)
    day = now - timedelta(hours=24)
    week = now - timedelta(days=7)

    cards = (await db.execute(select(AgentCard).order_by(AgentCard.code))).scalars().all()
    out = []
    for c in cards:
        async def agg(since):
            row = (await db.execute(select(
                func.count(RunLog.id),
                func.coalesce(func.sum(case((RunLog.status == 'error', 1), else_=0)), 0),
                func.coalesce(func.sum(RunLog.total_tokens), 0),
                func.coalesce(func.sum(RunLog.cost_usd), 0),
                func.coalesce(func.sum(RunLog.items), 0),
            ).where(RunLog.agent_code == c.id, RunLog.started_at >= since))).one()
            return {"runs": int(row[0]), "errors": int(row[1]),
                    "tokens": int(row[2]), "cost_usd": float(row[3] or 0),
                    "items": int(row[4])}
        last = (await db.execute(select(RunLog)
                .where(RunLog.agent_code == c.id)
                .order_by(RunLog.started_at.desc()).limit(1))).scalars().first()
        out.append({
            "code": c.code, "name": c.name, "active": c.active,
            "day": await agg(day), "week": await agg(week),
            "last_run": last.to_dict() if last else None,
        })
    recent = (await db.execute(select(RunLog).order_by(
        RunLog.started_at.desc()).limit(15))).scalars().all()
    totals_week = (await db.execute(select(
        func.count(RunLog.id),
        func.coalesce(func.sum(RunLog.total_tokens), 0),
        func.coalesce(func.sum(RunLog.cost_usd), 0),
    ).where(RunLog.started_at >= week))).one()
    return _ok({
        "agents": out,
        "recent": [r.to_dict() for r in recent],
        "week_totals": {"runs": int(totals_week[0]), "tokens": int(totals_week[1]),
                        "cost_usd": float(totals_week[2] or 0)},
    })


@agents_router.patch("/{code}")
async def patch_card(
    code: str,
    payload: CardPatch,
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    if not await _can_manage(db, user):
        raise ForbiddenError("управление агентами требует права agents:manage")
    card = await db.get(AgentCard, code)
    if not card:
        raise NotFoundError(f"агент {code} не найден")
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise ValidationError("нечего обновлять")
    for f, v in data.items():
        setattr(card, f, v)
    await db.commit()
    await db.refresh(card)
    return _ok(card.to_dict())


@agents_router.get("/{code}/prompts")
async def prompt_history(
    code: str,
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    card = await db.get(AgentCard, code)
    if not card:
        raise NotFoundError(f"агент {code} не найден")
    rows = (await db.execute(
        select(Prompt).where(Prompt.agent_code == code)
        .order_by(Prompt.version.desc())
    )).scalars().all()
    return _ok([r.to_dict() for r in rows])


@agents_router.put("/{code}/prompt")
async def put_prompt(
    code: str,
    payload: PromptPut,
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    if not await _can_manage(db, user):
        raise ForbiddenError("управление промтами требует права agents:manage")
    card = await db.get(AgentCard, code)
    if not card:
        raise NotFoundError(f"агент {code} не найден")
    text = (payload.text or "").strip()
    if len(text) < 10:
        raise ValidationError("промт слишком короткий")
    version = await next_version(db, code)
    db.add(Prompt(agent_code=code, version=version, text=text,
                  note=payload.note, author_id=user.id))
    await db.commit()
    invalidate_cache(code)
    return _ok({"code": code, "version": version})
