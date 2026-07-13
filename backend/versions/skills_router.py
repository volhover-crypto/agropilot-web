# backend/versions/skills_router.py -- AgroPILOT M9 Team Skills router
#
# Mount: app.include_router(skills_router, prefix="/agropilot/api/v1")
# Resulting base path: /agropilot/api/v1/team/skills
#
# Upsert strategy: ON CONFLICT (uq_user_skill) DO UPDATE — атомарно,
# без retry-цикла. Гонка двух параллельных PUT сериализуется PostgreSQL.
#
# Авторизация DELETE/PUT:
#   user_id == current_user.id (вариант A по §2.8 HANDOVER)
#   TODO: add admin role bypass when RBAC is implemented

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.versions.models import TeamSkill
from backend.common.errors import NotFoundError, ForbiddenError
from backend.common.deps import get_db, get_current_user

skills_router = APIRouter(
    prefix="/team/skills",
    tags=["skills"],
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SkillUpsert(BaseModel):
    user_id:   str
    user_name: str
    skill:     str
    level:     Optional[int] = Field(default=3, ge=1, le=5)
    note:      Optional[str] = None


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _ok(data) -> dict:
    return {"ok": True, "data": data}


async def _get_skill_or_404(skill_id: str, db: AsyncSession) -> TeamSkill:
    result = await db.execute(
        select(TeamSkill).where(TeamSkill.id == skill_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise NotFoundError("Skill not found")
    return skill


# ---------------------------------------------------------------------------
# Эндпоинты
# ---------------------------------------------------------------------------

@skills_router.get("")
async def list_skills(
    user_id: Optional[str] = Query(default=None),
    db:      AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """GET /team/skills — список навыков.

    Если передан ?user_id= — фильтрует по нему.
    Любой авторизованный пользователь может читать навыки (§4 контракта).
    """
    stmt = select(TeamSkill)
    if user_id is not None:
        stmt = stmt.where(TeamSkill.user_id == user_id)
    result = await db.execute(stmt)
    skills = result.scalars().all()
    return _ok([s.to_dict() for s in skills])


@skills_router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    db:       AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """GET /team/skills/:id — один навык.

    Любой авторизованный пользователь может читать (§4 контракта).
    """
    skill = await _get_skill_or_404(skill_id, db)
    return _ok(skill.to_dict())


@skills_router.put("")
async def upsert_skill(
    body: SkillUpsert,
    db:   AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """PUT /team/skills — идемпотентный upsert по (user_id, skill).

    ON CONFLICT (uq_user_skill) DO UPDATE — атомарен на уровне БД,
    без retry. Два параллельных PUT для одного (user_id, skill)
    сериализуются PostgreSQL; last-writer-wins по level/note/updated_at.

    Примечание: 'id' в values() используется только на пути INSERT.
    При конфликте существующий PK сохраняется (id не входит в set_).

    # TODO: add admin role bypass when RBAC is implemented
    """
    # Авторизация: только сам пользователь может upsert свои навыки (вариант A)
    if body.user_id != str(user.id):
        raise ForbiddenError("Cannot upsert skills for another user")

    effective_level = body.level if body.level is not None else 3

    stmt = (
        pg_insert(TeamSkill)
        .values(
            id=str(uuid.uuid4()),       # используется только на INSERT
            user_id=body.user_id,
            user_name=body.user_name,
            skill=body.skill,
            level=effective_level,
            note=body.note,
        )
        .on_conflict_do_update(
            constraint="uq_user_skill",  # точечно по имени constraint
            set_={
                "user_name":  body.user_name,   # имя могло измениться
                "level":      effective_level,
                "note":       body.note,
                "updated_at": func.now(),        # серверное время, не excluded
            },
        )
        .returning(TeamSkill)
    )
    result = await db.execute(stmt)
    skill  = result.scalar_one()
    await db.commit()
    await db.refresh(skill)   # чтобы updated_at не был None
    return _ok(skill.to_dict())


@skills_router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    db:       AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """DELETE /team/skills/:id — удалить навык.

    Авторизация: только владелец (user_id == current_user.id).
    # TODO: add admin role bypass when RBAC is implemented
    """
    skill = await _get_skill_or_404(skill_id, db)

    if skill.user_id != str(user.id):
        raise ForbiddenError("Cannot delete another user's skill")

    await db.delete(skill)
    await db.commit()
    # 204 No Content — тело не возвращается
