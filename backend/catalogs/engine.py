# backend/catalogs/engine.py -- §45: generic-движок справочников НСИ
#
# Единый CRUD/аудит/дедуп поверх реестра SPEC (registry.py) и реальных таблиц
# (models.py, миграция 041). Права (решение 2026-09-28): мутации — все
# авторизованные; физическое удаление — delete_roles (admin/manager).

from datetime import datetime, timezone
from decimal import Decimal
import importlib

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from backend.catalogs.audit import read_history, write_audit
from backend.catalogs.models import Contractor, Currency, NomenclatureItem, Region, Tag, Unit
from backend.catalogs.registry import CATALOGS, field_map
from backend.common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from backend.team.models import TeamMember

_MODELS = {c.__name__: c for c in (Unit, Currency, Region, Tag, Contractor, NomenclatureItem)}

_STATUS_ALLOWED = ("active", "archived", "all")
_SORT_BASE = {"id", "code", "name", "status", "sort_order", "created_at", "updated_at"}


# ---------------------------------------------------------------------------
# Реестр и сериализация
# ---------------------------------------------------------------------------

def get_spec(key: str) -> dict:
    spec = CATALOGS.get(key)
    if spec is None:
        raise NotFoundError(f"неизвестный тип справочника: {key}")
    return spec


def _model(spec: dict):
    return _MODELS[spec["model"]]


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
            "fields": fields,
        })
    return out


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def serialize(spec: dict, obj) -> dict:
    d = {
        "id": obj.id, "code": obj.code, "name": obj.name,
        "status": obj.status, "is_system": bool(obj.is_system), "sort_order": obj.sort_order,
        "created_at": _iso(obj.created_at), "updated_at": _iso(obj.updated_at),
        "updated_by": obj.updated_by,
    }
    for f in spec["fields"]:
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
    """Проставляет <key>_label для ref-полей (одним запросом на поле)."""
    ref_fields = [f for f in spec["fields"] if f["type"] == "ref"]
    for f in ref_fields:
        ids = {it[f["key"]] for it in items if it.get(f["key"]) is not None}
        if not ids:
            continue
        rspec = get_spec(f["ref"])
        rmodel = _model(rspec)
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
    for key, val in fields.items():
        if not val:
            continue
        f = field_map(spec).get(key)
        if not f or not f.get("unique"):
            continue
        q = select(func.count()).select_from(model).where(func.lower(getattr(model, key)) == str(val).lower())
        if exclude_id is not None:
            q = q.where(model.id != exclude_id)
        n = (await db.execute(q)).scalar() or 0
        if n:
            raise ConflictError(f"поле «{f.get('label', key)}»: значение «{val}» уже есть")


async def _next_code(db, spec, model) -> str:
    prefix = spec.get("code_prefix", "NSI")
    rows = (await db.execute(
        select(model.code).where(model.code.like(f"{prefix}-%")))).scalars().all()
    mx = 0
    for c in rows or []:
        try:
            mx = max(mx, int(str(c).rsplit("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"{prefix}-{mx + 1:04d}"


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
    spec = get_spec(key)
    model = _model(spec)
    stmt = select(model)

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
    spec = get_spec(key)
    obj = await db.get(_model(spec), item_id)
    if obj is None:
        raise NotFoundError(f"запись {item_id} не найдена в «{spec['title']}»")
    d = serialize(spec, obj)
    await _resolve_refs(db, spec, [d])
    return d


async def create_item(db, key: str, payload: dict, user) -> dict:
    spec = get_spec(key)
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
    spec = get_spec(key)
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
    diff: dict = {}
    for f in spec["fields"]:
        if f["key"] not in payload:
            continue
        v = _clean_value(f, payload[f["key"]])
        if _req_active(spec, f, is_group) and (v is None or v == ""):
            raise ValidationError(f"поле «{f.get('label', f['key'])}» обязательно")
        if v is None:
            continue
        old = getattr(obj, f["key"])
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
    spec = get_spec(key)
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
    spec = get_spec(key)
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
        n = (await db.execute(
            select(func.count()).select_from(model).where(model.parent_id == obj.id))).scalar() or 0
        if n:
            raise ConflictError(f"у элемента {n} вложенных — сначала переместите или удалите их")

    snapshot = {f["key"]: getattr(obj, f["key"]) for f in spec["fields"]}
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
    spec = get_spec(key)
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
        stmt = (select(model, sim.label("score"))
                .where(or_(sim >= 0.35,
                           *[getattr(model, f).ilike(like) for f in dup_fields]))
                .order_by(sim.desc()).limit(5))
        rows = (await db.execute(stmt)).all()
        items = [{"id": r[0].id, "code": r[0].code, "name": r[0].name,
                  "score": round(float(r[1]), 2)} for r in rows]
    else:
        rows = (await db.execute(
            select(model).where(or_(*[getattr(model, f).ilike(like) for f in dup_fields]))
            .limit(5))).scalars().all()
        items = [{"id": r.id, "code": r.code, "name": r.name, "score": None} for r in rows]
    return {"items": items}


async def merge_items(db, key: str, payload: dict, user) -> dict:
    """Слияние дублей: target — golden record (значения не трогаем), дубли
    архивируются; дети иерархии и ссылки из SPEC.refs переезжают на target."""
    spec = get_spec(key)
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
            update(model).where(model.parent_id.in_(ids)).values(parent_id=target_id))
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
    spec = get_spec(key)
    model = _model(spec)
    if await db.get(model, item_id) is None:
        raise NotFoundError(f"запись {item_id} не найдена в «{spec['title']}»")
    return await read_history(db, key, item_id)
