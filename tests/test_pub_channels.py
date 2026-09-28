# tests/test_pub_channels.py -- §46.6 (Ф2): реестр каналов публикаций.
# По образцу test_catalogs_engine.py: sqlite+aiosqlite in-memory, без HTTP —
# тестируем routes/engine напрямую (права admin, секреты наружу не отдаются,
# валидация platform/target/token/template, заморозка, ротация токена).

import asyncio

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.pub import routes as pub_routes
from backend.pub.models import Base as PubBase
from backend.common.deps import CurrentUser
from backend.common.errors import ConflictError, ForbiddenError, ValidationError
from backend.team.models import TeamMember

U_ADM = CurrentUser(id="u3", name="Админ")        # role_key=admin
U_ENG = CurrentUser(id="u2", name="Инженер")      # role_key=engineer

# team-модель несёт JSONB, который sqlite не рендерит — raw-DDL (паттерн §45)
_TEAM_DDL = """
CREATE TABLE IF NOT EXISTS team (
    id VARCHAR(16) PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
    avatar TEXT, cap INTEGER, can_confirm BOOLEAN,
    competencies TEXT DEFAULT '[]', permissions TEXT DEFAULT '[]',
    status VARCHAR(16) DEFAULT 'active', role_key VARCHAR(32),
    login VARCHAR(64), password_hash TEXT
)
"""

TG_TOKEN = "123456789:AAEhBOWeik6ad9r_QXMENQjcrGbqCr4K-4s"
VK_TOKEN = "vk1.a." + "x" * 60


def _run(coro_fn):
    async def wrap():
        eng = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with eng.begin() as conn:
            await conn.run_sync(PubBase.metadata.create_all)
            await conn.execute(text(_TEAM_DDL))
        maker = async_sessionmaker(eng, expire_on_commit=False)
        async with maker() as session:
            session.add(TeamMember(id="u2", name="Инженер", role="Инженер",
                                   competencies=[], permissions=[], status="active",
                                   role_key="engineer"))
            session.add(TeamMember(id="u3", name="Админ", role="Руководитель продаж",
                                   competencies=[], permissions=[], status="active",
                                   role_key="admin"))
            await session.commit()
            await coro_fn(session)
        await eng.dispose()
    asyncio.run(wrap())


def test_create_and_list_no_secrets_leak():
    async def body(db):
        r = await pub_routes.create_channel(
            {"name": "TG основной", "platform": "telegram", "target": "@agropilot",
             "token": TG_TOKEN, "template": {"max_len": 3000, "hashtags": "keep"}},
            db=db, user=U_ADM)
        ch = r["data"]
        assert ch["platform"] == "telegram" and ch["status"] == "active"
        assert ch["has_token"] is True
        assert "secrets" not in ch and "token" not in ch  # секреты наружу не отдаются
        lst = (await pub_routes.list_channels(db=db, user=U_ENG))["data"]
        assert len(lst) == 1
        assert lst[0]["has_token"] is True and "secrets" not in lst[0]
        # чтение доступно не-админу
        row = (await db.execute(text("SELECT secrets FROM pub_channels"))).first()
        assert TG_TOKEN in row[0]  # но в БД токен лежит
    _run(body)


def test_create_requires_admin():
    async def body(db):
        try:
            await pub_routes.create_channel(
                {"name": "x", "platform": "telegram", "target": "-100123",
                 "token": TG_TOKEN}, db=db, user=U_ENG)
            assert False, "ожидали ForbiddenError"
        except ForbiddenError:
            pass
    _run(body)


def test_instagram_conflicts_and_platform_validated():
    async def body(db):
        try:
            await pub_routes.create_channel(
                {"name": "ig", "platform": "instagram", "target": "1",
                 "token": "x" * 30}, db=db, user=U_ADM)
            assert False, "ожидали ConflictError (Ф6)"
        except ConflictError:
            pass
        try:
            await pub_routes.create_channel(
                {"name": "t", "platform": "tiktok", "target": "1",
                 "token": "x" * 30}, db=db, user=U_ADM)
            assert False, "ожидали ValidationError"
        except ValidationError:
            pass
    _run(body)


