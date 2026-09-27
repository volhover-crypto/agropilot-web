import os
import re
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from pydantic import BaseModel

from backend.common.deps import get_db, get_current_user
from backend.common.errors import NotFoundError, ValidationError
from backend.artifacts.models import Artifact, ArtifactFolder, VALID_KINDS
from backend.artifacts.template_models import ArtifactTemplate

router = APIRouter(prefix="/artifacts", tags=["artifacts"])

STORAGE_ROOT = "/opt/agropilot-data/artifacts"
MAX_SIZE = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXT = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv",
    "png", "jpg", "jpeg", "gif", "webp", "mp4", "mov", "webm", "zip",
}
_SAFE = re.compile(r"[^A-Za-z0-9А-Яа-яЁё._ -]", re.UNICODE)


def _safe_name(name: str) -> str:
    """Имя файла для диска/ссылки: путь отсечён, небезопасные символы
    заменены; кириллица СОХРАНЯЕТСЯ (иначе «Отчёт.docx» превращался в
    «_______.docx»). Пробелы -> '_' (URL-friendly)."""
    name = os.path.basename((name or "file").replace("\\", "/"))
    name = _SAFE.sub("_", name).strip().replace(" ", "_")
    return name[:200] or "file"


# ---------------------------------------------------------------------------
# Папки файлового менеджера (миграция 040): дерево строит фронт по parent_id
# ---------------------------------------------------------------------------

class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


class FolderPatch(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None


async def _folder_or_404(db: AsyncSession, folder_id: int) -> ArtifactFolder:
    f = await db.get(ArtifactFolder, folder_id)
    if f is None:
        raise NotFoundError(f"folder {folder_id} not found")
    return f


async def _assert_parent_ok(db: AsyncSession, folder: ArtifactFolder, new_parent: Optional[int]):
    """Родитель существует и не образует цикл (папка не может быть внутри
    своей вложенности)."""
    if new_parent is None:
        return
    parent = await db.get(ArtifactFolder, new_parent)
    if parent is None:
        raise ValidationError(f"parent folder {new_parent} not found")
    seen = {folder.id}
    cur = parent
    while cur is not None:
        if cur.id in seen:
            raise ValidationError("нельзя переместить папку внутрь самой себя")
        seen.add(cur.id)
        cur = await db.get(ArtifactFolder, cur.parent_id) if cur.parent_id else None


@router.get("/folders")
async def list_folders(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    rows = (await db.execute(select(ArtifactFolder).order_by(ArtifactFolder.name))).scalars().all()
    return {"ok": True, "data": [r.to_dict() for r in rows]}


@router.post("/folders")
async def create_folder(
    payload: FolderCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    name = (payload.name or "").strip()
    if not name:
        raise ValidationError("name пуст")
    if payload.parent_id is not None:
        await _folder_or_404(db, payload.parent_id)
    f = ArtifactFolder(name=name[:200], parent_id=payload.parent_id)
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return {"ok": True, "data": f.to_dict()}


@router.patch("/folders/{folder_id}")
async def patch_folder(
    folder_id: int,
    payload: FolderPatch,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Переименование (+ смена родителя, не-null). В корень -- POST /move."""
    f = await _folder_or_404(db, folder_id)
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise ValidationError("name пуст")
        f.name = name[:200]
    if payload.parent_id is not None:
        await _assert_parent_ok(db, f, payload.parent_id)
        f.parent_id = payload.parent_id
    await db.commit()
    await db.refresh(f)
    return {"ok": True, "data": f.to_dict()}


class FolderMove(BaseModel):
    parent_id: Optional[int] = None


@router.post("/folders/{folder_id}/move")
async def move_folder(
    folder_id: int,
    payload: FolderMove,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Перемещение папки (parent_id null = корень), с защитой от циклов."""
    f = await _folder_or_404(db, folder_id)
    await _assert_parent_ok(db, f, payload.parent_id)
    f.parent_id = payload.parent_id
    await db.commit()
    await db.refresh(f)
    return {"ok": True, "data": f.to_dict()}


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Удаление папки: подпапки поднимаются в её родителя, файлы --
    в родителя (как проводник: содержимое не удаляется вместе с папкой)."""
    f = await _folder_or_404(db, folder_id)
    parent = f.parent_id
    from sqlalchemy import update as sa_update

    await db.execute(sa_update(ArtifactFolder).where(
        ArtifactFolder.parent_id == folder_id).values(parent_id=parent))
    await db.execute(sa_update(Artifact).where(
        Artifact.folder_id == folder_id).values(folder_id=parent))
    await db.delete(f)
    await db.commit()
    return {"ok": True, "data": {"id": folder_id, "files_moved_to": parent}}


class GenerateBody(BaseModel):
    template_code: str
    deal_id: Optional[str] = None


class TemplateBody(BaseModel):
    code: str
    kind: str
    title_template: str
    body_template: str
    note: Optional[str] = None


@router.get("/templates")
async def list_templates(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    rows = (await db.execute(select(ArtifactTemplate).order_by(ArtifactTemplate.code))).scalars().all()
    return {"ok": True, "data": [r.to_dict() for r in rows]}


@router.post("/templates")
async def upsert_template(
    payload: TemplateBody,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    if payload.kind not in VALID_KINDS:
        raise ValidationError(f"kind должен быть одним из {sorted(VALID_KINDS)}")
    tpl = (await db.execute(select(ArtifactTemplate)
            .where(ArtifactTemplate.code == payload.code))).scalars().first()
    if tpl is None:
        tpl = ArtifactTemplate(code=payload.code, kind=payload.kind,
                               title_template=payload.title_template,
                               body_template=payload.body_template, note=payload.note)
        db.add(tpl)
    else:
        tpl.kind = payload.kind
        tpl.title_template = payload.title_template
        tpl.body_template = payload.body_template
        tpl.note = payload.note
    await db.commit()
    await db.refresh(tpl)
    return {"ok": True, "data": tpl.to_dict()}


@router.post("/generate")
async def generate(
    payload: GenerateBody,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """A5: черновик артефакта по шаблону из карточек сделки/клиента (§27).
    Результат status=draft; отсутствующие переменные — в missing."""
    from backend.artifacts.generate import generate_artifact

    try:
        art, missing = await generate_artifact(db, payload.template_code, payload.deal_id)
    except KeyError as e:
        raise ValidationError(str(e))
    await db.commit()
    await db.refresh(art)
    return {"ok": True, "data": {"artifact": art.to_dict(), "missing": missing}}


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
    folder_id: Optional[int] = Form(None),
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
    if folder_id is not None:
        await _folder_or_404(db, folder_id)

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
        folder_id=folder_id,
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
    if "folder_id" in payload:
        fid = payload["folder_id"]
        if fid is not None:
            await _folder_or_404(db, int(fid))
        obj.folder_id = fid
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
