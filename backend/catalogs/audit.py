# backend/catalogs/audit.py -- §45: журнал изменений НСИ (diff «кто/что/когда»)
#
# Пишется движком в той же транзакции, что и мутация (модель Frappe Version):
# create/update/archive/restore/delete + diff {поле: {old, new}}.
# Журнал append-only: откат = новая мутация со старыми значениями, строки не трогаем.

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from backend.catalogs.models import CatalogAuditEntry


def _jsonable(v):
    """Decimal/datetime → JSON-типы (json.dumps их не серриализует)."""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


async def write_audit(db, entity: str, entity_id: int, action: str,
                      diff: dict, user) -> None:
    entry = CatalogAuditEntry(
        entity=entity,
        entity_id=int(entity_id),
        action=action,
        diff=_jsonable(diff or {}),
        user_id=getattr(user, "id", None),
        user_name=getattr(user, "name", None),
    )
    db.add(entry)
    await db.flush()


def _iso(v) -> str | None:
    return v.isoformat() if hasattr(v, "isoformat") else v


async def read_history(db, entity: str, entity_id: int, limit: int = 100) -> dict:
    rows = (await db.execute(
        select(CatalogAuditEntry)
        .where(CatalogAuditEntry.entity == entity,
               CatalogAuditEntry.entity_id == int(entity_id))
        .order_by(CatalogAuditEntry.id.desc())
        .limit(limit)
    )).scalars().all()
    return {"items": [{
        "id": r.id,
        "action": r.action,
        "diff": r.diff or {},
        "user_id": r.user_id,
        "user_name": r.user_name,
        "created_at": _iso(r.created_at),
    } for r in rows]}