def test_target_rules_per_platform():
    async def body(db):
        for plat, bad in (("vk", "12345"), ("vk", "abc"),
                          ("telegram", "space inside")):
            try:
                await pub_routes.create_channel(
                    {"name": "t", "platform": plat, "target": bad,
                     "token": TG_TOKEN}, db=db, user=U_ADM)
                assert False, f"{plat}/{bad} должен был упасть"
            except ValidationError:
                pass
        # валидные варианты
        r = await pub_routes.create_channel(
            {"name": "vk", "platform": "vk", "target": "-12345678",
             "token": VK_TOKEN}, db=db, user=U_ADM)
        assert r["data"]["target"] == "-12345678"
    _run(body)


def test_token_validation():
    async def body(db):
        for tok in ("", "short", "x" * 300, "has space inside1234567890"):
            try:
                await pub_routes.create_channel(
                    {"name": "t", "platform": "telegram", "target": "@channel",
                     "token": tok}, db=db, user=U_ADM)
                assert False, f"{tok!r} должен был упасть"
            except ValidationError:
                pass
    _run(body)


def test_template_validation():
    async def body(db):
        for t in ("[]", {"max_len": 10}, {"max_len": "big"}, {"hashtags": "drop"},
                  {"llm_prompt": 42}):
            try:
                await pub_routes.create_channel(
                    {"name": "t", "platform": "telegram", "target": "@channel",
                     "token": TG_TOKEN, "template": t}, db=db, user=U_ADM)
                assert False, f"{t!r} должен был упасть"
            except ValidationError:
                pass
        r = await pub_routes.create_channel(
            {"name": "t", "platform": "telegram", "target": "@channel",
             "token": TG_TOKEN, "template": {"max_len": 2000, "hashtags": "strip",
                                             "custom_key": [1, 2]}},
            db=db, user=U_ADM)
        assert r["data"]["template"]["custom_key"] == [1, 2]  # прочие ключи проходят
    _run(body)


def test_freeze_and_token_rotation():
    async def body(db):
        ch = (await pub_routes.create_channel(
            {"name": "dzen relay", "platform": "dzen", "target": "-100999",
             "token": TG_TOKEN}, db=db, user=U_ADM))["data"]
        # заморозка
        r = await pub_routes.update_channel(ch["id"], {"status": "frozen"},
                                            db=db, user=U_ADM)
        assert r["data"]["status"] == "frozen" and r["data"]["frozen_at"]
        # заморозка видна в списке и не удаляет канал
        lst = (await pub_routes.list_channels(db=db, user=U_ADM))["data"]
        assert lst[0]["status"] == "frozen"
        # ротация токена: пустая строка не трогает, новый перезаписывает
        r = await pub_routes.update_channel(
            ch["id"], {"token": "", "name": "dzen relay 2"}, db=db, user=U_ADM)
        assert r["data"]["name"] == "dzen relay 2"
        row = (await db.execute(text("SELECT secrets FROM pub_channels"))).first()
        assert TG_TOKEN in row[0]
        NEW = "999:BB" + "y" * 40
        await pub_routes.update_channel(ch["id"], {"token": NEW}, db=db, user=U_ADM)
        row = (await db.execute(text("SELECT secrets FROM pub_channels"))).first()
        assert NEW in row[0] and TG_TOKEN not in row[0]
        # разморозка
        r = await pub_routes.update_channel(ch["id"], {"status": "active"},
                                            db=db, user=U_ADM)
        assert r["data"]["status"] == "active" and not r["data"]["frozen_at"]
    _run(body)


def test_update_requires_admin_and_404():
    from backend.common.errors import NotFoundError
    async def body(db):
        try:
            await pub_routes.update_channel(1, {"name": "x"}, db=db, user=U_ENG)
            assert False, "ожидали ForbiddenError"
        except ForbiddenError:
            pass
        ch = (await pub_routes.create_channel(
            {"name": "t", "platform": "telegram", "target": "@channel",
             "token": TG_TOKEN}, db=db, user=U_ADM))["data"]
        try:
            await pub_routes.update_channel(ch["id"] + 999, {"name": "x"},
                                            db=db, user=U_ADM)
            assert False, "ожидали NotFoundError"
        except NotFoundError:
            pass
    _run(body)
