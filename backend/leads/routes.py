# backend/leads/routes.py -- AgroPILOT Leads router (A-6.1, CONTRACTS.md 14)
#
# Mount: app.include_router(leads_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/leads
# Пагинация обязательна: data = {items, total, limit, offset}

from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.deps import get_db, get_current_user
from backend.common.errors import NotFoundError, ConflictError, ValidationError
from backend.leads.models import Lead
from backend.clients.models import Client

leads_router = APIRouter(prefix="/leads", tags=["leads"])

VALID_STATUS = {"new", "active", "inactive", "converted"}


def _ok(data):
    return {"ok": True, "data": data}


def _validate_status(status: Optional[str]) -> None:
    if status is not None and status not in VALID_STATUS:
        raise ValidationError(
            f"Invalid status '{status}'. Allowed: {', '.join(sorted(VALID_STATUS))}"
        )


async def _next_client_id(db: AsyncSession) -> str:
    res = await db.execute(
        text("SELECT COALESCE(MAX(CAST(SUBSTRING(id FROM 2) AS INTEGER)), 0) "
             "FROM clients WHERE id ~ '^C[0-9]+$'")
    )
    return f"C{int(res.scalar() or 0) + 1}"


class LeadPatch(BaseModel):
    name:           Optional[str] = None
    status:         Optional[str] = None
    contact_person: Optional[str] = None
    phone:          Optional[str] = None
    email:          Optional[str] = None
    owner:          Optional[str] = None
    region:         Optional[str] = None
    industry:       Optional[str] = None
    comment:        Optional[str] = None


@leads_router.get("")
async def list_leads(
    status: Optional[str] = Query(None),
    owner:  Optional[str] = Query(None),
    q:      Optional[str] = Query(None),
    limit:  int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort:   str = Query("name", pattern="^(name|status|owner)$"),
    order:  str = Query("asc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    _validate_status(status)

    conds = []
    if status:
        conds.append(Lead.status == status)
    if owner:
        conds.append(Lead.owner == owner)
    if q:
        like = f"%{q}%"
        conds.append(or_(
            Lead.name.ilike(like),
            Lead.contact_person.ilike(like),
            Lead.phone.ilike(like),
        ))

    total_stmt = select(func.count()).select_from(Lead)
    items_stmt = select(Lead)
    for c in conds:
        total_stmt = total_stmt.where(c)
        items_stmt = items_stmt.where(c)

    sort_col = {"name": Lead.name, "status": Lead.status, "owner": Lead.owner}[sort]
    total = (await db.execute(total_stmt)).scalar() or 0
    rows = (await db.execute(
        items_stmt.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
                  .limit(limit).offset(offset)
    )).scalars().all()

    return _ok({
        "items":  [r.to_dict() for r in rows],
        "total":  int(total),
        "limit":  limit,
        "offset": offset,
    })


@leads_router.get("/stats")
async def leads_stats(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    rows = (await db.execute(
        select(Lead.status, func.count()).group_by(Lead.status)
    )).all()
    data = {k: 0 for k in sorted(VALID_STATUS)}
    total = 0
    for status_value, cnt in rows:
        total += int(cnt)
        if status_value in data:
            data[status_value] = int(cnt)
        else:
            data[status_value] = int(cnt)
    data["total"] = total
    return _ok(data)


@leads_router.get("/{lead_id}")
async def get_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if lead is None:
        raise NotFoundError(f"Lead '{lead_id}' not found")
    return _ok(lead.to_dict())


@leads_router.patch("/{lead_id}")
async def patch_lead(
    lead_id: str,
    payload: LeadPatch,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if lead is None:
        raise NotFoundError(f"Lead '{lead_id}' not found")

    data = payload.model_dump(exclude_unset=True)
    _validate_status(data.get("status"))
    for field, value in data.items():
        setattr(lead, field, value)

    await db.commit()
    await db.refresh(lead)
    return _ok(lead.to_dict())


@leads_router.post("/{lead_id}/convert")
async def convert_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if lead is None:
        raise NotFoundError(f"Lead '{lead_id}' not found")
    if lead.status == "converted" or lead.converted_client_id:
        raise ConflictError(
            f"Lead '{lead_id}' already converted to client '{lead.converted_client_id}'"
        )

    client = Client(
        id=await _next_client_id(db),
        name=lead.name,
        industry=lead.industry,
        region=lead.region,
        health="green",
        source="bitrix24",
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db.add(client)
    await db.flush()

    lead.status = "converted"
    lead.converted_client_id = client.id

    await db.commit()
    await db.refresh(lead)
    await db.refresh(client)
    return _ok({"lead": lead.to_dict(), "client": client.to_dict()})
