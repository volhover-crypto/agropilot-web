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


# §33: дефолты лимитов расходов (переопределяются через PATCH /agents/{code}.limits)
_LIMIT_DEFAULTS = {
    "cost_usd_day": 1.0,     # $/сутки на агента (gpt-4o-mini)
    "cost_usd_week": 5.0,    # $/7 дней
    "tokens_day": 200_000,   # токенов/сутки
    "errors_day": 5,         # ошибок/сутки
}

# §33: ожидаемая частота прогонов (часы); None = агент работает по запросу
_SCHEDULE_H = {"a1": 1, "a6": 24}


def _agent_limits(card: AgentCard) -> dict:
    """Слияние лимитов карточки с дефолтами (карточка приоритетна)."""
    merged = dict(_LIMIT_DEFAULTS)
    merged.update(card.limits or {})
    return merged


def _limit_alerts(code: str, day: dict, week: dict, limits: dict) -> list:
    """Алерты превышения лимитов за сутки/неделю (§33)."""
    out = []
    checks = [
        ("cost_day", day["cost_usd"], limits.get("cost_usd_day"), "$ {:.3f}/сутки > лимита $ {:.3f}"),
        ("cost_week", week["cost_usd"], limits.get("cost_usd_week"), "$ {:.3f}/7дн > лимита $ {:.3f}"),
        ("tokens_day", day["tokens"], limits.get("tokens_day"), "{} токенов/сутки > лимита {}"),
        ("errors_day", day["errors"], limits.get("errors_day"), "{} ошибок/сутки > лимита {}"),
    ]
    for kind, value, limit, fmt in checks:
        if limit and value > limit:  # limit=0/None — контроль отключён
            out.append({"agent_code": code, "kind": kind,
                        "value": value, "limit": limit,
                        "message": fmt.format(value, limit)})
    return out


def _staleness_hours(code: str, active: bool, last_run: dict | None) -> float | None:
    """Часы молчания агента с расписанием; None — расписание не задано/агент на паузе."""
    every = _SCHEDULE_H.get(code)
    if every is None or not active:
        return None
    if not last_run:
        return float(every * 24)  # ни одного прогона — «молчит» давно
    started = last_run.get("started_at") or ""
    try:
        t = datetime.fromisoformat(started)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return round((datetime.now(timezone.utc) - t).total_seconds() / 3600, 1)
    except ValueError:
        return None


@agents_router.get("/dashboard/summary")
async def dashboard_summary(
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    """§32 агрегаты 24ч/7д + §33 v2: дневной ряд 14д, алерты лимитов,
    метрика правок черновиков, «молчание» агентов с расписанием."""
    from datetime import timedelta
    from sqlalchemy import func, case
    from backend.agents.runlog_models import RunLog

    now = datetime.now(timezone.utc)
    day = now - timedelta(hours=24)
    week = now - timedelta(days=7)
    fortnight = now - timedelta(days=14)

    cards = (await db.execute(select(AgentCard).order_by(AgentCard.code))).scalars().all()

    # -- агрегаты по агентам (24ч/7д) + алерты + молчание --
    out, alerts = [], []
    for c in cards:
        async def agg(since):
            row = (await db.execute(select(
                func.count(RunLog.id),
                func.coalesce(func.sum(case((RunLog.status == 'error', 1), else_=0)), 0),
                func.coalesce(func.sum(RunLog.total_tokens), 0),
                func.coalesce(func.sum(RunLog.cost_usd), 0),
                func.coalesce(func.sum(RunLog.items), 0),
            ).where(RunLog.agent_code == c.code, RunLog.started_at >= since))).one()
            return {"runs": int(row[0]), "errors": int(row[1]),
                    "tokens": int(row[2]), "cost_usd": float(row[3] or 0),
                    "items": int(row[4])}
        day_agg, week_agg = await agg(day), await agg(week)
        last = (await db.execute(select(RunLog)
                .where(RunLog.agent_code == c.code)
                .order_by(RunLog.started_at.desc()).limit(1))).scalars().first()
        last_dict = last.to_dict() if last else None
        limits = _agent_limits(c)
        alerts.extend(_limit_alerts(c.code, day_agg, week_agg, limits))
        every = _SCHEDULE_H.get(c.code)
        stale = _staleness_hours(c.code, c.active, last_dict)
        if stale is not None and every and stale > every + 1:
            alerts.append({
                "agent_code": c.code, "kind": "silent", "value": stale,
                "limit": float(every),
                "message": "молчит {:.0f} ч (ожидался каждые {} ч)".format(stale, every)})
        out.append({
            "code": c.code, "name": c.name, "active": c.active,
            "day": day_agg, "week": week_agg,
            "last_run": last_dict,
            "expected_every_h": every,
            "stale_hours": stale,
        })

    # -- дневной ряд за 14 дней (дни по Asia/Almaty — как у таймеров) --
    day_expr = func.to_char(func.timezone("Asia/Almaty", RunLog.started_at), "YYYY-MM-DD")
    rows = (await db.execute(select(
        day_expr.label("d"),
        func.count(RunLog.id),
        func.coalesce(func.sum(case((RunLog.status == 'error', 1), else_=0)), 0),
        func.coalesce(func.sum(RunLog.total_tokens), 0),
        func.coalesce(func.sum(RunLog.cost_usd), 0),
    ).where(RunLog.started_at >= fortnight).group_by(day_expr).order_by(day_expr))).all()
    by_date = {r[0]: r for r in rows}
    almaty = timezone(timedelta(hours=5))
    daily = []
    for i in range(14):
        d = (now + timedelta(days=i - 13)).astimezone(almaty).strftime("%Y-%m-%d")
        r = by_date.get(d)
        daily.append({"date": d,
                      "runs": int(r[1]) if r else 0,
                      "errors": int(r[2]) if r else 0,
                      "tokens": int(r[3]) if r else 0,
                      "cost_usd": float(r[4]) if r else 0.0})

    # -- метрика правок черновиков (§33): версии после первой = правки --
    from backend.content.models import ContentVersion
    vrows = (await db.execute(select(
        ContentVersion.content_id,
        func.count(ContentVersion.id),
    ).where(ContentVersion.created_at >= fortnight)
        .group_by(ContentVersion.content_id))).all()
    contents = len(vrows)
    edited = sum(1 for r in vrows if r[1] > 1)
    revisions = sum(r[1] - 1 for r in vrows)
    edits = {
        "period_days": 14,
        "contents": contents,
        "edited": edited,
        "avg_revisions": round(revisions / contents, 2) if contents else 0.0,
        "untouched_pct": round(100.0 * (contents - edited) / contents, 1) if contents else 0.0,
    }

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
        "daily": daily,
        "alerts": alerts,
        "edits": edits,
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
