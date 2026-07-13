# backend/versions/deals_versions_router.py -- AgroPILOT M9 Deal Versions router
#
# Mount: app.include_router(deals_versions_router, prefix="/agropilot/api/v1")
# Resulting base path: /agropilot/api/v1/deals/{deal_id}/versions
#
# Retry-логика version_num:
#   SELECT MAX+1 → INSERT под UNIQUE constraint uq_deal_version
#   При конфликте ИМЕННО uq_deal_version — retry (до MAX_RETRIES).
#   Любой другой IntegrityError — rollback + re-raise без обёртки.

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.versions.models import DealVersion
from backend.common.errors import NotFoundError, ConflictError
from backend.common.deps import get_db, get_current_user

logger = logging.getLogger(__name__)

deals_versions_router = APIRouter(
    prefix="/deals",
    tags=["versions"],
)

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

MAX_RETRIES      = 3
_UQ_DEAL_VERSION = "uq_deal_version"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class VersionCreate(BaseModel):
    comment:  Optional[str]  = None
    snapshot: Optional[dict] = None


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _ok(data) -> dict:
    return {"ok": True, "data": data}


def _is_version_num_conflict(exc: IntegrityError) -> bool:
    """True только если IntegrityError вызван constraint uq_deal_version."""
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False
    diag = getattr(orig, "diag", None)
    if diag is not None:
        constraint = getattr(diag, "constraint_name", None)
        if constraint:
            return constraint == _UQ_DEAL_VERSION
    return _UQ_DEAL_VERSION in str(orig).lower()


async def create_version(
    deal_id:     str,
    comment:     Optional[str],
    snapshot:    dict,
    author_id:   str,
    author_name: str,
    db:          AsyncSession,
) -> DealVersion:
    """Create a new deal version with race condition protection.

    UNIQUE(deal_id, version_num) guards against parallel inserts.
    Retries only on uq_deal_version conflicts (up to MAX_RETRIES).
    Any other IntegrityError is rolled back and re-raised as-is.
    """
    for attempt in range(MAX_RETRIES):
        result = await db.execute(
            select(func.max(DealVersion.version_num))
            .where(DealVersion.deal_id == deal_id)
        )
        current_max = result.scalar() or 0
        version_num = current_max + 1

        version = DealVersion(
            deal_id=deal_id,
            version_num=version_num,
            snapshot=snapshot,
            comment=comment,
            author_id=author_id,
            author_name=author_name,
        )
        try:
            db.add(version)
            await db.flush()
            await db.commit()
            await db.refresh(version)
            return version
        except IntegrityError as exc:
            await db.rollback()
            if not _is_version_num_conflict(exc):
                raise
            logger.warning(
                "version_num conflict on deal_id=%s (num=%s), retry %s/%s",
                deal_id, version_num, attempt + 1, MAX_RETRIES,
            )

    raise ConflictError("Could not allocate version_num after retries")


# ---------------------------------------------------------------------------
# Эндпоинты
# ---------------------------------------------------------------------------

@deals_versions_router.get("/{deal_id}/versions")
async def list_versions(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """GET /deals/:deal_id/versions"""
    result = await db.execute(
        select(DealVersion)
        .where(DealVersion.deal_id == deal_id)
        .order_by(DealVersion.version_num.desc())
    )
    versions = result.scalars().all()
    return _ok([v.to_dict() for v in versions])


@deals_versions_router.post("/{deal_id}/versions", status_code=201)
async def post_version(
    deal_id: str,
    body:    VersionCreate,
    db:      AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """POST /deals/:deal_id/versions"""
    snapshot = body.snapshot or {}
    version = await create_version(
        deal_id=deal_id,
        comment=body.comment,
        snapshot=snapshot,
        author_id=str(user.id),
        author_name=getattr(user, "name", str(user.id)),
        db=db,
    )
    return _ok(version.to_dict())


@deals_versions_router.get("/{deal_id}/versions/{version_num}")
async def get_version(
    deal_id:     str,
    version_num: int,
    db:          AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """GET /deals/:deal_id/versions/:version_num

    WHERE (deal_id + version_num) — защита от подмены deal_id.
    """
    result = await db.execute(
        select(DealVersion).where(
            DealVersion.deal_id     == deal_id,
            DealVersion.version_num == version_num,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise NotFoundError("Version not found")
    return _ok(version.to_dict())


@deals_versions_router.post("/{deal_id}/versions/{version_num}/restore")
async def restore_version(
    deal_id:     str,
    version_num: int,
    db:          AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """POST /deals/:deal_id/versions/:version_num/restore

    Восстанавливает безопасные поля сделки из snapshot.
    НЕ перезаписывает: id, client_id, owner_id, created_at.
    Автосоздаёт новую версию через create_version().
    WHERE (deal_id + version_num) — защита от подмены deal_id.
    """
    result = await db.execute(
        select(DealVersion).where(
            DealVersion.deal_id     == deal_id,
            DealVersion.version_num == version_num,
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise NotFoundError("Version not found")

    SAFE_FIELDS = {"title", "stage", "amount", "description",
                   "need_type", "culture", "region"}
    restore_snapshot = {
        k: v for k, v in (source.snapshot or {}).items()
        if k in SAFE_FIELDS
    }

    new_version = await create_version(
        deal_id=deal_id,
        comment=f"Restored from v{version_num}",
        snapshot=restore_snapshot,
        author_id=str(user.id),
        author_name=getattr(user, "name", str(user.id)),
        db=db,
    )

    return _ok({
        "deal":        None,  # TODO: вернуть реальный Deal после интеграции
        "new_version": new_version.to_dict(),
    })
