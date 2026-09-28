# tests/test_catalogs_engine.py -- §45: generic-движок справочников НСИ (фаза 1a).
# По образцу test_artifact_folders.py: sqlite+aiosqlite in-memory, без HTTP —
# тестируем engine напрямую (CRUD, автокод, уникальность, аудит, архив,
# RESTRICT при удалении родителя, дедуп-фолбэк, роли на удаление).

import asyncio

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.catalogs.models import Base as NsiBase
from backend.catalogs import engine
from backend.common.deps import CurrentUser
from backend.common.errors import ConflictError, ForbiddenError, ValidationError
from backend.team.models import TeamMember

U_MGR = CurrentUser(id="u1", name="Менеджер")     # role_key=manager
U_ENG = CurrentUser(id="u2", name="Инженер")      # role_key=engineer

# team-модель несёт «чистый» JSONB, который sqlite не рендерит — в тестах
# подменяем таблицу raw-DDL (engine читает из неё только id и role_key).
_TEAM_DDL = """
CREATE TABLE IF NOT EXISTS team (
    id VARCHAR(16) PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
    avatar TEXT, cap INTEGER, can_confirm BOOLEAN,
    competencies TEXT DEFAULT '[]', permissions TEXT DEFAULT '[]',
    status VARCHAR(16) DEFAULT 'active', role_key VARCHAR(32),
    login VARCHAR(64), password_hash TEXT
)
"""


def _run(coro_fn):
    async def wrap():
        eng = create_async_engine("sqlite+aiosqlite:///:memory:")

        # sqlite lower()/LIKE регистронезависимы только для ASCII; на проде —
        # postgres с юникодной локалью. Переопределяем lower() python-версией,
        # чтобы ilike/func.lower работали с кириллицей как на проде.
        @event.listens_for(eng.sync_engine, "connect")
        def _ci_lower(dbapi_conn, record):
            dbapi_conn.create_function(
                "lower", 1, lambda v: v.lower() if isinstance(v, str) else v)

        async with eng.begin() as conn:
            await conn.run_sync(NsiBase.metadata.create_all)
            await conn.execute(text(_TEAM_DDL))
        maker = async_sessionmaker(eng, expire_on_commit=False)
        async with maker() as session:
            session.add(TeamMember(id="u1", name="Менеджер", role="Руководитель продаж",
                                   competencies=[], permissions=[], status="active",
                                   role_key="manager"))
            session.add(TeamMember(id="u2", name="Инженер", role="Инженер",
                                   competencies=[], permissions=[], status="active",
                                   role_key="engineer"))
            await session.commit()
            return await coro_fn(session)

    return asyncio.run(wrap())


def _expect(exc_cls, coro):
    """Асинхронный вызов, ожидание исключения exc_cls; возвращает exception."""
    async def scenario(s):
        try:
            await coro(s)
            return None
        except exc_cls as e:
            return e
    return _run(scenario)


def test_specs_and_fields():
    specs = engine.specs_payload()
    keys = {s["key"] for s in specs}
    assert {"units", "currencies", "regions", "tags"} <= keys
    units = next(s for s in specs if s["key"] == "units")
    fmap = {f["key"]: f for f in units["fields"]}
    assert fmap["name"]["required"] and fmap["name"]["unique"]
    assert isinstance(fmap["kind"]["options"], dict)  # нормализованы в value->label


def test_create_autocode_prefix():
    """Автокод префиксный: ED-0001, затем ED-0002 (решение 2026-09-28)."""
    async def scenario(s):
        a = await engine.create_item(s, "units", {"name": "Пачка", "symbol": "пач", "kind": "шт"}, U_MGR)
        b = await engine.create_item(s, "units", {"name": "Рулон", "symbol": "рул", "kind": "шт"}, U_MGR)
        return a["code"], b["code"], a["status"], a["is_system"]
    assert _run(scenario) == ("ED-0001", "ED-0002", "active", False)


def test_create_unique_name_conflict():
    async def mk(s):
        await engine.create_item(s, "tags", {"name": "Важное"}, U_MGR)
        await engine.create_item(s, "tags", {"name": "важное"}, U_MGR)  # регистр не важен
    e = _expect(ConflictError, mk)
    assert e is not None and "уже есть" in e.message


def test_update_diff_audited():
    async def scenario(s):
        u = await engine.create_item(s, "units", {"name": "Пачка", "symbol": "пач", "kind": "шт"}, U_MGR)
        u2 = await engine.update_item(s, "units", u["id"], {"symbol": "пл"}, U_MGR)
        h = await engine.history(s, "units", u["id"])
        top = h["items"][0]
        return u2["symbol"], top["action"], top["diff"].get("symbol"), top["user_name"]
    sym, action, d, who = _run(scenario)
    assert sym == "пл"
    assert action == "update" and d == {"old": "пач", "new": "пл"} and who == "Менеджер"


