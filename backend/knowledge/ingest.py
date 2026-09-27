# backend/knowledge/ingest.py -- §41.1: конвейер документа (идемпотентный)
#
# uploaded -> parsed -> chunked -> indexed -> ready | failed(reason).
# Паттерны Octop (changelog 1.0.2b1/b3):
#   - фолбэк-кодировки: utf-8 -> cp1251, недекодируемое -> failed(encoding);
#   - PDF без текстового слоя -> OCR (rapidocr, extra-зависимость);
#     OCR-отказ «нет изображения» -> failed(no_text), НЕ ready с пустым корпусом;
#   - идемпотентность: повторный запуск по doc_id очищает точки векторного
#     хранилища и строки чанков перед переиндексацией (дублей не остаётся).
#
# Файлы хранятся в ФС: knowledge_files/<doc_id><ext> (см. routes), в БД --
# только статусы и чанки.

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete as sa_delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.knowledge.chunking import chunk_text
from backend.knowledge.models import KnowledgeBase, KnowledgeChunk, KnowledgeDoc


class IngestError(Exception):
    """Ошибка конвейера: reason попадает в fail_reason."""

    def __init__(self, reason: str, message: str = ""):
        super().__init__(message or reason)
        self.reason = reason


# ---------------------------------------------------------------------------
# Извлечение текста (чистые функции -- тестируемы на фикстурах)
# ---------------------------------------------------------------------------

