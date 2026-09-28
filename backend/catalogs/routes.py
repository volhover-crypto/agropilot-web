# backend/catalogs/routes.py -- §45: справочники НСИ, единые эндпоинты
#
# Mount: app.include_router(router, prefix="/agropilot/api/v1")
# GET/POST /v1/catalogs, /v1/catalogs/{type}[/...] — см. CONTRACTS.md §45.
# Права: чтение и мутации — любой авторизованный; DELETE — admin/manager
# (решение 2026-09-28). Роли берутся из team.role_key (токен ролей не несёт).

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.catalogs import engine
from backend.catalogs.models import CatalogType
from backend.common.deps import get_current_user, get_db
from backend.common.errors import NotFoundError

router = APIRouter(prefix="/catalogs", tags=["catalogs"])

# Фаза 1d: управление самими справочниками (только admin) — §45.10
types_router = APIRouter(prefix="/catalogs-types", tags=["catalogs"])


def _ok(data):
    return {"ok": True, "data": data}


@router.get("")
async def list_catalog_types(db: AsyncSession = Depends(get_db),
                             user=Depends(get_current_user)):
    """Реестр типов справочников + схема полей — фронт строит UI из этого.
    Статические (registry.py) + пользовательские (catalog_types, фаза 1d)."""
    return _ok(await engine.specs_payload_db(db))


# ---- управление типами справочников (фаза 1d, admin) ----

@types_router.post("")
async def create_catalog_type(payload: dict = Body(...),
                              db: AsyncSession = Depends(get_db),
                              user=Depends(get_current_user)):
    """Создать пользовательский справочник — только admin."""
    return _ok(await engine.create_type(db, payload, user))


@types_router.get("/{type_id}")
async def get_catalog_type(type_id: int,
                           db: AsyncSession = Depends(get_db),
                           user=Depends(get_current_user)):
    ct = await db.get(CatalogType, type_id)
    if ct is None:
        raise NotFoundError(f"справочник {type_id} не найден")
    return _ok(engine.type_payload(ct))


@types_router.patch("/{type_id}")
async def update_catalog_type(type_id: int, payload: dict = Body(...),
                              db: AsyncSession = Depends(get_db),
                              user=Depends(get_current_user)):
    """Изменить метаданные справочника; схема полей — только добавление новых."""
    return _ok(await engine.update_type(db, type_id, payload, user))


@types_router.post("/{type_id}/archive")
async def archive_catalog_type(type_id: int,
                               db: AsyncSession = Depends(get_db),
                               user=Depends(get_current_user)):
    return _ok(await engine.set_type_status(db, type_id, "archived", user, "archive"))


@types_router.post("/{type_id}/restore")
async def restore_catalog_type(type_id: int,
                               db: AsyncSession = Depends(get_db),
                               user=Depends(get_current_user)):
    return _ok(await engine.set_type_status(db, type_id, "active", user, "restore"))


@types_router.get("/{type_id}/history")
async def catalog_type_history(type_id: int,
                               db: AsyncSession = Depends(get_db),
                               user=Depends(get_current_user)):
    return _ok(await engine.type_history(db, type_id))


# ВАЖНО: /{key}/duplicates и /{key}/merge объявляются ДО /{key}/{item_id},
# иначе FastAPI сматчит "duplicates"/"merge" как item_id.
@router.get("/{key}/duplicates")
async def find_duplicates(key: str, q: str = Query(..., min_length=2),
                          db: AsyncSession = Depends(get_db),
                          user=Depends(get_current_user)):
    return _ok(await engine.duplicates(db, key, q))


@router.post("/{key}/merge")
async def merge_items(key: str, payload: dict = Body(...),
                      db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    """Слияние дублей: {target_id, source_ids[]} — только admin/manager."""
    return _ok(await engine.merge_items(db, key, payload, user))


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
