# backend/skills/routes.py -- AgroPILOT M9 Team Skills router
# Mount: app.include_router(router, prefix="/agropilot/api/v1")
# Resulting base path: /agropilot/api/v1/team/skills
#
# Upsert strategy: ON CONFLICT (uq_team_skill) DO UPDATE
# This avoids retry loops and is safe under concurrent requests.
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from backend.versions.models import TeamSkill
from backend.common.errors import NotFoundError, ForbiddenError

router = APIRouter(prefix="/team/skills", tags=["skills"])


# --------------- Pydantic schemas ---------------

class SkillUpsert(BaseModel):
    skill_name: str
    level: int = Field(default=1, ge=1, le=5)
    notes: Optional[str] = None


def _ok(data):
    return {"ok": True, "data": data}


# --------------- GET /team/skills ---------------

@router.get("")
async def list_skills(
    user_id: Optional[str] = Query(None, description="Filter by user_id (default: current user)"),
    db: AsyncSession = Depends(),
    user=Depends(),
):
    """List skills. Without user_id param returns skills of the current user."""
    target_uid = user_id or str(user.id)
    rows = (
        await db.execute(
            select(TeamSkill)
            .where(TeamSkill.user_id == target_uid)
            .order_by(TeamSkill.skill_name)
        )
    ).scalars().all()
    return _ok([r.to_dict() for r in rows])


# --------------- GET /team/skills/{skill_id} ---------------

@router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    db: AsyncSession = Depends(),
    user=Depends(),
):
    skill = await db.get(TeamSkill, skill_id)
    if not skill:
        raise NotFoundError("Skill not found")
    return _ok(skill.to_dict())


# --------------- PUT /team/skills ---------------
# Upsert: insert or update level+notes on conflict (user_id, skill_name)

@router.put("", status_code=200)
async def upsert_skill(
    body: SkillUpsert,
    db: AsyncSession = Depends(),
    user=Depends(),
):
    """Create or update a skill for the current user.

    Uses PostgreSQL ON CONFLICT (uq_team_skill) DO UPDATE so concurrent
    requests never collide — no retry loop needed.
    Returns the upserted row.
    """
    import uuid as _uuid
    stmt = (
        pg_insert(TeamSkill)
        .values(
            id=str(_uuid.uuid4()),
            user_id=str(user.id),
            user_name=getattr(user, "name", str(user.id)),
            skill_name=body.skill_name,
            level=body.level,
            notes=body.notes,
        )
        .on_conflict_do_update(
            constraint="uq_team_skill",
            set_={
                "level": body.level,
                "notes": body.notes,
                "updated_at": text("now()"),
            },
        )
        .returning(TeamSkill)
    )
    result = await db.execute(stmt)
    await db.commit()
    row = result.scalars().one()
    return _ok(row.to_dict())


# --------------- DELETE /team/skills/{skill_id} ---------------

@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    db: AsyncSession = Depends(),
    user=Depends(),
):
    """Delete a skill.
    Only the owner (user_id == current user) may delete their skill.
    # TODO: add admin role bypass when RBAC is implemented.
    """
    skill = await db.get(TeamSkill, skill_id)
    if not skill:
        raise NotFoundError("Skill not found")
    if skill.user_id != str(user.id):
        raise ForbiddenError("Not the owner of this skill")
    await db.delete(skill)
    await db.commit()
    return Response(status_code=204)
