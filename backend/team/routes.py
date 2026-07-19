# backend/team/routes.py -- AgroPILOT Team router
#
# Mount: app.include_router(team_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/team
# Контракт ответа: {"ok": true, "data": ...} (backend/common/errors.py).
# Stage 2 / Блок E: PATCH /team/{id} (competencies|permissions|status|role_key), isManager().

from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.team.models import TeamMember
from backend.common.errors import NotFoundError, ForbiddenError
from backend.common.deps import get_db, get_current_user

team_router = APIRouter(prefix="/team", tags=["team"])

_MANAGER_ROLE_KEYS = {"manager", "admin"}


def _ok(data):
    return {"ok": True, "data": data}


async def _is_manager(db: AsyncSession, user) -> bool:
    """Enforcement по конвенции проекта: менеджер/админ по role_key текущего юзера."""
    member = await db.get(TeamMember, user.id)
    return bool(member and member.role_key in _MANAGER_ROLE_KEYS)


class TeamPatch(BaseModel):
    competencies: Optional[List[str]] = None
    permissions:  Optional[List[str]] = None
    status:       Optional[str]       = None
    role_key:     Optional[str]       = None


@team_router.get("")
async def list_team(
    limit: int          = Query(100, le=500),
    db:    AsyncSession = Depends(get_db),
    user                = Depends(get_current_user),
):
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


@team_router.patch("/{member_id}")
async def patch_member(
    member_id: str,
    payload:   TeamPatch,
    db:        AsyncSession = Depends(get_db),
    user                    = Depends(get_current_user),
):
    if not await _is_manager(db, user):
        raise ForbiddenError("Manager role required")
    member = await db.get(TeamMember, member_id)
    if not member:
        raise NotFoundError("Team member not found")
    data = payload.model_dump(exclude_unset=True)
    for field in ("competencies", "permissions", "status", "role_key"):
        if field in data and data[field] is not None:
            setattr(member, field, data[field])
    await db.commit()
    await db.refresh(member)
    return _ok(member.to_dict())
