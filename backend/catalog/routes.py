# backend/catalog/routes.py -- AgroPILOT Catalog (Блок B, CONTRACTS.md §18)
#
# Mount: app.include_router(catalog_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/catalog
#
# READ-MODEL: агрегатор поверх существующих реестров. Своих таблиц и миграций
# НЕТ и не будет (§18.7). Ничего не пишем — только читаем.
#
# Модели проекта разнородны: Artifact объявлен классическим Column, у Goal и
# TeamMember в модели НЕ отображён created_at (в БД он есть). Поэтому доступ к
# необязательным полям — через getattr, а не по прямой ссылке.

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_, cast, String as SAString
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.deps import get_db, get_current_user
from backend.common.errors import NotFoundError, ValidationError

from backend.artifacts.models import Artifact
from backend.content.models import Content
from backend.deals.models import Deal
from backend.clients.models import Client
from backend.goals.models import Goal
from backend.strategy_tasks.models import StrategyTask
from backend.sources.models import Source
from backend.team.models import TeamMember

catalog_router = APIRouter(prefix="/catalog", tags=["catalog"])


def _ok(data):
    return {"ok": True, "data": data}


# §18.1 — ветки в порядке ТЗ §5.5. group_attr задаёт промежуточный уровень.
# link_route — §18.3: карточка есть только у client/deal/goal, остальные ведут
# в раздел-список.
BRANCHES = [
    {"key": "artifacts",      "type": "artifact",      "title": "Артефакты",
     "model": Artifact,     "title_attr": "title", "owner_attr": None,
     "group_attr": None,    "link_route": "artifacts"},
    {"key": "content",        "type": "content",       "title": "Контент",
     "model": Content,      "title_attr": "title", "owner_attr": "author_id",
     "group_attr": None,    "link_route": "content"},
    {"key": "deals",          "type": "deal",          "title": "Сделки",
     "model": Deal,         "title_attr": "name",  "owner_attr": "owner_id",
     "group_attr": None,    "link_route": "deal"},
    {"key": "clients",        "type": "client",        "title": "Клиенты",
     "model": Client,       "title_attr": "name",  "owner_attr": None,
     "group_attr": None,    "link_route": "client"},
    {"key": "goals",          "type": "goal",          "title": "Цели",
     "model": Goal,         "title_attr": "title", "owner_attr": "owner_id",
     "group_attr": None,    "link_route": "goal"},
    {"key": "strategy_tasks", "type": "strategy_task", "title": "Стратегические задачи",
     "model": StrategyTask, "title_attr": "title", "owner_attr": "owner_id",
     "group_attr": None,    "link_route": "strategy"},
    {"key": "sources",        "type": "source",        "title": "Источники",
     "model": Source,       "title_attr": "url",   "owner_attr": "added_by",
     "group_attr": "type",  "link_route": "monitoring"},
    {"key": "team",           "type": "team",          "title": "Пользователи",
     "model": TeamMember,   "title_attr": "name",  "owner_attr": None,
     "group_attr": "role",  "link_route": "skills"},
]

BRANCH_BY_KEY = {b["key"]: b for b in BRANCHES}
TYPE_TO_BRANCH = {b["type"]: b for b in BRANCHES}


def _col(branch, attr):
    """Колонка модели или None, если поле не отображено (см. шапку модуля)."""
    return getattr(branch["model"], attr, None) if attr else None


def _order(branch):
    """created_at DESC, id DESC — либо только id DESC, если created_at нет."""
    created = _col(branch, "created_at")
    ident = branch["model"].id
    return [created.desc(), ident.desc()] if created is not None else [ident.desc()]


