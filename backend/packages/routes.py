# backend/packages/routes.py -- AgroPILOT Packages router
#
# Mount: app.include_router(packages_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/packages
# Контракт: {"ok": true, "data": ...} M10-4

from typing import Optional
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.packages.models import Package
from backend.common.errors import NotFoundError
from backend.common.deps import get_db, get_current_user

packages_router = APIRouter(prefix="/packages", tags=["packages"])

VALID_STATUSES = {"draft", "active", "archived"}

def _ok(data):
    return {"ok": True, "data": data}


class PackageCreate(BaseModel):
    title:       str
    description: Optional[str]   = None
    price:       Optional[float] = None
    status:      Optional[str]   = "draft"
    deal_id:     Optional[str]   = None


class PackagePatch(BaseModel):
    title:       Optional[str]   = None
    description: Optional[str]   = None
    price:       Optional[float] = None
    status:      Optional[str]   = None
    deal_id:     Optional[str]   = None


@packages_router.get("")
async def list_packages(
    status:  Optional[str] = Query(None),
    deal_id: Optional[str] = Query(None),
    limit:   int           = Query(100, le=500),
    db:      AsyncSession  = Depends(get_db),
    user                   = Depends(get_current_user),
):
    q = select(Package).order_by(Package.created_at.desc())
    if status:
        q = q.where(Package.status == status)
    if deal_id:
        q = q.where(Package.deal_id == deal_id)
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return _ok([r.to_dict() for r in rows])


@packages_router.post("")
async def create_package(
    payload: PackageCreate,
    db:      AsyncSession = Depends(get_db),
    user                  = Depends(get_current_user),
):
    if payload.status and payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(VALID_STATUSES)}")
    item = Package(
        title       = payload.title,
        description = payload.description,
        price       = payload.price,
        status      = payload.status or "draft",
        deal_id     = payload.deal_id,
        created_at  = datetime.now(timezone.utc),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@packages_router.patch("/{package_id}")
async def patch_package(
    package_id: int,
    payload:    PackagePatch,
    db:         AsyncSession = Depends(get_db),
    user                     = Depends(get_current_user),
):
    item = await db.get(Package, package_id)
    if not item:
        raise NotFoundError("Package not found")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(VALID_STATUSES)}")
    for field, val in data.items():
        setattr(item, field, val)
    await db.commit()
    await db.refresh(item)
    return _ok(item.to_dict())


@packages_router.delete("/{package_id}")
async def delete_package(
    package_id: int,
    db:         AsyncSession = Depends(get_db),
    user                     = Depends(get_current_user),
):
    item = await db.get(Package, package_id)
    if not item:
        raise NotFoundError("Package not found")
    await db.delete(item)
    await db.commit()
    return _ok({"deleted": package_id})
