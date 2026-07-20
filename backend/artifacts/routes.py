from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from backend.common.deps import get_db, get_current_user

from backend.common.errors import NotFoundError
from backend.artifacts.models import Artifact, VALID_KINDS

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("")
async def list_artifacts(
    kind: Optional[str] = Query(None),
    deal_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    q = select(Artifact).order_by(Artifact.created_at.desc()).limit(limit)
    if kind:
        q = q.where(Artifact.kind == kind)
    if deal_id:
        q = q.where(Artifact.deal_id == deal_id)
    rows = (await db.execute(q)).scalars().all()
    return {"ok": True, "data": [r.to_dict() for r in rows]}


@router.post("")
async def create_artifact(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    kind = payload.get("kind", "")
    if kind not in VALID_KINDS:
        return {"ok": False, "error": f"Invalid kind. Allowed: {sorted(VALID_KINDS)}"}
    if not payload.get("title"):
        return {"ok": False, "error": "title required"}
    obj = Artifact(
        kind=kind,
        title=payload["title"],
        url=payload.get("url"),
        deal_id=payload.get("deal_id"),
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return {"ok": True, "data": obj.to_dict()}


@router.patch("/{artifact_id}")
async def update_artifact(
    artifact_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    obj = await db.get(Artifact, artifact_id)
    if not obj:
        raise NotFoundError(f"artifact {artifact_id} not found")
    if "kind" in payload:
        if payload["kind"] not in VALID_KINDS:
            return {"ok": False, "error": f"Invalid kind. Allowed: {sorted(VALID_KINDS)}"}
        obj.kind = payload["kind"]
    for field in ("title", "url", "deal_id"):
        if field in payload:
            setattr(obj, field, payload[field])
    await db.commit()
    await db.refresh(obj)
    return {"ok": True, "data": obj.to_dict()}


@router.delete("/{artifact_id}")
async def delete_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    obj = await db.get(Artifact, artifact_id)
    if not obj:
        raise NotFoundError(f"artifact {artifact_id} not found")
    await db.delete(obj)
    await db.commit()
    return {"ok": True, "data": {"id": artifact_id}}
