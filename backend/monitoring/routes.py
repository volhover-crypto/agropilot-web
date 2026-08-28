# backend/monitoring/routes.py -- AgroPILOT Monitoring router (A-3, CONTRACTS.md §17)
#
# Mount: app.include_router(monitoring_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/monitoring
#
# ТОЛЬКО ЧТЕНИЕ (§17.1): таблицу field_alerts наполняют внешние процессы вне
# этого репозитория. POST/PATCH/DELETE здесь не появляются.
# Пагинация обязательна: data = {items, total, limit, offset}.

from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.deps import get_db, get_current_user
from backend.common.errors import ValidationError
from backend.monitoring.models import FieldAlert, VALID_LEVELS
from backend.strategy_tasks.models import StrategyTask

monitoring_router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def _ok(data):
    return {"ok": True, "data": data}


def _validate_level(level: Optional[str]) -> Optional[str]:
    """§17.3: сравнение регистронезависимое, недопустимый уровень -> 422."""
    if level is None:
        return None
    norm = level.lower()
    if norm not in VALID_LEVELS:
        raise ValidationError(
            f"Invalid level '{level}'. Allowed: {', '.join(VALID_LEVELS)}"
        )
    return norm


async def _focus_keywords(db: AsyncSession) -> list:
    """§17.4: объединение monitoring_focus всех задач стратегии.

    Таблица strategy_tasks может быть пустой — тогда набор пуст и лента
    отдаётся полностью, без пометок. Это штатное поведение, не ошибка.
    """
    rows = (await db.execute(select(StrategyTask.monitoring_focus))).scalars().all()
    words = []
    seen = set()
    for focus in rows:
        for w in (focus or []):
            key = str(w).strip().lower()
            if key and key not in seen:
                seen.add(key)
                words.append(str(w).strip())
    return words


def _match_focus(alert: FieldAlert, words: list) -> list:
    """Слова, встречающиеся в message/parameter/category (регистронезависимо)."""
    if not words:
        return []
    haystack = " ".join(
        filter(None, [alert.message, alert.parameter, alert.category])
    ).lower()
    return [w for w in words if w.lower() in haystack]


@monitoring_router.get("")
async def list_monitoring(
    level:    Optional[str]  = Query(None),
    category: Optional[str]  = Query(None),
    source:   Optional[str]  = Query(None),
    q:        Optional[str]  = Query(None),
    since:    Optional[date] = Query(None),
    focus:    bool           = Query(False),
    limit:    int            = Query(50, ge=1, le=200),
    offset:   int            = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """§17.3 — лента наблюдений, новое сверху."""
    norm_level = _validate_level(level)

    conds = []
    if norm_level:
        # в таблице встречаются CRITICAL/WARNING — сравниваем по нижнему регистру
        conds.append(func.lower(FieldAlert.level) == norm_level)
    if category:
        conds.append(FieldAlert.category == category)
    if source:
        conds.append(FieldAlert.source == source)
    if since:
        conds.append(cast(FieldAlert.created_at, Date) >= since)
    if q:
        like = f"%{q}%"
        conds.append(or_(
            FieldAlert.message.ilike(like),
            FieldAlert.parameter.ilike(like),
        ))

    total_stmt = select(func.count()).select_from(FieldAlert)
    items_stmt = select(FieldAlert)
    for c in conds:
        total_stmt = total_stmt.where(c)
        items_stmt = items_stmt.where(c)

    words = await _focus_keywords(db)

    # §17.4: focus=true отбирает по вычисляемой пометке, поэтому фильтруем
    # после выборки — иначе total и пагинация разойдутся с содержимым.
    if focus:
        rows = (await db.execute(
            items_stmt.order_by(FieldAlert.created_at.desc(), FieldAlert.id.desc())
        )).scalars().all()
        marked = [(r, _match_focus(r, words)) for r in rows]
        marked = [(r, m) for r, m in marked if m]
        total = len(marked)
        page = marked[offset:offset + limit]
        items = [r.to_dict(m) for r, m in page]
    else:
        total = (await db.execute(total_stmt)).scalar() or 0
        rows = (await db.execute(
            items_stmt.order_by(FieldAlert.created_at.desc(), FieldAlert.id.desc())
                      .limit(limit).offset(offset)
        )).scalars().all()
        items = [r.to_dict(_match_focus(r, words)) for r in rows]

    return _ok({
        "items":  items,
        "total":  int(total),
        "limit":  limit,
        "offset": offset,
    })


@monitoring_router.get("/stats")
async def monitoring_stats(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """§17.5 — счётчики и свежесть ленты."""
    by_level = {}
    for lvl, cnt in (await db.execute(
        select(func.lower(FieldAlert.level), func.count()).group_by(func.lower(FieldAlert.level))
    )).all():
        by_level[lvl or "unknown"] = int(cnt)

    by_category = {}
    for cat, cnt in (await db.execute(
        select(FieldAlert.category, func.count()).group_by(FieldAlert.category)
    )).all():
        by_category[cat or "unknown"] = int(cnt)

    total = (await db.execute(select(func.count()).select_from(FieldAlert))).scalar() or 0
    latest = (await db.execute(select(func.max(FieldAlert.created_at)))).scalar()

    return _ok({
        "total":       int(total),
        "by_level":    by_level,
        "by_category": by_category,
        "latest_at":   latest.isoformat() if latest else None,
    })
