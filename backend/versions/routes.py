# backend/versions/routes.py -- AgroPILOT M9 Deal Versions router
# Mount: app.include_router(router, prefix="/agropilot/api/v1")
# Resulting base path: /agropilot/api/v1/deals/{deal_id}/versions
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from .models import DealVersion
from backend.common.errors import NotFoundError, ForbiddenError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deals", tags=["versions"])

_MAX_VERSION_RETRIES = 3
_UQ_DEAL_VERSION = "uq_deal_version"


# --------------- Pydantic schemas ---------------

class VersionCreate(BaseModel):
    title: str
    description: Optional[str] = None


def _ok(data):
    return {"ok": True, "data": data}


# --------------- helpers ---------------

async def _next_version_number(db: AsyncSession, deal_id: str) -> int:
    """Return MAX(version_number) + 1 for the given deal, or 1 if no versions yet."""
    result = await db.execute(
        select(sqlfunc.max(DealVersion.version_number)).where(
            DealVersion.deal_id == deal_id
        )
    )
    current_max = result.scalar()
    return (current_max or 0) + 1


async def _create_version(
    db: AsyncSession,
    deal_id: str,
    body: VersionCreate,
    user_id: str,
) -> DealVersion:
    """Insert a new DealVersion, retrying up to _MAX_VERSION_RETRIES times
    if uq_deal_version fires (concurrent insert race).
    Any other IntegrityError is re-raised immediately.
    """
    for attempt in range(1, _MAX_VERSION_RETRIES + 1):
        version_number = await _next_version_number(db, deal_id)
        version = DealVersion(
            deal_id=deal_id,
            version_number=version_number,
            title=body.title,
            description=body.description,
            created_by=user_id,
        )
        try:
            db.add(version)
            await db.flush()   # raises IntegrityError if conflict
            await db.commit()
            return version
        except IntegrityError as exc:
            await db.rollback()
            # Detect constraint by name; fall back to string check
            constraint = getattr(
                getattr(exc.orig, "diag", None), "constraint_name", None
            ) or ""
            if _UQ_DEAL_VERSION not in constraint:
                # pgcode path: check sqlstate 23505 + message
                orig_str = str(exc.orig).lower()
                if _UQ_DEAL_VERSION not in orig_str:
                    logger.error(
                        "Non-version IntegrityError on deal %s: %s", deal_id, exc
                    )
                    raise  # unrelated constraint violation
            logger.warning(
                "uq_deal_version conflict on deal=%s attempt=%d/%d — retrying",
                deal_id, attempt, _MAX_VERSION_RETRIES,
            )
    # Exhausted retries
    raise RuntimeError(
        f"Could not create version for deal {deal_id} after {_MAX_VERSION_RETRIES} retries"
    )


# --------------- GET /deals/{deal_id}/versions ---------------

@router.get("/{deal_id}/versions")
async def list_versions(
    deal_id: str,
    db: AsyncSession = Depends(),
    user=Depends(),
):
    rows = (
        await db.execute(
            select(DealVersion)
            .where(DealVersion.deal_id == deal_id)
            .order_by(DealVersion.version_number)
        )
    ).scalars().all()
    return _ok([r.to_dict() for r in rows])


# --------------- POST /deals/{deal_id}/versions ---------------

@router.post("/{deal_id}/versions", status_code=201)
async def create_version(
    deal_id: str,
    body: VersionCreate,
    db: AsyncSession = Depends(),
    user=Depends(),
):
    version = await _create_version(db, deal_id, body, str(user.id))
    return _ok(version.to_dict())


# --------------- GET /deals/{deal_id}/versions/{version_id} ---------------

@router.get("/{deal_id}/versions/{version_id}")
async def get_version(
    deal_id: str,
    version_id: str,
    db: AsyncSession = Depends(),
    user=Depends(),
):
    v = await db.get(DealVersion, version_id)
    if not v or v.deal_id != deal_id:
        raise NotFoundError("Version not found")
    return _ok(v.to_dict())


# --------------- DELETE /deals/{deal_id}/versions/{version_id} ---------------

@router.delete("/{deal_id}/versions/{version_id}", status_code=204)
async def delete_version(
    deal_id: str,
    version_id: str,
    db: AsyncSession = Depends(),
    user=Depends(),
):
    v = await db.get(DealVersion, version_id)
    if not v or v.deal_id != deal_id:
        raise NotFoundError("Version not found")
    if v.created_by != str(user.id):
        raise ForbiddenError("Not the creator of this version")
    await db.delete(v)
    await db.commit()
    return Response(status_code=204)
