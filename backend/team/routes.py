# backend/team/routes.py -- AgroPILOT Team router
#
# Mount: app.include_router(team_router, prefix="/agropilot/api/v1")
# Resulting base path: /agropilot/api/v1/team
#
# Read-only on Stage 1: список команды + одна карточка.
# Контракт ответа: {"ok": true, "data": ...} (backend/common/errors.py).

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.team.models import TeamMember
from backend.common.errors import NotFoundError
from backend.common.deps import get_db, get_current_user

team_router = APIRouter(prefix="/team", tags=["team"])


def _ok(data):
    return {"ok": True, "data": data}


@team_router.get("")
async def list_team(
    limit: int          = Query(100, le=500),
    db:    AsyncSession = Depends(get_db),
    user                = Depends(get_current_user),
):
    """Вся команда (U1–U5). Без фильтров на Этапе 1."""
    q = select(TeamMember).order_by(TeamMember.id).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return _ok([r.to_dict() for r in rows])


@team_router.get("/{member_id}")
async def get_member(
    member_id: str,
    db:        AsyncSession = Depends(get_db),
    user                    = Depends(get_current_user),
):
    member = await db.get(TeamMember, member_id)
    if not member:
        raise NotFoundError("Team member not found")
    return _ok(member.to_dict())