def test_archive_restore_and_create_audit():
    async def scenario(s):
        t = await engine.create_item(s, "tags", {"name": "Сезонное"}, U_MGR)
        a = await engine.set_status(s, "tags", t["id"], "archived", U_MGR, "archive")
        lst_active = await engine.list_items(s, "tags", status="active")
        lst_arch = await engine.list_items(s, "tags", status="archived")
        r = await engine.set_status(s, "tags", t["id"], "active", U_MGR, "restore")
        h = await engine.history(s, "tags", t["id"])
        actions = [x["action"] for x in h["items"]]
        return a["status"], len(lst_active["items"]), len(lst_arch["items"]), r["status"], actions
    st, n_active, n_arch, st2, actions = _run(scenario)
    assert st == "archived" and st2 == "active"
    assert n_active == 0 and n_arch == 1
    assert actions[0] == "restore" and "archive" in actions and "create" in actions


def test_delete_region_with_children_restricted():
    async def scenario(s):
        ru = await engine.create_item(s, "regions", {"name": "Россия", "level": "country"}, U_MGR)
        await engine.create_item(s, "regions",
                                 {"name": "Воронежская область", "level": "region",
                                  "parent_id": ru["id"]}, U_MGR)
        err = None
        try:
            await engine.delete_item(s, "regions", ru["id"], U_MGR)
        except ConflictError as e:
            err = e
        return err is not None and "вложенных" in err.message
    assert _run(scenario) is True


def test_delete_role_restricted_and_system_protected():
    async def scenario(s):
        t = await engine.create_item(s, "tags", {"name": "Временное"}, U_MGR)
        err = None
        try:
            await engine.delete_item(s, "tags", t["id"], U_ENG)  # engineer — нельзя
        except ForbiddenError as e:
            err = e
        # делаем системной и проверяем запрет удаления менеджеру
        from backend.catalogs.models import Tag
        obj = await s.get(Tag, t["id"])
        obj.is_system = True
        await s.commit()
        err2 = None
        try:
            await engine.delete_item(s, "tags", t["id"], U_MGR)
        except ForbiddenError as e:
            err2 = e
        return err is not None, err2 is not None
    denied_eng, denied_sys = _run(scenario)
    assert denied_eng and denied_sys


def test_update_system_only_name():
    async def scenario(s):
        from backend.catalogs.models import Unit
        u = await engine.create_item(s, "units", {"name": "Пачка", "symbol": "пач", "kind": "шт"}, U_MGR)
        obj = await s.get(Unit, u["id"])
        obj.is_system = True
        await s.commit()
        err = None
        try:
            await engine.update_item(s, "units", u["id"], {"symbol": "xx"}, U_MGR)
        except ForbiddenError as e:
            err = e
        ok = await engine.update_item(s, "units", u["id"], {"name": "Пачка (10 шт)"}, U_MGR)
        return err is not None, ok["name"]
    denied, newname = _run(scenario)
    assert denied and newname == "Пачка (10 шт)"


def test_duplicates_ilike_fallback():
    async def scenario(s):
        await engine.create_item(s, "units", {"name": "Килограмм", "symbol": "кг", "kind": "вес"}, U_MGR)
        await engine.create_item(s, "units", {"name": "Штука", "symbol": "шт", "kind": "шт"}, U_MGR)
        d = await engine.duplicates(s, "units", "килог")     # sqlite-путь: ILIKE
        d2 = await engine.duplicates(s, "units", "кг")        # дубль по symbol
        d3 = await engine.duplicates(s, "units", "я")         # <2 символов — пусто
        names = [i["name"] for i in d["items"]]
        return names, [i["name"] for i in d2["items"]], d3["items"]
    names, by_sym, empty = _run(scenario)
    assert names == ["Килограмм"] and by_sym == ["Килограмм"] and empty == []


def test_validation_required_and_enum():
    async def mk(s):
        await engine.create_item(s, "units", {"name": ""}, U_MGR)
    e = _expect(ValidationError, mk)
    assert e is not None

    async def mk2(s):
        await engine.create_item(s, "currencies", {"name": "Гривна", "minor_unit": "abc"}, U_MGR)
    e2 = _expect(ValidationError, mk2)
    assert e2 is not None and "целое число" in e2.message


def test_list_filter_sort_pagination():
    async def scenario(s):
        await engine.create_item(s, "tags", {"name": "Бета"}, U_MGR)
        await engine.create_item(s, "tags", {"name": "Альфа"}, U_MGR)
        await engine.create_item(s, "tags", {"name": "Гамма"}, U_MGR)
        page = await engine.list_items(s, "tags", sort="name", limit=2, offset=0)
        page2 = await engine.list_items(s, "tags", sort="-name", limit=2, offset=0)
        q = await engine.list_items(s, "tags", q="альф")
        return ([t["name"] for t in page["items"]], page["total"],
                [t["name"] for t in page2["items"]],
                [t["name"] for t in q["items"]])
    names, total, names_desc, found = _run(scenario)
    assert names == ["Альфа", "Бета"] and total == 3
    assert names_desc == ["Гамма", "Бета"] and found == ["Альфа"]
