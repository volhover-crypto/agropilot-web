# backend/knowledge/store.py -- §41.1: векторное хранилище
#
# QDRANT_URL задан -> QdrantStore (qdrant-client, ленивый импорт;
# коллекция agropilot_kb, создаётся при первом использовании).
# Не задан -> MemoryStore (чистый python, cosine) -- разработка/тесты.
# Точка: id = "doc{doc_id}:c{chunk_db_id}", payload = {doc_id, kb_id,
# chunk_id, ord, quote}. Идемпотентность переиндексации -- delete_by_doc
# перед upsert (вызывает ingest).

import math
import os
from typing import Optional

_COLLECTION = "agropilot_kb"


class MemoryStore:
    """Псевдовекторное хранилище для разработки/тестов (cosine)."""

    def __init__(self):
        self._points: dict[str, tuple[list[float], dict]] = {}

    def ensure_collection(self, dim: int) -> None:
        pass

    def upsert(self, points: list[dict]) -> None:
        for p in points:
            self._points[str(p["id"])] = (p["vector"], dict(p.get("payload") or {}))

    def delete_by_doc(self, doc_id: int) -> int:
        gone = [k for k, (_, pl) in self._points.items() if pl.get("doc_id") == doc_id]
        for k in gone:
            del self._points[k]
        return len(gone)

    def search(self, vector: list[float], limit: int = 5,
               kb_ids: Optional[list[int]] = None) -> list[dict]:
        qn = math.sqrt(sum(x * x for x in vector)) or 1.0
        scored = []
        for pid, (vec, pl) in self._points.items():
            if kb_ids and pl.get("kb_id") not in kb_ids:
                continue
            vn = math.sqrt(sum(x * x for x in vec)) or 1.0
            dot = sum(a * b for a, b in zip(vector, vec))
            scored.append({"id": pid, "score": dot / (qn * vn), "payload": pl})
        scored.sort(key=lambda r: -r["score"])
        return scored[:limit]


class QdrantStore:
    """Прод-хранилище. QDRANT_URL, напр. http://127.0.0.1:6333."""

    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self._client = None

    def _get(self):
        if self._client is None:
            from qdrant_client import QdrantClient  # лениво

            self._client = QdrantClient(url=self.url, timeout=10)
        return self._client

    def ensure_collection(self, dim: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        client = self._get()
        if not client.collection_exists(_COLLECTION):
            client.create_collection(
                collection_name=_COLLECTION,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    def upsert(self, points: list[dict]) -> None:
        from qdrant_client.models import PointStruct

        def _pid(p):
            # Qdrant: только UUID/int; произвольная строка -> детерминированный uuid5
            pid = str(p["id"])
            try:
                import uuid as _uuid

                _uuid.UUID(pid)
                return pid
            except (ValueError, AttributeError):
                import uuid as _uuid

                return str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"agropilot:{pid}"))

        self._get().upsert(
            collection_name=_COLLECTION,
            points=[
                PointStruct(
                    id=_pid(p), vector=p["vector"],
                    payload=dict(p.get("payload") or {}),
                )
                for p in points
            ],
        )

    def delete_by_doc(self, doc_id: int) -> int:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        try:
            res = self._get().delete(
                collection_name=_COLLECTION,
                points_selector=Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
                ),
                wait=True,
            )
            return 1 if getattr(res, "status", None) else 0
        except Exception as e:
            # коллекции ещё нет -- нечего удалять (идемпотентность)
            if "404" in str(e) or "doesn't exist" in str(e) or "Not found" in str(e):
                return 0
            raise

    def search(self, vector: list[float], limit: int = 5,
               kb_ids: Optional[list[int]] = None) -> list[dict]:
        from qdrant_client.models import FieldCondition, Filter, MatchAny

        flt = None
        if kb_ids:
            flt = Filter(must=[FieldCondition(key="kb_id", match=MatchAny(any=kb_ids))])
        hits = self._get().query_points(
            collection_name=_COLLECTION, query=vector, limit=limit, query_filter=flt
        ).points
        return [{"id": str(h.id), "score": float(h.score), "payload": dict(h.payload or {})}
                for h in hits]


def get_store():
    url = os.environ.get("QDRANT_URL", "").strip()
    if url:
        return QdrantStore(url)
    return MemoryStore()
