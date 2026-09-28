# backend/catalogs/engine.py -- §45: generic-движок справочников НСИ
#
# Единый CRUD/аудит/дедуп поверх реестра SPEC (registry.py) и реальных таблиц
# (models.py, миграция 041). Права (решение 2026-09-28): мутации — все
# авторизованные; физическое удаление — delete_roles (admin/manager).
#
# Фаза 1d (045): пользовательские справочники — реестр catalog_types в БД,
# записи в generic-таблице nsi_user_items (значения полей в attrs JSONB).
# Статические SPEC и динамические типы объединяет resolve_spec(db, key).

from datetime import datetime, timezone
from decimal import Decimal
import importlib
import re

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from backend.catalogs.audit import read_history, write_audit
from backend.catalogs.models import (
    CatalogType, Contractor, Currency, NomenclatureItem, Region, Tag, Unit, UserItem)
from backend.catalogs.registry import CATALOGS, field_map
from backend.common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from backend.team.models import TeamMember

_MODELS = {c.__name__: c for c in (Unit, Currency, Region, Tag, Contractor, NomenclatureItem)}

_STATUS_ALLOWED = ("active", "archived", "all")
_SORT_BASE = {"id", "code", "name", "status", "sort_order", "created_at", "updated_at"}

# Реестр пользовательских справочников — entity в catalog_audit
TYPE_ENTITY = "catalog_type"


# ---------------------------------------------------------------------------
# Реестр и сериализация
# ---------------------------------------------------------------------------

def get_spec(key: str) -> dict:
    """Только статические SPEC (ref-цели и прочие синхронные вызовы)."""
    spec = CATALOGS.get(key)
    if spec is None:
        raise NotFoundError(f"неизвестный тип справочника: {key}")
    return spec


async def resolve_spec(db, key: str) -> dict:
    """Статический SPEC или динамический из catalog_types (фаза 1d)."""
    spec = CATALOGS.get(key)
    if spec is not None:
        return spec
    ct = (await db.execute(
        select(CatalogType).where(CatalogType.key == key))).scalar_one_or_none()
    if ct is None:
        raise NotFoundError(f"неизвестный тип справочника: {key}")
    return user_spec(ct)


# Базовые поля каждой generic-записи (колонки code/name); прочие — из схемы типа
_USER_BASE_FIELDS = (
    {"key": "code", "type": "string", "label": "Код", "grid": True, "width": 100},
    {"key": "name", "type": "string", "label": "Наименование", "required": True, "grid": True},
)


def user_spec(ct) -> dict:
    """SPEC того же формата, что и статические, но поверх nsi_user_items."""
    fields = [f for f in (ct.fields_schema or [])
              if isinstance(f, dict) and f.get("key") and f["key"] not in ("code", "name")]
    hierarchical = bool(ct.hierarchical)
    return {
        "title": ct.title,
        "group": ct.group_name or "Мои справочники",
        "icon": ct.icon or "📁",
        "hierarchical": hierarchical,
        "group_items": hierarchical,          # подразделы = группы (папки)
        "code_prefix": ct.code_prefix or "NSI",
        "user_catalog_id": ct.id,
        "user_status": ct.status,
        "fields": [dict(f) for f in (_USER_BASE_FIELDS + tuple(fields))],
        "element_fields": [f["key"] for f in fields],
        "dup_fields": ("name",),
        "delete_roles": ("admin", "manager"),
        "form": "drawer" if len(fields) > 5 else "modal",
    }


def _model(spec: dict):
    if spec.get("user_catalog_id"):
        return UserItem
    return _MODELS[spec["model"]]


def _scoped(spec: dict, model, stmt):
    """Запросы по generic-таблице — всегда в пределах одного справочника."""
    uid = spec.get("user_catalog_id")
    return stmt.where(model.catalog_id == uid) if uid else stmt


def specs_payload() -> list:
    out = []
    for key, spec in CATALOGS.items():
        fields = []
        for f in spec["fields"]:
            opts = f.get("options")
            norm = opts if isinstance(opts, dict) else ({v: v for v in opts} if opts else None)
            fields.append({
                "key": f["key"], "type": f["type"], "label": f.get("label", f["key"]),
                "required": bool(f.get("required")), "unique": bool(f.get("unique")),
                "grid": bool(f.get("grid")), "width": f.get("width"), "options": norm,
            })
        out.append({
            "key": key, "title": spec["title"], "group": spec.get("group", ""),
            "icon": spec.get("icon", "📁"), "hierarchical": bool(spec.get("hierarchical")),
            "status": "active", "managed": False,
            "fields": fields,
        })
    return out


