# backend/clients/routes.py -- AgroPILOT Clients router
#
# Mount: app.include_router(clients_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/clients
# Контракт §13.1 A-6: {"ok": true, "data": ...}
# API-слой поверх СУЩЕСТВУЮЩЕЙ таблицы clients. deals_count не читаем.

from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients.models import Client
from backend.deals.models import Deal
from backend.common.errors import NotFoundError
from backend.common.deps import get_db, get_current_user

clients_router = APIRouter(prefix="/clients", tags=["clients"])

VALID_HEALTH = {"green", "yellow", "red"}
VALID_STATUS = {"active", "inactive", "archived"}
VALID_SOURCE = {"manual", "signal", "smm", "petrushka"}


def _ok(data):
    return {"ok": True, "data": data}


def _validate(health, status, source):
    if health is not None and health not in VALID_HEALTH:
        raise HTTPException(status_code=422, detail=f"health must be one of {sorted(VALID_HEALTH)}")
    if status is not None and status not in VALID_STATUS:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(VALID_STATUS)}")
    if source is not None and source not in VALID_SOURCE:
        raise HTTPException(status_code=422, detail=f"source must be one of {sorted(VALID_SOURCE)}")


async def _deals_counts(db: AsyncSession) -> dict:
    q = (
        select(Deal.client_id, func.count())
        .where(Deal.client_id.is_not(None))
        .group_by(Deal.client_id)
    )
    rows = (await db.execute(q)).all()
    return {cid: cnt for cid, cnt in rows}


def _next_id(existing: list) -> str:
    max_n = 0
    for cid in existing:
        if cid and cid.startswith("C") and cid[1:].isdigit():
            max_n = max(max_n, int(cid[1:]))
    return f"C{max_n + 1}"


class ClientCreate(BaseModel):
    id:       Optional[str] = None
    name:     str
    industry: Optional[str] = None
    region:   Optional[str] = None
    need:     Optional[list] = None
    health:   Optional[str] = None
    source:   Optional[str] = None
    status:   Optional[str] = None


class ClientPatch(BaseModel):
    name:     Optional[str] = None
    industry: Optional[str] = None
    region:   Optional[str] = None
    need:     Optional[list] = None
    health:   Optional[str] = None
    source:   Optional[str] = None
    status:   Optional[str] = None


@clients_router.get("")
async def list_clients(
    status: Optional[str] = Query(None),
    health: Optional[str] = Query(None),
    limit:  int           = Query(100, le=500),
    db:     AsyncSession  = Depends(get_db),
    user                  = Depends(get_current_user),
):
    q = select(Client).order_by(Client.created_at.desc().nulls_last(), Client.id)
    if status:
        q = q.where(Client.status == status)
    if health:
        q = q.where(Client.health == health)
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    counts = await _deals_counts(db)
    data = []
    for r in rows:
        d = r.to_dict()
        d["dealsCount"] = counts.get(r.id, 0)
        data.append(d)
    return _ok(data)


@clients_router.get("/{client_id}")
async def get_client(
    client_id: str,
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    item = await db.get(Client, client_id)
    if not item:
        raise NotFoundError("Client not found")
    counts = await _deals_counts(db)
    d = item.to_dict()
    d["dealsCount"] = counts.get(item.id, 0)
    return _ok(d)


@clients_router.post("")
async def create_client(
    payload: ClientCreate,
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    _validate(payload.health, payload.status, payload.source)
    cid = payload.id
    if not cid:
        existing = (await db.execute(select(Client.id))).scalars().all()
        cid = _next_id(existing)
    item = Client(
        id         = cid,
        name       = payload.name,
        industry   = payload.industry,
        region     = payload.region,
        need       = payload.need,
        health     = payload.health or "green",
        source     = payload.source or "manual",
        status     = payload.status or "active",
        created_at = datetime.now(timezone.utc),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    d = item.to_dict()
    d["dealsCount"] = 0
    return _ok(d)


@clients_router.patch("/{client_id}")
async def patch_client(
    client_id: str,
    payload: ClientPatch,
    db:   AsyncSession = Depends(get_db),
    user               = Depends(get_current_user),
):
    item = await db.get(Client, client_id)
    if not item:
        raise NotFoundError("Client not found")
    data = payload.model_dump(exclude_unset=True)
    _validate(data.get("health"), data.get("status"), data.get("source"))
    for field, val in data.items():
        setattr(item, field, val)
    await db.commit()
    await db.refresh(item)
    counts = await _deals_counts(db)
    d = item.to_dict()
    d["dealsCount"] = counts.get(item.id, 0)
    return _ok(d)
