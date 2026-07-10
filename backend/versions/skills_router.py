from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from pydantic import BaseModel

from backend.common.db import get_db
from backend.common.auth import get_current_user
from backend.versions.models import TeamSkill

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillCreate(BaseModel):
    name: str
    level: int = 1
    category: str = ""


class SkillUpdate(BaseModel):
    name: str | None = None
    level: int | None = None
    category: str | None = None


class SkillOut(BaseModel):
    id: int
    name: str
    level: int
    category: str
    owner_id: str

    class Config:
        from_attributes = True


@router.get("/", response_model=List[SkillOut])
async def list_skills(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(TeamSkill).where(TeamSkill.owner_id == str(user.id))
    )
    return result.scalars().all()


@router.post("/", response_model=SkillOut, status_code=201)
async def create_skill(
    payload: SkillCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    skill = TeamSkill(
        name=payload.name,
        level=payload.level,
        category=payload.category,
        owner_id=str(user.id),
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


@router.patch("/{skill_id}", response_model=SkillOut)
async def update_skill(
    skill_id: int,
    payload: SkillUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(TeamSkill).where(
            TeamSkill.id == skill_id,
            TeamSkill.owner_id == str(user.id),
        )
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(skill, field, value)

    await db.commit()
    await db.refresh(skill)
    return skill


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(TeamSkill).where(
            TeamSkill.id == skill_id,
            TeamSkill.owner_id == str(user.id),
        )
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    await db.delete(skill)
    await db.commit()
