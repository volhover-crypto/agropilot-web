# backend/catalogs/routes.py -- §45: справочники НСИ, единые эндпоинты
#
# Mount: app.include_router(router, prefix="/agropilot/api/v1")
# GET/POST /v1/catalogs, /v1/catalogs/{type}[/...] — см. CONTRACTS.md §45.
# Права: чтение и мутации — любой авторизованный; DELETE — admin/manager
# (решение 2026-09-28). Роли берутся из team.role_key (токен ролей не несёт).

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.catalogs import engine
from backend.common.deps import get_current_user, get_db

router = APIRouter(prefix="/catalogs", tags=["catalogs"])


def _ok(data):
    return {"ok": True, "data": data}


@router.get("")
async def list_catalog_types(user=Depends(get_current_user)):
    """Реестр типов справочников + схема полей — фронт строит UI из этого."""
    return _ok(engine.specs_payload())


# ВАЖНО: /{key}/duplicates объявляется ДО /{key}/{item_id}, иначе FastAPI
# сматчит "duplicates" как item_id.
@router.get("/{key}/duplicates")
async def find_duplicates(key: str, q: str = Query(..., min_length=2),
                          db: AsyncSession = Depends(get_db),
                          user=Depends(get_current_user)):
    return _ok(await engine.duplicates(db, key, q))


@router.get("/{key}")
async def list_items(key: str, q: str = "", status: str = "active",
                     parent: str = "all", sort: str = "code",
                     limit: int = Query(50, ge=1, le=200),
                     offset: int = Query(0, ge=0),
                     db: AsyncSession = Depends(get_db),
                     user=Depends(get_current_user)):
    return _ok(await engine.list_items(
        db, key, q=q, status=status, parent=parent, sort=sort,
        limit=limit, offset=offset))


@router.post("/{key}")
async def create_item(key: str, payload: dict = Body(...),
                      db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    return _ok(await engine.create_item(db, key, payload, user))


@router.get("/{key}/{item_id}")
async def get_item(key: str, item_id: int,
                   db: AsyncSession = Depends(get_db),
                   user=Depends(get_current_user)):
    return _ok(await engine.get_item(db, key, item_id))


@router.patch("/{key}/{item_id}")
async def update_item(key: str, item_id: int, payload: dict = Body(...),
                      db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    return _ok(await engine.update_item(db, key, item_id, payload, user))


@router.post("/{key}/{item_id}/archive")
async def archive_item(key: str, item_id: int,
                       db: AsyncSession = Depends(get_db),
                       user=Depends(get_current_user)):
    return _ok(await engine.set_status(db, key, item_id, "archived", user, "archive"))


@router.post("/{key}/{item_id}/restore")
async def restore_item(key: str, item_id: int,
                       db: AsyncSession = Depends(get_db),
                       user=Depends(get_current_user)):
    return _ok(await engine.set_status(db, key, item_id, "active", user, "restore"))


@router.delete("/{key}/{item_id}")
async def delete_item(key: str, item_id: int,
                      db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    return _ok(await engine.delete_item(db, key, item_id, user))


@router.get("/{key}/{item_id}/history")
async def item_history(key: str, item_id: int,
                       db: AsyncSession = Depends(get_db),
                       user=Depends(get_current_user)):
    return _ok(await engine.history(db, key, item_id))