def decode_text(data: bytes) -> tuple[str, str]:
    """UTF-8 -> cp1251 (ру-фолбэк а-ля GB18030 у Octop). Исключение -> encoding."""
    for enc in ("utf-8", "cp1251"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise IngestError("encoding", "недекодируемо ни в utf-8, ни в cp1251")


def extract_txt(data: bytes) -> tuple[str, str]:
    return decode_text(data)


def extract_pdf(data: bytes) -> tuple[str, str]:
    """PDF: pypdf; без текстового слоя -- OCR картинок страниц (rapidocr).
    Картинок нет / OCR недоступен -> IngestError(no_text|ocr_unavailable)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise IngestError("parse", "pypdf не установлен")
    import io

    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    text = "\n".join(parts).strip()
    if len(text) >= 50:
        return text, "utf-8"
    # нет текстового слоя -- пробуем OCR встроенных картинок страниц
    images = []
    for page in reader.pages:
        try:
            for img in page.images:
                images.append(img.data)
        except Exception:
            continue
    if not images:
        # «нет изображения» -- фикс-паттерн Octop: НЕ ready с пустым корпусом
        raise IngestError("no_text", "PDF без текстового слоя и без изображений")
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        raise IngestError("ocr_unavailable", "rapidocr-onnxruntime не установлен")
    ocr = RapidOCR()
    ocr_parts = []
    for img in images[:20]:
        try:
            result, _ = ocr(img)
            if result:
                ocr_parts.extend(line[1] for line in result if line and len(line) > 1)
        except Exception:
            continue
    text = "\n".join(ocr_parts).strip()
    if len(text) < 20:
        raise IngestError("no_text", "OCR не дал текста")
    return text, "utf-8"


def extract_docx(data: bytes) -> tuple[str, str]:
    try:
        import io

        from docx import Document
    except ImportError:
        raise IngestError("parse", "python-docx не установлен")
    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    text = "\n".join(parts).strip()
    if not text:
        raise IngestError("no_text", "docx без текста")
    return text, "utf-8"


def extract_sheet(data: bytes, filename: str) -> tuple[str, str]:
    """xlsx (openpyxl) или csv (stdlib, с фолбэком кодировок)."""
    if filename.lower().endswith(".csv"):
        import csv
        import io

        for enc in ("utf-8-sig", "cp1251"):
            try:
                rows = list(csv.reader(io.StringIO(data.decode(enc))))
                break
            except UnicodeDecodeError:
                continue
        else:
            raise IngestError("encoding", "csv недекодируем")
        lines = [" | ".join(c for c in row if c) for row in rows if row]
        text = "\n".join(lines).strip()
        if not text:
            raise IngestError("no_text", "csv пуст")
        return text, enc
    try:
        import io

        from openpyxl import load_workbook
    except ImportError:
        raise IngestError("parse", "openpyxl не установлен")
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append(" | ".join(cells))
    wb.close()
    text = "\n".join(lines).strip()
    if not text:
        raise IngestError("no_text", "xlsx пуст")
    return text, "utf-8"


def extract_text(filename: str, data: bytes) -> tuple[str, str]:
    """Диспетчер по расширению -> (text, charset). Битый файл -> parse."""
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf"):
            return extract_pdf(data)
        if name.endswith((".docx",)):
            return extract_docx(data)
        if name.endswith((".xlsx", ".csv", ".tsv")):
            return extract_sheet(data, name)
        if name.endswith((".md", ".markdown")):
            text, enc = decode_text(data)
            return text, enc
        if name.endswith((".txt", ".json", ".log")) or "." not in name:
            return extract_txt(data)
        # неизвестное расширение -- пробуем как текст
        return extract_txt(data)
    except IngestError:
        raise
    except Exception as e:
        raise IngestError("parse", f"битый файл: {str(e)[:120]}")


# ---------------------------------------------------------------------------
# Конвейер (транзитивные статусы + corpus_version)
# ---------------------------------------------------------------------------

async def run_pipeline(
    db: AsyncSession,
    doc: KnowledgeDoc,
    data: bytes,
    store=None,
    embedder=None,
) -> KnowledgeDoc:
    """Полный конвейер по doc_id. Идемпотентен: перед индексацией удаляет
    прежние точки и строки чанков документа. corpus_version инкрементируется
    только при успешном изменении корпуса."""
    from backend.knowledge.embedder import get_embedder
    from backend.knowledge.store import get_store

    store = store or get_store()
    embedder = embedder or get_embedder()

    async def _fail(reason: str):
        doc.status = "failed"
        doc.fail_reason = reason
        doc.updated_at = datetime.now(timezone.utc)
        await db.commit()

    # 1) parse
    try:
        text, charset = extract_text(doc.title, data)
    except IngestError as e:
        await _fail(e.reason)
        return doc
    doc.status = "parsed"
    doc.charset = charset
    doc.size_bytes = len(data)
    doc.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # 2) chunk
    chunks = chunk_text(text)
    if not chunks:
        await _fail("empty")
        return doc
    doc.status = "chunked"
    await db.commit()

    # 3) идемпотентная очистка прежней индексации этого doc_id
    # (коллекция создаётся ДО очистки: delete_by_doc по несуществующей
    # коллекции Qdrant возвращает 404)
    store.ensure_collection(embedder.dim())
    await db.execute(sa_delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.id))
    store.delete_by_doc(doc.id)

    # 4) embed + index
    vectors = embedder.embed([c["text"] for c in chunks])
    rows = []
    points = []
    for c, vec in zip(chunks, vectors):
        row = KnowledgeChunk(
            doc_id=doc.id, kb_id=doc.kb_id,
            ord=c["ord"], quote_start=c["start"], quote_end=c["end"],
            text=c["text"],
        )
        db.add(row)
        rows.append(row)
    await db.flush()  # chunk.id для point_id
    for row, vec in zip(rows, vectors):
        # Qdrant принимает только UUID/int ID: детерминированный uuid5 из
        # doc_id/chunk_id (стабилен при переиндексации, валиден для Qdrant)
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"agropilot:doc{doc.id}:c{row.id}"))
        row.qdrant_point_id = point_id
        points.append({
            "id": point_id,
            "vector": vec,
            "payload": {"doc_id": doc.id, "kb_id": doc.kb_id, "chunk_id": row.id,
                        "ord": row.ord},
        })
    store.upsert(points)
    doc.status = "indexed"
    await db.commit()

    # 5) ready + corpus_version (§9.1: инкремент при изменении корпуса)
    kb = await db.get(KnowledgeBase, doc.kb_id)
    if kb is not None:
        kb.corpus_version = (kb.corpus_version or 0) + 1
        kb.indexed_at = datetime.now(timezone.utc)
        cnt = len((await db.execute(
            select(KnowledgeDoc.id).where(
                KnowledgeDoc.kb_id == kb.id, KnowledgeDoc.status == "ready")
        )).scalars().all())
        kb.doc_count = cnt + 1  # сам doc переводится в ready ниже
    doc.status = "ready"
    doc.fail_reason = None
    doc.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return doc