async def specs_payload_db(db) -> list:
    """Статические + пользовательские справочники (фаза 1d) — для GET /v1/catalogs."""
    out = specs_payload()
    rows = (await db.execute(
        select(CatalogType).order_by(CatalogType.group_name, CatalogType.sort_order, CatalogType.id))
    ).scalars().all()
    for ct in rows:
        spec = user_spec(ct)
        fields = []
        for f in spec["fields"]:
            opts = f.get("options")
            norm = opts if isinstance(opts, dict) else ({v: v for v in opts} if opts else None)
            fields.append({
                "key": f["key"], "type": f["type"], "label": f.get("label", f["key"]),
                "required": bool(f.get("required")), "unique": bool(f.get("unique")),
                "grid": bool(f.get("grid")), "width": f.get("width"), "options": norm,
            })
        out.append({
            "key": ct.key, "title": ct.title, "group": spec["group"],
            "icon": spec["icon"], "hierarchical": spec["hierarchical"],
            "status": ct.status, "managed": True, "type_id": ct.id,
            "code_prefix": ct.code_prefix,
            "fields": fields,
        })
    return out


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def serialize(spec: dict, obj) -> dict:
    uid = spec.get("user_catalog_id")
    d = {
        "id": obj.id, "code": obj.code, "name": obj.name,
        "status": obj.status, "is_system": bool(obj.is_system), "sort_order": obj.sort_order,
        "created_at": _iso(obj.created_at), "updated_at": _iso(obj.updated_at),
        "updated_by": obj.updated_by,
    }
    attrs = obj.attrs or {}
    for f in spec["fields"]:
        if uid and f["key"] not in ("code", "name"):
            v = attrs.get(f["key"])
        else:
            v = getattr(obj, f["key"])
        if f["type"] == "decimal" and v is not None:
            v = float(v)  # Decimal не серриализуется в JSON напрямую
        d[f["key"]] = v
    if spec.get("hierarchical"):
        d["parent_id"] = obj.parent_id
    if spec.get("group_items"):
        d["is_group"] = bool(obj.is_group)
    return d


async def _resolve_refs(db, spec: dict, items: list) -> None:
    """Проставляет <key>_label для ref-полей (одним запросом на поле).
    ref-цели — только статические справочники (проверяется при создании типа)."""
    ref_fields = [f for f in spec["fields"] if f["type"] == "ref"]
    for f in ref_fields:
        ids = {it[f["key"]] for it in items if it.get(f["key"]) is not None}
        if not ids:
            continue
        rspec = CATALOGS.get(f["ref"])
        if rspec is None:
            continue
        rmodel = _MODELS[rspec["model"]]
        rows = (await db.execute(
            select(rmodel).where(rmodel.id.in_(ids)))).scalars().all()
        m = {r.id: r.name for r in rows}
        for it in items:
            it[f["key"] + "_label"] = m.get(it[f["key"]])


def _req_active(spec: dict, field: dict, is_group: bool) -> bool:
    """Обязательность поля с учётом групп номенклатуры (element_fields)."""
    if field.get("required") and is_group and field["key"] in spec.get("element_fields", []):
        return False
    return bool(field.get("required"))


async def _check_refs(db, spec: dict, values: dict) -> None:
    for f in spec["fields"]:
        if f["type"] != "ref" or values.get(f["key"]) is None:
            continue
        rspec = get_spec(f["ref"])
        rid = values[f["key"]]
        if await db.get(_model(rspec), rid) is None:
            raise ValidationError(
                f"поле «{f.get('label', f['key'])}»: записи {rid} нет в «{rspec['title']}»")


# ---------------------------------------------------------------------------
# Валидация
# ---------------------------------------------------------------------------

def _clean_value(field: dict, value):
    """Приводит значение к типу поля; ValidationError при несоответствии."""
    t = field["type"]
    label = field.get("label", field["key"])
    if t == "int":
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValidationError(f"поле «{label}» — ожидается целое число")
    if t == "enum":
        if value is None or value == "":
            return None
        opts = field.get("options")
        allowed = list(opts.keys()) if isinstance(opts, dict) else list(opts or [])
        if value not in allowed:
            raise ValidationError(f"поле «{label}» — допустимо: {', '.join(map(str, allowed))}")
        return value
    if t == "decimal":
        if value is None or value == "":
            return None
        try:
            return Decimal(str(value).replace(",", "."))
        except Exception:
            raise ValidationError(f"поле «{label}» — ожидается число")
    if t == "ref":
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValidationError(f"поле «{label}» — ссылка (id записи)")
    # string
    if value is None:
        return ""
    return str(value).strip()


