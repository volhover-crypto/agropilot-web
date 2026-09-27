# backend/knowledge/retrieval.py -- §41.3: ретрив чанков по вопросу

import os
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.knowledge.models import KnowledgeChunk, KnowledgeDoc


def min_score() -> float:
    """RETRIEVE_MIN_SCORE: ниже порога чанк не считается «источником»."""
    try:
        return max(0.0, min(1.0, float(os.environ.get("RETRIEVE_MIN_SCORE", "0.30"))))
    except ValueError:
        return 0.30


def validate_citations(answer: str, citations_count: int) -> list[int]:
    """Номера источников [n], реально использованных в ответе (1-based).
    Пусто -> ответ unverified (деградация §41.3)."""
    import re

    used = set()
    for m in re.finditer(r"\[(\d+)\]", answer or ""):
        n = int(m.group(1))
        if 1 <= n <= citations_count:
            used.add(n)
    return sorted(used)


async def retrieve(
    db: AsyncSession,
    question: str,
    kb_ids: Optional[list[int]] = None,
    limit: int = 6,
) -> list[dict]:
    """Векторный поиск чанков -> [{chunk_id, doc_id, doc_title, score, text}].
    Отбираются только чанки готовых (ready) документов."""
    from backend.knowledge.embedder import get_embedder
    from backend.knowledge.store import get_store

    embedder = get_embedder()
    store = get_store()
    vec = embedder.embed([question])[0]
    hits = store.search(vec, limit=limit, kb_ids=kb_ids)
    if not hits:
        return []
    out = []
    for h in hits:
        if h["score"] < min_score():
            continue
        pl = h.get("payload") or {}
        chunk = await db.get(KnowledgeChunk, pl.get("chunk_id"))
        if chunk is None:
            continue
        doc = await db.get(KnowledgeDoc, chunk.doc_id)
        if doc is None or doc.status != "ready":
            continue
        out.append({
            "chunk_id": chunk.id,
            "doc_id": chunk.doc_id,
            "doc_title": doc.title,
            "score": round(float(h["score"]), 4),
            "text": chunk.text,
        })
    return out
