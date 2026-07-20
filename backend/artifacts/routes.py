import os
import re
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from backend.common.deps import get_db, get_current_user
from backend.common.errors import NotFoundError
from backend.artifacts.models import Artifact, VALID_KINDS

router = APIRouter(prefix="/artifacts", tags=["artifacts"])

STORAGE_ROOT = "/opt/agropilot-data/artifacts"
MAX_SIZE = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXT = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv",
    "png", "jpg", "jpeg", "gif", "webp", "mp4", "mov", "webm", "zip",
}
_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_name(name: str) -> str:
    name = os.path.basename(name or "file")
    return _SAFE.sub("_", name)[:200] or "file"


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
        type=payload.get("type"),
        status=payload.get("status"),
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return {"ok": True, "data": obj.to_dict()}


@router.post("/upload")
async def upload_artifact(
    file: UploadFile = File(...),
    kind: str = Form("other"),
    title: str = Form(""),
    deal_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    if kind not in VALID_KINDS:
        return {"ok": False, "error": f"Invalid kind. Allowed: {sorted(VALID_KINDS)}"}

    orig = _safe_name(file.filename)
    ext = orig.rsplit(".", 1)[-1].lower() if "." in orig else ""
    if ext not in ALLOWED_EXT:
        return {"ok": False, "error": f"Extension .{ext} not allowed. Allowed: {sorted(ALLOWED_EXT)}"}

    data = await file.read()
    if len(data) > MAX_SIZE:
        return {"ok": False, "error": f"File too large ({len(data)} bytes). Max {MAX_SIZE}."}
    if len(data) == 0:
        return {"ok": False, "error": "empty file"}

    obj = Artifact(
        kind=kind,
        title=title or orig,
        deal_id=deal_id,
        filename=orig,
        ext=ext,
        mime=file.content_type,
        size=len(data),
        type="file",
        status="final",
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)

    dest_dir = os.path.join(STORAGE_ROOT, str(obj.id))
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, orig)
    with open(dest_path, "wb") as f:
        f.write(data)

    obj.blob_uri = f"/agropilot/files/{obj.id}/{orig}"
    await db.commit()
    await db.refresh(obj)
    return {"ok": True, "data": obj.to_dict()}


@router.get("/{artifact_id}/download")
async def download_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    obj = await db.get(Artifact, artifact_id)
    if not obj or not obj.filename:
        raise NotFoundError(f"artifact file {artifact_id} not found")
    path = os.path.join(STORAGE_ROOT, str(obj.id), obj.filename)
    if not os.path.isfile(path):
        raise NotFoundError(f"file missing on disk for artifact {artifact_id}")
    return FileResponse(path, filename=obj.filename, media_type=obj.mime or "application/octet-stream")


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
    for field in ("title", "url", "deal_id", "type", "status"):
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
    fdir = os.path.join(STORAGE_ROOT, str(artifact_id))
    await db.delete(obj)
    await db.commit()
    try:
        if os.path.isdir(fdir):
            for fn in os.listdir(fdir):
                os.remove(os.path.join(fdir, fn))
            os.rmdir(fdir)
    except OSError:
        pass
    return {"ok": True, "data": {"id": artifact_id}}
