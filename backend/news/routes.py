# backend/news/routes.py -- медиа-мониторинг A1 (контракт §20.2)
#
# Mount: app.include_router(news_router, prefix="/agropilot/api/v1")
# GET   /v1/news            — лента NewsItem (фильтры, пагинация)
# PATCH /v1/news/{id}       — статус: selected/rejected/used (content:approve)
# POST  /v1/news/scan       — запуск сканирования (n8n, сервисный JWT)

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.common.deps import get_db, get_current_user
from backend.common.errors import NotFoundError, ValidationError
from backend.news.models import NewsItem, Source
from backend.news.collectors import collect
from backend.team.models import TeamMember

news_router = APIRouter(prefix="/news", tags=["news"])

VALID_NEWS_STATUS = ("new", "selected", "rejected", "used")


def _ok(data):
    return {"ok": True, "data": data}


async def _can_moderate(db: AsyncSession, user) -> bool:
    member = await db.get(TeamMember, user.id)
    if member is None:
        return False
    if member.role_key in ("manager", "admin"):
        return True
    perms = member.permissions or []
    return any(p in perms for p in ("content:approve", "sources:approve", "*:*"))


def _relevance(text: str, keywords: list) -> tuple[Optional[Decimal], Optional[str]]:
    """MVP-оценка релевантности: доля ключевых слов источника, встретившихся в тексте.
    Заменяется LLM-оценкой при подключении шлюза (§10 ТЗ v1.1) без смены схемы."""
    if not keywords:
        return None, None
    low = (text or "").lower()
    matched = [kw for kw in keywords if str(kw).lower() in low]
    if not matched:
        return Decimal("0.00"), "нет совпадений с ключевыми словами"
    score = Decimal(len(matched)) / Decimal(len(keywords))
    return score.quantize(Decimal("0.01")), "совпадения: " + ", ".join(map(str, matched))


@news_router.get("")
async def list_news(
    source_id: Optional[int]  = Query(None),
    status:    Optional[str]  = Query(None),
    relevance_min: Optional[float] = Query(None, ge=0, le=1),
    limit:     int            = Query(50, ge=1, le=200),
    offset:    int            = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user              = Depends(get_current_user),
):
    q = select(NewsItem).order_by(NewsItem.fetched_at.desc())
    if source_id is not None:
        q = q.where(NewsItem.source_id == source_id)
    if status is not None:
        if status not in VALID_NEWS_STATUS:
            raise ValidationError(f"status должен быть одним из {VALID_NEWS_STATUS}")
        q = q.where(NewsItem.status == status)
    if relevance_min is not None:
        q = q.where(NewsItem.relevance >= relevance_min)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows = (await db.execute(q.limit(limit).offset(offset))).scalars().all()
    return _ok({"items": [r.to_dict() for r in rows], "total": total, "limit": limit, "offset": offset})


class NewsPatch(BaseModel):
    status: str


@news_router.patch("/{news_id}")
async def patch_news(
    news_id: int,
    body: NewsPatch,
    db: AsyncSession = Depends(get_db),
    user              = Depends(get_current_user),
):
    if body.status not in VALID_NEWS_STATUS:
        raise ValidationError(f"status должен быть одним из {VALID_NEWS_STATUS}")
    if not await _can_moderate(db, user):
        raise ValidationError("недостаточно прав (нужен content:approve)")
    item = await db.get(NewsItem, news_id)
    if item is None:
        raise NotFoundError(f"news_item {news_id} не найден")
    item.status = body.status
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@news_router.post("/scan")
async def scan_sources(
    db: AsyncSession = Depends(get_db),
    user              = Depends(get_current_user),
):
    """Обход активных источников, дедуп: UNIQUE(source_id, url) + pre-check в сессии."""
    if not await _can_moderate(db, user):
        raise ValidationError(
            "запуск сканирования доступен менеджерам/админам и A1-сервису (U7)"
        )

    run_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    sources = (await db.execute(
        select(Source).where(Source.active.is_(True), Source.status == "active")
    )).scalars().all()

    stats = {"sources": len(sources), "collected": 0, "inserted": 0, "errors": []}
    for src in sources:
        try:
            materials = collect(src.type, src.url)
        except Exception as e:
            stats["errors"].append({"source_id": src.id, "error": str(e)[:200]})
            continue
        stats["collected"] += len(materials)
        keywords = src.keywords or []
        for mat in materials[:50]:  # за один прогон — до 50 на источник
            url = mat.get("url") or ""
            if url:
                dup = await db.execute(
                    select(NewsItem.id).where(
                        NewsItem.source_id == src.id, NewsItem.url == url
                    ).limit(1)
                )
                if dup.first() is not None:
                    continue
            text_for_relevance = " ".join(filter(None, [mat["title"], mat.get("summary")]))
            rel, reason = _relevance(text_for_relevance, keywords)
            db.add(NewsItem(
                source_id=src.id,
                title=mat["title"],
                summary=mat.get("summary"),
                url=url or None,
                fetched_at=now,
                relevance=rel,
                relevance_reason=reason,
                agent_run_id=run_id,
            ))
            stats["inserted"] += 1
    await db.commit()
    return _ok({"run_id": run_id, **stats})