async def _assert_unique(db, spec, model, fields: dict, exclude_id=None) -> None:
    uid = spec.get("user_catalog_id")
    for key, val in fields.items():
        if not val:
            continue
        f = field_map(spec).get(key)
        if not f or not f.get("unique"):
            continue
        if uid:
            # generic-таблица: уникальность значений проверяем в Python —
            # attrs JSONB, DB-констрейнта по выражению нецелесообразна
            rows = (await db.execute(
                _scoped(spec, model, select(model)))).scalars().all()
            for r in rows:
                if exclude_id is not None and r.id == exclude_id:
                    continue
                cur = r.name if key == "name" else (r.attrs or {}).get(key)
                if cur is not None and str(cur).lower() == str(val).lower():
                    raise ConflictError(f"поле «{f.get('label', key)}»: значение «{val}» уже есть")
            continue
        q = select(func.count()).select_from(model).where(func.lower(getattr(model, key)) == str(val).lower())
        if exclude_id is not None:
            q = q.where(model.id != exclude_id)
        n = (await db.execute(q)).scalar() or 0
        if n:
            raise ConflictError(f"поле «{f.get('label', key)}»: значение «{val}» уже есть")


async def _next_code(db, spec, model) -> str:
    prefix = spec.get("code_prefix", "NSI")
    q = _scoped(spec, model, select(model.code).where(model.code.like(f"{prefix}-%")))
    rows = (await db.execute(q)).scalars().all()
    mx = 0
    for c in rows or []:
        try:
            mx = max(mx, int(str(c).rsplit("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"{prefix}-{mx + 1:04d}"


def _require_mutation_allowed(spec: dict) -> None:
    """Записи архивированного справочника только читаются (фаза 1d)."""
    if spec.get("user_status") == "archived":
        raise ConflictError("справочник в архиве — сначала восстановите его (админ)")


async def _require_role(db, user, spec) -> None:
    allowed = tuple(spec.get("delete_roles", ("admin", "manager")))
    m = await db.get(TeamMember, user.id)
    if m is None or (m.role_key or "") not in allowed:
        raise ForbiddenError("удаление записей справочника — только руководитель (admin/manager)")


# ---------------------------------------------------------------------------
# Операции
# ---------------------------------------------------------------------------

async def list_items(db, key: str, *, q: str = "", status: str = "active",
                     parent: str = "all", sort: str = "code",
                     limit: int = 50, offset: int = 0) -> dict:
    spec = await resolve_spec(db, key)
    model = _model(spec)
    stmt = _scoped(spec, model, select(model))

    if status not in _STATUS_ALLOWED:
        raise ValidationError("status: active | archived | all")
    if status != "all":
        stmt = stmt.where(model.status == status)

    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        conds = [model.name.ilike(like), model.code.ilike(like)]
        stmt = stmt.where(or_(*conds))

    if spec.get("hierarchical"):
        if parent == "none":
            stmt = stmt.where(model.parent_id.is_(None))
        elif parent not in ("", "all"):
            try:
                stmt = stmt.where(model.parent_id == int(parent))
            except ValueError:
                raise ValidationError("parent: all | none | id")

    fmap = field_map(spec)
    skey = sort.lstrip("-")
    if skey not in _SORT_BASE and skey not in fmap:
        raise ValidationError(f"сортировка по «{skey}» недоступна")
    col = getattr(model, skey, model.code)
    stmt = stmt.order_by(col.desc() if sort.startswith("-") else col.asc(), model.id.asc())

    total = (await db.execute(
        select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    rows = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    items = [serialize(spec, r) for r in rows]
    await _resolve_refs(db, spec, items)
    return {"items": items,
            "total": total, "limit": limit, "offset": offset}


async def get_item(db, key: str, item_id: int) -> dict:
    spec = await resolve_spec(db, key)
    obj = await db.get(_model(spec), item_id)
    if obj is None:
        raise NotFoundError(f"запись {item_id} не найдена в «{spec['title']}»")
    d = serialize(spec, obj)
    await _resolve_refs(db, spec, [d])
    return d


async def create_item(db, key: str, payload: dict, user) -> dict:
    spec = await resolve_spec(db, key)
    _require_mutation_allowed(spec)
    model = _model(spec)
    if not isinstance(payload, dict):
        raise ValidationError("тело запроса — объект JSON")
    fmap = field_map(spec)
    allowed_keys = set(fmap) | ({"parent_id"} if spec.get("hierarchical") else set())
    if spec.get("group_items"):
        allowed_keys.add("is_group")
    unknown = set(payload) - allowed_keys
    if unknown:
        raise ValidationError(f"неизвестные поля: {', '.join(sorted(unknown))}")

    values: dict = {}
    is_group = bool(payload.get("is_group")) if spec.get("group_items") else False
    for f in spec["fields"]:
        if f["key"] in payload:
            v = _clean_value(f, payload[f["key"]])
            if _req_active(spec, f, is_group) and (v is None or v == ""):
                raise ValidationError(f"поле «{f.get('label', f['key'])}» обязательно")
            if v is not None:
                values[f["key"]] = v
        elif _req_active(spec, f, is_group):
            raise ValidationError(f"поле «{f.get('label', f['key'])}» обязательно")

    if spec.get("hierarchical") and payload.get("parent_id") not in (None, ""):
        try:
            pid = int(payload["parent_id"])
        except (TypeError, ValueError):
            raise ValidationError("parent_id — целое число")
        if await db.get(model, pid) is None:
            raise ValidationError(f"родительский элемент {pid} не найден")
        values["parent_id"] = pid

    await _check_refs(db, spec, values)
    await _assert_unique(db, spec, model, values)
    if not values.get("code"):
        values["code"] = await _next_code(db, spec, model)

    now = datetime.now(timezone.utc)
    if spec.get("user_catalog_id"):
        # generic-хранилище: code/name/parent_id/is_group — колонки, остальное attrs
        attrs = {}
        for k, v in values.items():
            if k in ("code", "name", "parent_id"):
                continue
            if isinstance(v, Decimal):
                v = float(v)  # Decimal не кладём в JSONB
            attrs[k] = v
        obj = UserItem(
            catalog_id=spec["user_catalog_id"],
            code=values.get("code", ""), name=values.get("name", ""),
            parent_id=values.get("parent_id"), is_group=is_group, attrs=attrs,
            created_by=user.id, updated_by=user.id, created_at=now, updated_at=now)
    else:
        extra = {"is_group": is_group} if spec.get("group_items") else {}
        obj = model(**values, **extra, created_by=user.id, updated_by=user.id,
                    created_at=now, updated_at=now)
    db.add(obj)
    try:
        await db.flush()
    except IntegrityError:
        raise ConflictError("конфликт уникальности: код/наименование уже существуют")
    await write_audit(db, key, obj.id, "create",
                      {k: {"old": None, "new": v} for k, v in values.items()}, user)
    await db.commit()
    await db.refresh(obj)
    d = serialize(spec, obj)
    await _resolve_refs(db, spec, [d])
    return d


async def update_item(db, key: str, item_id: int, payload: dict, user) -> dict:
    spec = await resolve_spec(db, key)
    _require_mutation_allowed(spec)
    model = _model(spec)
    if not isinstance(payload, dict):
        raise ValidationError("тело запроса — объект JSON")
    obj = await db.get(model, item_id)
    if obj is None:
        raise NotFoundError(f"запись {item_id} не найдена в «{spec['title']}»")

    fmap = field_map(spec)
    allowed_keys = set(fmap) | ({"parent_id"} if spec.get("hierarchical") else set())
    if spec.get("group_items"):
        allowed_keys.add("is_group")
    unknown = set(payload) - allowed_keys
    if unknown:
        raise ValidationError(f"неизвестные поля: {', '.join(sorted(unknown))}")

    # тип записи (группа/элемент) не меняется после создания
    if spec.get("group_items") and "is_group" in payload \
            and bool(payload["is_group"]) != bool(obj.is_group):
        raise ValidationError("тип записи (группа/элемент) не меняется — создайте новую запись")

    is_group = bool(getattr(obj, "is_group", False))
    uid = spec.get("user_catalog_id")
    diff: dict = {}
    for f in spec["fields"]:
        if f["key"] not in payload:
            continue
        v = _clean_value(f, payload[f["key"]])
        if _req_active(spec, f, is_group) and (v is None or v == ""):
            raise ValidationError(f"поле «{f.get('label', f['key'])}» обязательно")
        if v is None:
            continue
        old = ((obj.attrs or {}).get(f["key"])
               if (uid and f["key"] not in ("code", "name"))
               else getattr(obj, f["key"]))
        if v != old:
            diff[f["key"]] = {"old": old, "new": v}

    if spec.get("hierarchical") and "parent_id" in payload:
        new_parent = payload.get("parent_id")
        np = None if new_parent in (None, "") else int(new_parent)
        if np == obj.id:
            raise ValidationError("элемент не может быть родителем сам себе")
        if np is not None and await db.get(model, np) is None:
            raise ValidationError(f"родительский элемент {np} не найден")
        if obj.parent_id != np:
            diff["parent_id"] = {"old": obj.parent_id, "new": np}

    if not diff:
        return serialize(spec, obj)

    # Предопределённые записи: менять можно только наименование и порядок
    if obj.is_system and set(diff) - {"name", "sort_order"}:
        raise ForbiddenError("системная запись: изменение только наименования/порядка")

    await _check_refs(db, spec, {k: v["new"] for k, v in diff.items()})
    await _assert_unique(db, spec, model,
                         {k: v["new"] for k, v in diff.items()}, exclude_id=obj.id)

    if spec.get("user_catalog_id"):
        # generic-хранилище: code/name — колонки, прочие поля — attrs
        attrs = dict(obj.attrs or {})
        for k, v in diff.items():
            nv = v["new"]
            if isinstance(nv, Decimal):
                nv = float(nv)
            if k in ("code", "name", "parent_id"):
                setattr(obj, k, nv)
            else:
                attrs[k] = nv
        obj.attrs = attrs
    else:
        for k, v in diff.items():
            setattr(obj, k, v["new"])
    obj.updated_by = user.id
    obj.updated_at = datetime.now(timezone.utc)
    try:
        await db.flush()
    except IntegrityError:
        raise ConflictError("конфликт уникальности: код/наименование уже существуют")
    await write_audit(db, key, obj.id, "update", diff, user)
    await db.commit()
    await db.refresh(obj)
    d = serialize(spec, obj)
    await _resolve_refs(db, spec, [d])
    return d


async def set_status(db, key: str, item_id: int, status: str, user,
                     action: str) -> dict:
    spec = await resolve_spec(db, key)
    _require_mutation_allowed(spec)
    model = _model(spec)
    obj = await db.get(model, item_id)
    if obj is None:
        raise NotFoundError(f"запись {item_id} не найдена в «{spec['title']}»")
    if obj.is_system:
        raise ForbiddenError("системную запись нельзя архивировать/удалять")
    if obj.status == status:
        return serialize(spec, obj)
    old = obj.status
    obj.status = status
    obj.updated_by = user.id
    obj.updated_at = datetime.now(timezone.utc)
    await write_audit(db, key, obj.id, action, {"status": {"old": old, "new": status}}, user)
    await db.commit()
    await db.refresh(obj)
    return serialize(spec, obj)


async def delete_item(db, key: str, item_id: int, user) -> dict:
    spec = await resolve_spec(db, key)
    _require_mutation_allowed(spec)
    model = _model(spec)
    await _require_role(db, user, spec)
    obj = await db.get(model, item_id)
    if obj is None:
        raise NotFoundError(f"запись {item_id} не найдена в «{spec['title']}»")
    if obj.is_system:
        raise ForbiddenError("системную запись нельзя удалить")

    # Вложенные элементы иерархии не дают удалить (self-FK RESTRICT на проде;
    # явный предчек даёт читаемую ошибку и на sqlite в тестах)
    if spec.get("hierarchical"):
        q = _scoped(spec, model,
                    select(func.count()).select_from(model).where(model.parent_id == obj.id))
        n = (await db.execute(q)).scalar() or 0
        if n:
            raise ConflictError(f"у элемента {n} вложенных — сначала переместите или удалите их")

    snapshot: dict = {}
    for f in spec["fields"]:
        snapshot[f["key"]] = ((obj.attrs or {}).get(f["key"])
                              if (spec.get("user_catalog_id") and f["key"] not in ("code", "name"))
                              else getattr(obj, f["key"]))
    await write_audit(db, key, obj.id, "delete",
                      {k: {"old": v, "new": None} for k, v in snapshot.items()}, user)
    await db.delete(obj)
    try:
        await db.flush()
    except IntegrityError:
        raise ConflictError("запись используется в других сущностях — удаление запрещено")
    await db.commit()
    return {"deleted": item_id}


async def duplicates(db, key: str, q: str) -> dict:
    """Fuzzy-кандидаты дублей: pg_trgm similarity (PG) + ILIKE-фолбэк (тесты)."""
    spec = await resolve_spec(db, key)
    model = _model(spec)
    q = (q or "").strip()
    if len(q) < 2:
        return {"items": []}
    dup_fields = spec.get("dup_fields", ("name",))
    like = f"%{q}%"

    is_pg = False
    try:
        is_pg = db.dialect.name == "postgresql"
    except Exception:
        pass

    if is_pg:
        sim = func.similarity(model.name, q)
        stmt = (_scoped(spec, model, select(model, sim.label("score")))
                .where(or_(sim >= 0.35,
                           *[getattr(model, f).ilike(like) for f in dup_fields]))
                .order_by(sim.desc()).limit(5))
        rows = (await db.execute(stmt)).all()
        items = [{"id": r[0].id, "code": r[0].code, "name": r[0].name,
                  "score": round(float(r[1]), 2)} for r in rows]
    else:
        stmt = _scoped(spec, model, select(model)).where(
            or_(*[getattr(model, f).ilike(like) for f in dup_fields])).limit(5)
        rows = (await db.execute(stmt)).scalars().all()
        items = [{"id": r.id, "code": r.code, "name": r.name, "score": None} for r in rows]
    return {"items": items}


async def merge_items(db, key: str, payload: dict, user) -> dict:
    """Слияние дублей: target — golden record (значения не трогаем), дубли
    архивируются; дети иерархии и ссылки из SPEC.refs переезжают на target."""
    spec = await resolve_spec(db, key)
    _require_mutation_allowed(spec)
    model = _model(spec)
    await _require_role(db, user, spec)  # слияние сродни удалению дублей
    if not isinstance(payload, dict):
        raise ValidationError("тело запроса — объект JSON")
    target_id = payload.get("target_id")
    source_ids = payload.get("source_ids")
    if target_id in (None, ""):
        raise ValidationError("target_id обязателен")
    try:
        target_id = int(target_id)
    except (TypeError, ValueError):
        raise ValidationError("target_id — целое число")
    if not isinstance(source_ids, (list, tuple)) or not source_ids:
        raise ValidationError("source_ids — список хотя бы из одной записи")
    ids = []
    for sid in source_ids:
        try:
            ids.append(int(sid))
        except (TypeError, ValueError):
            raise ValidationError("source_ids — целые числа")
    if target_id in ids:
        raise ValidationError("цель слияния не может быть среди дублей")

    target = await db.get(model, target_id)
    if target is None:
        raise NotFoundError(f"запись {target_id} не найдена в «{spec['title']}»")
    sources = []
    for sid in ids:
        s = await db.get(model, sid)
        if s is None:
            raise NotFoundError(f"запись {sid} не найдена в «{spec['title']}»")
        if s.is_system:
            raise ForbiddenError(f"«{s.name}» — системная запись, слияние недоступно")
        sources.append(s)

    moved: dict = {}
    if spec.get("hierarchical"):
        res = await db.execute(
            _scoped(spec, model,
                    update(model).where(model.parent_id.in_(ids)).values(parent_id=target_id)))
        moved["children"] = int(res.rowcount or 0)
    for r in spec.get("refs", []):  # фаза 1c+: ссылки из других модулей
        RModel = getattr(importlib.import_module(r["module"]), r["model"])
        res = await db.execute(
            update(RModel).where(getattr(RModel, r["column"]).in_(ids))
            .values(**{r["column"]: target_id}))
        moved[r["model"]] = int(res.rowcount or 0)

    now = datetime.now(timezone.utc)
    for s in sources:
        s.status = "archived"
        s.updated_by = user.id
        s.updated_at = now
        await write_audit(db, key, s.id, "merge",
                          {"merged_into": {"old": None,
                                           "new": {"id": target.id, "name": target.name}}}, user)
    await write_audit(db, key, target.id, "merge",
                      {"merged_from": {"old": None,
                                       "new": [{"id": s.id, "name": s.name} for s in sources]},
                       "moved": {"old": None, "new": moved}}, user)
    await db.commit()
    return {"target_id": target.id, "merged": [s.id for s in sources], "moved": moved}


async def history(db, key: str, item_id: int) -> dict:
    spec = await resolve_spec(db, key)
    model = _model(spec)
    if await db.get(model, item_id) is None:
        raise NotFoundError(f"запись {item_id} не найдена в «{spec['title']}»")
    return await read_history(db, key, item_id)


# ---------------------------------------------------------------------------
# Управление типами справочников (фаза 1d) — только admin (role_key)
# ---------------------------------------------------------------------------

_ALLOWED_FIELD_TYPES = ("string", "int", "decimal", "enum", "ref")
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

# Транслитерация RU→EN для автоключа из названия
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(text: str) -> str:
    s = (text or "").strip().lower()
    s = "".join(_TRANSLIT.get(ch, ch) for ch in s)
    s = re.sub(r"[^a-z0-9_]+", "_", s).strip("_")
    return s[:32]


async def _require_admin(db, user) -> None:
    m = await db.get(TeamMember, user.id)
    if m is None or (m.role_key or "") != "admin":
        raise ForbiddenError("управление справочниками — только администратор (role_key=admin)")


def _validate_fields_schema(fields) -> list:
    """Нормализация и проверка схемы полей пользовательского справочника."""
    if not isinstance(fields, (list, tuple)):
        raise ValidationError("fields — список описаний полей")
    out = []
    seen = set()
    for raw in fields:
        if not isinstance(raw, dict):
            raise ValidationError("каждое поле — объект {key, type, label}")
        key = str(raw.get("key") or "").strip()
        if not re.match(r"^[a-z][a-z0-9_]{0,31}$", key):
            raise ValidationError(f"ключ поля «{key}»: латиница/цифры/подчёркивание, с буквы")
        if key in ("code", "name", "parent_id", "is_group", "id", "status"):
            raise ValidationError(f"ключ поля «{key}» зарезервирован")
        if key in seen:
            raise ValidationError(f"поле «{key}» повторяется")
        seen.add(key)
        t = raw.get("type", "string")
        if t not in _ALLOWED_FIELD_TYPES:
            raise ValidationError(f"поле «{key}»: тип должен быть одним из {_ALLOWED_FIELD_TYPES}")
        opts = raw.get("options")
        if t == "enum":
            if isinstance(opts, dict):
                opts = dict(opts)
            elif isinstance(opts, (list, tuple)) and opts:
                opts = {str(v): str(v) for v in opts}
            else:
                raise ValidationError(f"поле «{key}» (enum): нужен список options")
        elif t == "ref":
            ref = str(raw.get("ref") or "")
            if ref not in CATALOGS:
                raise ValidationError(f"поле «{key}» (ref): цель «{ref}» не существует")
        f = {"key": key, "type": t, "label": str(raw.get("label") or key)}
        for flag in ("required", "unique", "grid"):
            if raw.get(flag):
                f[flag] = True
        if raw.get("width"):
            f["width"] = int(raw["width"])
        if opts is not None and t == "enum":
            f["options"] = opts
        if t == "ref":
            f["ref"] = ref
        out.append(f)
    return out


def type_payload(ct) -> dict:
    return {
        "id": ct.id, "key": ct.key, "title": ct.title,
        "group": ct.group_name, "icon": ct.icon,
        "hierarchical": bool(ct.hierarchical), "code_prefix": ct.code_prefix,
        "fields": ct.fields_schema or [], "status": ct.status,
        "sort_order": ct.sort_order,
        "created_at": _iso(ct.created_at), "updated_at": _iso(ct.updated_at),
    }


async def create_type(db, payload: dict, user) -> dict:
    await _require_admin(db, user)
    if not isinstance(payload, dict):
        raise ValidationError("тело запроса — объект JSON")
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValidationError("title обязателен")
    key = str(payload.get("key") or "").strip() or slugify(title)
    if not _KEY_RE.match(key):
        raise ValidationError("key: латиница/цифры/подчёркивание, начинается с буквы (2–32 знака)")
    if key in CATALOGS:
        raise ConflictError(f"ключ «{key}» занят системным справочником")
    dup = (await db.execute(
        select(CatalogType).where(CatalogType.key == key))).scalar_one_or_none()
    if dup is not None:
        raise ConflictError(f"справочник с ключом «{key}» уже есть")
    prefix = str(payload.get("code_prefix") or "").strip().upper() or (key[:3].upper() or "NSI")
    if not re.match(r"^[A-Z0-9]{1,6}$", prefix):
        raise ValidationError("code_prefix: 1–6 заглавных латинских букв/цифр")
    fields = _validate_fields_schema(payload.get("fields") or [])

    ct = CatalogType(
        key=key, title=title,
        group_name=str(payload.get("group") or "").strip() or "Мои справочники",
        icon=str(payload.get("icon") or "📁")[:8] or "📁",
        hierarchical=bool(payload.get("hierarchical", True)),
        code_prefix=prefix, fields_schema=fields,
        status="active", sort_order=int(payload.get("sort_order") or 0),
        created_by=user.id, updated_by=user.id,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(ct)
    try:
        await db.flush()
    except IntegrityError:
        raise ConflictError(f"справочник с ключом «{key}» уже есть")
    await write_audit(db, TYPE_ENTITY, ct.id, "create",
                      {"title": {"old": None, "new": ct.title},
                       "key": {"old": None, "new": ct.key},
                       "fields": {"old": None,
                                  "new": [f["key"] for f in fields]}}, user)
    await db.commit()
    await db.refresh(ct)
    return type_payload(ct)


async def update_type(db, type_id: int, payload: dict, user) -> dict:
    await _require_admin(db, user)
    if not isinstance(payload, dict):
        raise ValidationError("тело запроса — объект JSON")
    ct = await db.get(CatalogType, type_id)
    if ct is None:
        raise NotFoundError(f"справочник {type_id} не найден")
    if ct.status == "archived":
        raise ConflictError("справочник в архиве — сначала восстановите его")

    diff: dict = {}
    for col, k in (("title", "title"), ("group_name", "group"), ("icon", "icon")):
        if k in payload:
            v = str(payload[k] or "").strip()
            if k == "title" and not v:
                raise ValidationError("title не может быть пустым")
            old = getattr(ct, col)
            if v and v != old:
                diff[col] = {"old": old, "new": v}
    if "code_prefix" in payload:
        p = str(payload["code_prefix"] or "").strip().upper()
        if not re.match(r"^[A-Z0-9]{1,6}$", p):
            raise ValidationError("code_prefix: 1–6 заглавных латинских букв/цифр")
        if p != ct.code_prefix:
            diff["code_prefix"] = {"old": ct.code_prefix, "new": p}
    if "sort_order" in payload:
        so = int(payload["sort_order"] or 0)
        if so != ct.sort_order:
            diff["sort_order"] = {"old": ct.sort_order, "new": so}

    if "fields" in payload:
        new_fields = _validate_fields_schema(payload["fields"])
        old_fields = {f["key"]: f for f in (ct.fields_schema or [])}
        new_keys = {f["key"] for f in new_fields}
        has_items = (await db.execute(
            select(func.count()).select_from(UserItem)
            .where(UserItem.catalog_id == ct.id))).scalar() or 0
        removed = []
        for k, old_f in old_fields.items():
            new_f = next((f for f in new_fields if f["key"] == k), None)
            if new_f is None:
                if has_items:
                    raise ConflictError(
                        f"поле «{k}» удалить нельзя — в справочнике {has_items} записей "
                        "(допускается только добавление новых полей)")
                removed.append(k)
            elif (new_f.get("type") != old_f.get("type")
                  or bool(new_f.get("required")) != bool(old_f.get("required"))):
                raise ConflictError(
                    f"поле «{k}»: менять тип/обязательность существующего поля нельзя "
                    "(допускается только добавление новых полей)")
        added = [f["key"] for f in new_fields if f["key"] not in old_fields]
        if added or removed:
            diff["fields"] = {"old": list(old_fields), "new": [f["key"] for f in new_fields]}
            ct.fields_schema = new_fields

    if not diff:
        return type_payload(ct)
    for k, v in diff.items():
        if k in ("title", "group_name", "icon", "code_prefix", "sort_order"):
            setattr(ct, k, v["new"])
    ct.updated_by = user.id
    ct.updated_at = datetime.now(timezone.utc)
    await write_audit(db, TYPE_ENTITY, ct.id, "update", diff, user)
    await db.commit()
    await db.refresh(ct)
    return type_payload(ct)


async def set_type_status(db, type_id: int, status: str, user, action: str) -> dict:
    await _require_admin(db, user)
    ct = await db.get(CatalogType, type_id)
    if ct is None:
        raise NotFoundError(f"справочник {type_id} не найден")
    if ct.status == status:
        return type_payload(ct)
    old = ct.status
    ct.status = status
    ct.updated_by = user.id
    ct.updated_at = datetime.now(timezone.utc)
    await write_audit(db, TYPE_ENTITY, ct.id, action,
                      {"status": {"old": old, "new": status}}, user)
    await db.commit()
    await db.refresh(ct)
    return type_payload(ct)


async def type_history(db, type_id: int) -> dict:
    ct = await db.get(CatalogType, type_id)
    if ct is None:
        raise NotFoundError(f"справочник {type_id} не найден")
    return await read_history(db, TYPE_ENTITY, type_id)
