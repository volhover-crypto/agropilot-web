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
from backend.deals.models import Deal

leads_router = APIRouter(prefix="/leads", tags=["leads"])

VALID_STATUS = {"new", "active", "inactive", "converted"}

# §15.7 B требует «первый в существующем VALID_STATUS deals». Такого набора в
# backend/deals нет (поле называется stage, валидации значений нет), поэтому
# берём default из модели Deal — stage="lead". Решение согласовано 2026-08-25.
DEAL_INITIAL_STAGE = "lead"


def _ok(data):
    return {"ok": True, "data": data}


def _validate_status(status: Optional[str]) -> None:
    if status is not None and status not in VALID_STATUS:
        raise ValidationError(
            f"Invalid status '{status}'. Allowed: {', '.join(sorted(VALID_STATUS))}"
        )


async def _next_seq_id(db: AsyncSession, table: str, prefix: str) -> str:
    """Следующий id вида <prefix><N>. table/prefix — только константы модуля."""
    res = await db.execute(
        text(f"SELECT COALESCE(MAX(CAST(SUBSTRING(id FROM 2) AS INTEGER)), 0) "
             f"FROM {table} WHERE id ~ '^{prefix}[0-9]+$'")
    )
    return f"{prefix}{int(res.scalar() or 0) + 1}"


async def _next_client_id(db: AsyncSession) -> str:
    return await _next_seq_id(db, "clients", "C")


async def _next_lead_id(db: AsyncSession) -> str:
    return await _next_seq_id(db, "leads", "B")


async def _next_deal_id(db: AsyncSession) -> str:
    return await _next_seq_id(db, "deals", "D")


class LeadCreate(BaseModel):
    name:           str
    contact_person: Optional[str] = None
    phone:          Optional[str] = None
    owner:          Optional[str] = None
    source:         Optional[str] = None
    comment:        Optional[str] = None
    status:         Optional[str] = None


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
    sort:   str = Query("name", pattern="^(name|status|owner|next_action_at)$"),
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

    sort_col = {
        "name":           Lead.name,
        "status":         Lead.status,
        "owner":          Lead.owner,
        "next_action_at": Lead.next_action_at,
    }[sort]
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


@leads_router.post("")
async def create_lead(
    payload: LeadCreate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """§15.7 A — создание лида вручную. id по схеме B<N>."""
    name = (payload.name or "").strip()
    if not name:
        raise ValidationError("Field 'name' is required and must be non-empty")

    _validate_status(payload.status)

    fields = payload.model_dump(exclude_none=True)
    fields.pop("name", None)
    fields.pop("status", None)

    lead = Lead(
        id=await _next_lead_id(db),
        name=name,
        status=payload.status or "new",
        **fields,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return _ok(lead.to_dict())


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

    # §15.7 C: перевод в inactive («Некачественный») требует причины.
    if data.get("status") == "inactive" and not (data.get("comment") or "").strip():
        raise ValidationError(
            "Field 'comment' is required and must be non-empty "
            "when moving a lead to status 'inactive'"
        )
    for field, value in data.items():
        setattr(lead, field, value)

    await db.commit()
    await db.refresh(lead)
    return _ok(lead.to_dict())


@leads_router.post("/{lead_id}/convert")
async def convert_lead(
    lead_id: str,
    target: str = Query("client", pattern="^(client|client_deal)$"),
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

    # §15.7 B: target=client_deal дополнительно создаёт сделку.
    # Явно перекрывает §14 «не трогаем deals». Схема deals НЕ меняется.
    deal = None
    if target == "client_deal":
        deal = Deal(
            id=await _next_deal_id(db),
            name=f"Сделка по лиду {lead.name}",
            stage=DEAL_INITIAL_STAGE,
            client_id=client.id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(deal)
        await db.flush()

    await db.commit()
    await db.refresh(lead)
    await db.refresh(client)
    if deal is not None:
        await db.refresh(deal)

    return _ok({
        "lead":   lead.to_dict(),
        "client": client.to_dict(),
        "deal":   deal.to_dict() if deal is not None else None,
    })
