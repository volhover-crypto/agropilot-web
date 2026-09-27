# backend/knowledge/routes.py -- §41.2: управление базами знаний (M11, О1)
#
# Mount: app.include_router(knowledge_router, prefix="/agropilot/api/v1")
#   GET  /v1/knowledge                     — список KB (corpus_version)
#   POST /v1/knowledge {title}             — создать KB (менеджер)
#   GET  /v1/knowledge/{id}/docs           — документы конвейера
#   POST /v1/knowledge/{id}/docs           — загрузка {filename, content_b64}
#   POST /v1/knowledge/{id}/docs/{doc_id}/reindex — повтор конвейера
#   GET  /v1/knowledge/{id}/chunks/{chunk_id}     — чанк для подсветки цитаты
#
# Файлы документов: knowledge_files/<doc_id>__<safe-name> (ФС рядом с BFF);
# повторная загрузка того же имени = новый документ (версионирование M7).

import base64
import os
import re
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.deps import get_db, get_current_user
from backend.common.errors import NotFoundError, ValidationError
from backend.knowledge.models import KnowledgeBase, KnowledgeChunk, KnowledgeDoc
from backend.team.models import TeamMember

knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_MANAGER_ROLE_KEYS = {"manager", "admin"}
_FILES_DIR = os.environ.get("KNOWLEDGE_FILES_DIR", "knowledge_files")

VALID_DOC_STATUS = ("uploaded", "parsed", "chunked", "indexed", "ready", "failed")


def _ok(data):
    return {"ok": True, "data": data}


async def _is_manager(db: AsyncSession, user) -> bool:
    member = await db.get(TeamMember, user.id)
    return bool(member and member.role_key in _MANAGER_ROLE_KEYS)


def _safe_name(filename: str) -> str:
    base = os.path.basename(filename or "doc.txt")
    return re.sub(r"[^A-Za-z0-9А-Яа-яЁё._-]", "_", base)[:120] or "doc.txt"


def doc_path(doc_id: int, filename: str) -> str:
    return os.path.join(_FILES_DIR, f"{doc_id}__{_safe_name(filename)}")


@knowledge_router.get("")
async def list_kbs(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    rows = (await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.status == "active")
        .order_by(KnowledgeBase.id))).scalars().all()
    return _ok([r.to_dict() for r in rows])


class KBCreate(BaseModel):
    title: str


@knowledge_router.post("")
async def create_kb(
    body: KBCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    if not body.title or not body.title.strip():
        raise ValidationError("title пуст")
    if not await _is_manager(db, user):
        raise ValidationError("создание баз знаний — менеджеры/админ")
    kb = KnowledgeBase(title=body.title.strip()[:200], verified_by=str(user.id))
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return _ok(kb.to_dict())


@knowledge_router.get("/{kb_id}/docs")
async def list_docs(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    rows = (await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.kb_id == kb_id)
        .order_by(KnowledgeDoc.id.desc()))).scalars().all()
    return _ok([r.to_dict() for r in rows])


class DocUpload(BaseModel):
    filename: str
    content_b64: str


@knowledge_router.post("/{kb_id}/docs")
async def upload_doc(
    kb_id: int,
    body: DocUpload,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Загрузка документа (base64) + запуск конвейера. Синхронно: файлы MVP
    небольшие; тяжёлые PDF/OCR уводить в reindex-повтор при таймаутах."""
    from backend.knowledge.ingest import run_pipeline

    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundError(f"knowledge base {kb_id} не найдена")
    if not await _is_manager(db, user):
        raise ValidationError("загрузка в базы знаний — менеджеры/админ")
    try:
        data = base64.b64decode(body.content_b64, validate=True)
    except Exception:
        raise ValidationError("content_b64 не является валидным base64")
    if not data:
        raise ValidationError("пустой файл")
    if len(data) > 25 * 1024 * 1024:
        raise ValidationError("файл больше 25 МБ — разбейте на части")

    doc = KnowledgeDoc(kb_id=kb_id, title=_safe_name(body.filename))
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    os.makedirs(_FILES_DIR, exist_ok=True)
    with open(doc_path(doc.id, body.filename), "wb") as f:
        f.write(data)

    doc = await run_pipeline(db, doc, data)
    return _ok(doc.to_dict())


@knowledge_router.post("/{kb_id}/docs/{doc_id}/reindex")
async def reindex_doc(
    kb_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Повтор конвейера по сохранённому файлу (идемпотентен: дедуб точек)."""
    from backend.knowledge.ingest import run_pipeline

    if not await _is_manager(db, user):
        raise ValidationError("переиндексация — менеджеры/админ")
    doc = await db.get(KnowledgeDoc, doc_id)
    if doc is None or doc.kb_id != kb_id:
        raise NotFoundError(f"doc {doc_id} в kb {kb_id} не найден")
    path = next(
        (os.path.join(_FILES_DIR, f) for f in sorted(os.listdir(_FILES_DIR))
         if f.startswith(f"{doc_id}__")),
        None,
    ) if os.path.isdir(_FILES_DIR) else None
    if path is None or not os.path.isfile(path):
        raise NotFoundError(f"файл документа {doc_id} не найден на диске")
    with open(path, "rb") as f:
        data = f.read()
    doc = await run_pipeline(db, doc, data)
    return _ok(doc.to_dict())


@knowledge_router.get("/chunks/{chunk_id}")
async def get_chunk(
    chunk_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Чанк для клика doc -> chunk -> подсветка quote: текст + диапазон."""
    chunk = await db.get(KnowledgeChunk, chunk_id)
    if chunk is None:
        raise NotFoundError(f"chunk {chunk_id} не найден")
    doc = await db.get(KnowledgeDoc, chunk.doc_id)
    return _ok({
        "id": chunk.id,
        "kb_id": chunk.kb_id,
        "doc_id": chunk.doc_id,
        "doc_title": doc.title if doc else None,
        "doc_status": doc.status if doc else None,
        "ord": chunk.ord,
        "quote_start": chunk.quote_start,
        "quote_end": chunk.quote_end,
        "text": chunk.text,
    })


class KBQuery(BaseModel):
    question: str


@knowledge_router.post("/{kb_id}/query")
async def query_kb(
    kb_id: int,
    body: KBQuery,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """§9.2: ответ ОБЯЗАН содержать citations[] (пустой -- значит ответ
    unverified: знаний по вопросу в корпусе нет)."""
    from backend.orchestrator.routes import orchestrator_chat

    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundError(f"knowledge base {kb_id} не найдена")
    result = await orchestrator_chat(db, user, body.question, kb_id=kb_id)
    return _ok(result)
