# backend/deals/routes.py -- AgroPILOT M9 Deals router
#
# Mount: app.include_router(deals_router, prefix="/agropilot/api/v1")
# Resulting base path: /agropilot/api/v1/deals
#
# Политика фильтрации:
#   GET /deals       — все сделки команды (без фильтра по owner — командный рабочий стол)
#   GET /deals/:id   — одна сделка
#   PATCH /deals/:id — обновить stage/score/signal/updated_at

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.deals.models import Deal
from backend.common.errors import NotFoundError
from backend.common.deps import get_db, get_current_user

deals_router = APIRouter(prefix="/deals", tags=["deals"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DealPatch(BaseModel):
    stage:      Optional[str] = None
    score:      Optional[int] = None
    signal:     Optional[str] = None


def _ok(data):
    return {"ok": True, "data": data}


# ---------------------------------------------------------------------------
# GET /deals
# ---------------------------------------------------------------------------

@deals_router.get("")
async def list_deals(
    stage:  Optional[str] = Query(None),
    limit:  int           = Query(200, le=500),
    db:     AsyncSession  = Depends(get_db),
    user                  = Depends(get_current_user),
):
    """Все сделки команды. Опциональный фильтр по stage."""
    q = select(Deal).order_by(Deal.score.desc())
    if stage:
        q = q.where(Deal.stage == stage)
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return _ok([r.to_dict() for r in rows])


# ---------------------------------------------------------------------------
# GET /deals/:id
# ---------------------------------------------------------------------------

@deals_router.get("/{deal_id}")
async def get_deal(
    deal_id: str,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise NotFoundError("Deal not found")
    return _ok(deal.to_dict())


# ---------------------------------------------------------------------------
# PATCH /deals/:id
# ---------------------------------------------------------------------------

@deals_router.patch("/{deal_id}")
async def patch_deal(
    deal_id: str,
    body:    DealPatch,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise NotFoundError("Deal not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(deal, field, val)
    deal.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(deal)
    return _ok(deal.to_dict())
