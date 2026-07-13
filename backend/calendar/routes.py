# backend/calendar/routes.py -- AgroPILOT M7 FastAPI Calendar router
# Mount: app.include_router(router, prefix="/agropilot/api/v1")
# Resulting base path: /agropilot/api/v1/calendar  (matches CONTRACTS §1.2 /v1/calendar)
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import CalendarEvent, EventKind
from backend.common.errors import NotFoundError, ForbiddenError
from backend.common.deps import get_db, get_current_user

# -- Dependency stubs (replace with your actual db/auth deps) --
# from app.deps import get_db, current_user

router = APIRouter(prefix="/calendar", tags=["calendar"])

# --------------- Pydantic schemas ---------------

class EventCreate(BaseModel):
    title: str
    start_at: datetime
    description: Optional[str] = None
    end_at: Optional[datetime] = None
    all_day: bool = False
    deal_id: Optional[str] = None
    kind: EventKind = EventKind.other


class EventPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    all_day: Optional[bool] = None
    deal_id: Optional[str] = None
    kind: Optional[EventKind] = None


def _ok(data):
    return {"ok": True, "data": data}


# --------------- GET /calendar ---------------

@router.get("")
async def list_events(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date:   Optional[str] = Query(None, alias="to"),
    limit: int = Query(200, le=500),
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    # Default range: approx. current month ±7 days
    # start = 1st of month minus 7 days (via day=1 then -7d)
    # end   = 28th of month plus 7 days  (via day=28 then +7d)
    # Intentionally approximate — see CONTRACTS.md §1.2 GET /v1/calendar note
    start = datetime.fromisoformat(from_date) if from_date else now.replace(day=1)  - timedelta(days=7)
    end   = datetime.fromisoformat(to_date)   if to_date   else now.replace(day=28) + timedelta(days=7)
    q = select(CalendarEvent).where(
        CalendarEvent.owner_id == str(user.id),
        CalendarEvent.start_at >= start,
        CalendarEvent.start_at <= end,
    ).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return _ok([r.to_dict() for r in rows])


# --------------- POST /calendar ---------------

@router.post("", status_code=201)
async def create_event(body: EventCreate, db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    ev = CalendarEvent(
        title=body.title,
        description=body.description,
        start_at=body.start_at,
        end_at=body.end_at,
        all_day=body.all_day,
        deal_id=body.deal_id,
        kind=body.kind,
        owner_id=str(user.id),
        owner_name=getattr(user, "name", str(user.id)),
    )
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return _ok(ev.to_dict())


# --------------- PATCH /calendar/:id ---------------

@router.patch("/{event_id}")
async def update_event(
    event_id: str,
    body: EventPatch,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    ev = await db.get(CalendarEvent, event_id)
    if not ev:
        raise NotFoundError("Event not found")
    if ev.owner_id != str(user.id):
        raise ForbiddenError("Not the owner of this event")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(ev, field, val)
    await db.commit()
    await db.refresh(ev)
    return _ok(ev.to_dict())


# --------------- DELETE /calendar/:id ---------------

@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    ev = await db.get(CalendarEvent, event_id)
    if not ev:
        raise NotFoundError("Event not found")
    if ev.owner_id != str(user.id):
        raise ForbiddenError("Not the owner of this event")
    await db.delete(ev)
    await db.commit()
    return Response(status_code=204)