def _leaf(branch, row) -> dict:
    title = getattr(row, branch["title_attr"], None)
    # У источника заголовок — url; handle уточняет, какой именно канал.
    if branch["key"] == "sources":
        handle = getattr(row, "handle", None)
        if handle:
            title = f"{title} · {handle}" if title else handle
    created = getattr(row, "created_at", None)
    owner = getattr(row, branch["owner_attr"], None) if branch["owner_attr"] else None
    return {
        "id":         row.id,
        "type":       branch["type"],
        "title":      title if title else str(row.id),
        "created_at": created.isoformat() if created else None,
        "owner":      owner,
        # §18.2: поля source_agent нет — данных для него не существует.
        "link":       {"route": branch["link_route"], "id": row.id},
    }


async def _count(db: AsyncSession, model, where=None) -> int:
    stmt = select(func.count()).select_from(model)
    if where is not None:
        stmt = stmt.where(where)
    return int((await db.execute(stmt)).scalar() or 0)


@catalog_router.get("/tree")
async def catalog_tree(
    node:   Optional[str] = Query(None),
    limit:  int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """§18.4 — корень, ветка, подветка. Неизвестный node -> 404."""

    # --- корень: перечень веток ---
    if not node:
        items = []
        for b in BRANCHES:
            items.append({
                "id":           b["key"],
                "type":         "branch",
                "title":        b["title"],
                "count":        await _count(db, b["model"]),
                "has_children": bool(b["group_attr"]),
            })
        return _ok({"items": items, "total": len(items), "limit": limit, "offset": 0})

    key, _, group = node.partition(":")
    branch = BRANCH_BY_KEY.get(key)
    if branch is None:
        raise NotFoundError(f"Catalog node '{node}' not found")

    group_col = _col(branch, branch["group_attr"])

    # --- ветка с промежуточным уровнем и без указанной подветки ---
    if group_col is not None and not group:
        rows = (await db.execute(
            select(group_col, func.count()).group_by(group_col).order_by(group_col)
        )).all()
        items = [{
            "id":           f"{key}:{val}",
            "type":         "branch",
            "title":        val if val else "—",
            "count":        int(cnt),
            "has_children": False,
        } for val, cnt in rows]
        return _ok({"items": items, "total": len(items), "limit": limit, "offset": 0})

    # --- листья ---
    where = None
    if group:
        if group_col is None:
            raise NotFoundError(f"Catalog node '{node}' not found")
        where = group_col == group
        if await _count(db, branch["model"], where) == 0:
            raise NotFoundError(f"Catalog node '{node}' not found")

    total = await _count(db, branch["model"], where)
    stmt = select(branch["model"])
    if where is not None:
        stmt = stmt.where(where)
    rows = (await db.execute(
        stmt.order_by(*_order(branch)).limit(limit).offset(offset)
    )).scalars().all()

    return _ok({
        "items":  [_leaf(branch, r) for r in rows],
        "total":  total,
        "limit":  limit,
        "offset": offset,
    })


@catalog_router.get("/search")
async def catalog_search(
    q:     str = Query(...),
    type:  Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """§18.5 — плоский поиск по заголовку и id во всех ветках."""
    term = (q or "").strip()
    if len(term) < 2:
        raise ValidationError("Query 'q' must be at least 2 characters long")

    if type is not None and type not in TYPE_TO_BRANCH:
        raise ValidationError(
            f"Invalid type '{type}'. Allowed: {', '.join(sorted(TYPE_TO_BRANCH))}"
        )

    branches = [TYPE_TO_BRANCH[type]] if type else BRANCHES
    like = f"%{term}%"
    items = []

    for b in branches:
        title_col = _col(b, b["title_attr"])
        conds = [cast(b["model"].id, SAString).ilike(like)]
        if title_col is not None:
            conds.append(title_col.ilike(like))
        rows = (await db.execute(
            select(b["model"]).where(or_(*conds))
                              .order_by(*_order(b)).limit(limit)
        )).scalars().all()
        for r in rows:
            leaf = _leaf(b, r)
            leaf["branch"] = b["key"]
            items.append(leaf)

    total = len(items)
    return _ok({
        "items":  items[:limit],
        "total":  total,
        "limit":  limit,
        "offset": 0,
    })
