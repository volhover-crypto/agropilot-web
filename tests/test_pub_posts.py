# tests/test_pub_posts.py -- §46.7 (Ф3): посты публикаций + publish (n8n мок).
# По образцу test_pub_channels.py: sqlite in-memory, без HTTP. Вызов n8n
# мокируем подменой urllib.request.urlopen (проверяем контракт publish:
# pending-строки, проксирование ответа, недоступность движка).

import asyncio
import io
import json

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.pub import routes as pub_routes
from backend.pub.models import Base as PubBase
from backend.common.deps import CurrentUser
from backend.common.errors import ConflictError, ValidationError
from backend.team.models import TeamMember

U_ADM = CurrentUser(id="U3", name="Админ")       # role_key=admin
U_MGR = CurrentUser(id="U1", name="Менеджер")    # role_key=manager
U_ENG = CurrentUser(id="U2", name="Инженер")     # role_key=engineer

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


def _run(coro_fn):
    async def wrap():
        eng = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with eng.begin() as conn:
            await conn.run_sync(PubBase.metadata.create_all)
            await conn.execute(text(_TEAM_DDL))
        maker = async_sessionmaker(eng, expire_on_commit=False)
        async with maker() as session:
            for uid, name, rk in (("U1", "Менеджер", "manager"),
                                  ("U2", "Инженер", "engineer"),
                                  ("U3", "Админ", "admin")):
                session.add(TeamMember(id=uid, name=name, role="Роль",
                                       competencies=[], permissions=[],
                                       status="active", role_key=rk))
            await session.commit()
            await coro_fn(session)
        await eng.dispose()
    asyncio.run(wrap())


async def _mk_channels(db):
    a = await pub_routes.create_channel(
        {"name": "TG", "platform": "telegram", "target": "@channel", "token": TG_TOKEN},
        db=db, user=U_ADM)
    b = await pub_routes.create_channel(
        {"name": "VK", "platform": "vk", "target": "-111", "token": "vk1.a." + "x" * 40},
        db=db, user=U_ADM)
    return a["data"]["id"], b["data"]["id"]


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_post_crud_and_overrides():
    async def body(db):
        ca, cb = await _mk_channels(db)
        r = await pub_routes.create_post(
            {"body_md": "**Привет** мир",
             "media": [{"type": "photo", "url": "/agropilot/files/7/f.png"}],
             "channel_ids": [ca, cb],
             "overrides": {str(cb): "Свой текст VK"}},
            db=db, user=U_MGR)
        p = r["data"]
        assert p["status"] == "draft"
        assert p["media"][0]["url"].startswith("https://")  # относительный достроен
        assert p["media"][0]["url"].endswith("/agropilot/files/7/f.png")
        ov = {c["channel_id"]: c["body_override"] for c in p["channels"]}
        assert ov[cb] == "Свой текст VK" and ov[ca] is None
        # PATCH: замена набора каналов убирает отвязанные строки
        r = await pub_routes.update_post(p["id"], {"channel_ids": [ca]},
                                         db=db, user=U_MGR)
        assert [c["channel_id"] for c in r["data"]["channels"]] == [ca]
        # список и получение
        lst = (await pub_routes.list_posts(db=db, user=U_ENG))["data"]
        assert len(lst) == 1
        got = (await pub_routes.get_post(p["id"], db=db, user=U_ENG))["data"]
        assert got["channels"][0]["status"] == "pending"
        # валидация
        for bad in ({"body_md": ""}, {"body_md": "x" * 20001}):
            try:
                await pub_routes.create_post({**bad, "channel_ids": []},
                                             db=db, user=U_MGR)
                assert False
            except ValidationError:
                pass
        try:
            await pub_routes.create_post(
                {"body_md": "ok", "channel_ids": [ca], "media": [{"type": "video", "url": "http://x"}]},
                db=db, user=U_MGR)
            assert False
        except ValidationError:
            pass
        # удаление черновика
        d = await pub_routes.delete_post(p["id"], db=db, user=U_ADM)
        assert d["data"]["deleted"] == p["id"]
        assert (await pub_routes.list_posts(db=db, user=U_ADM))["data"] == []
    _run(body)


def test_roles_and_frozen_channel():
    async def body(db):
        ca, _ = await _mk_channels(db)
        try:
            await pub_routes.create_post({"body_md": "x", "channel_ids": [ca]},
                                         db=db, user=U_ENG)
            assert False, "engineer не должен создавать"
        except Exception as e:
            assert type(e).__name__ == "ForbiddenError"
        # заморозили канал — привязка падает валидацией
        await pub_routes.update_channel(ca, {"status": "frozen"}, db=db, user=U_ADM)
        try:
            await pub_routes.create_post({"body_md": "x", "channel_ids": [ca]},
                                         db=db, user=U_MGR)
            assert False
        except ValidationError:
            pass
    _run(body)


def test_publish_flows():
    async def body(db):
        ca, cb = await _mk_channels(db)
        p = (await pub_routes.create_post(
            {"body_md": "текст", "channel_ids": [ca, cb],
             "overrides": {str(cb): "VK-текст"}}, db=db, user=U_MGR))["data"]

        # 1) движок ответил итогами — проксируем как есть (мок держим на оба
        # вызова publish: повторная публикация тоже идёт в движок)
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(req)
            return _FakeResp(json.dumps(
                {"ok": True, "data": {"post_id": str(p["id"]), "post_status": "partial",
                                      "results": [{"channel_id": ca, "status": "ok"}]}}
            ).encode())

        orig = pub_routes.urllib.request.urlopen
        pub_routes.urllib.request.urlopen = fake_urlopen
        try:
            r = await pub_routes.publish_post(p["id"], {}, db=db, user=U_ADM)
            assert r["ok"] is True and r["data"]["post_status"] == "partial"
            # заголовок токена и тело запроса к движку
            assert calls and calls[0].get_header("X-pub-token") == pub_routes.PUB_ENGINE_TOKEN
            assert json.loads(calls[0].data) == {"post_id": p["id"]}

            # зона ответственности бэкенда: строки выставлены в pending (итоги
            # пишет движок n8n — мок их не трогает), override сохранён
            rows = (await db.execute(text(
                "SELECT channel_id, status, body_override FROM pub_post_channels "
                "WHERE post_id = :p"), {"p": p["id"]})).all()
            st = {cid: (s, bo) for cid, s, bo in rows}
            assert st[ca][0] == "pending" and st[cb][0] == "pending"
            assert st[cb][1] == "VK-текст" and st[ca][1] is None

            # повторная публикация одного канала: он снова pending
            # (первый прогон оставил publishing — сдвигаем updated_at назад,
            # гард «уже публикуется» пропускает только зависшие >3 мин)
            await db.execute(text(
                "UPDATE pub_posts SET updated_at = datetime('now','-10 minutes') WHERE id = :p"),
                {"p": p["id"]})
            await db.commit()
            r2 = await pub_routes.publish_post(p["id"], {"channel_ids": [cb]},
                                               db=db, user=U_MGR)
            assert r2["ok"] is True and len(calls) == 2
        finally:
            pub_routes.urllib.request.urlopen = orig

        # 2) без каналов публикация невозможна
        p2 = (await pub_routes.create_post({"body_md": "без каналов", "channel_ids": []},
                                           db=db, user=U_MGR))["data"]
        try:
            await pub_routes.publish_post(p2["id"], {}, db=db, user=U_ADM)
            assert False
        except ValidationError:
            pass
    _run(body)


def test_publish_engine_unreachable():
    async def body(db):
        import urllib.error
        ca, _ = await _mk_channels(db)
        p = (await pub_routes.create_post({"body_md": "x", "channel_ids": [ca]},
                                          db=db, user=U_ADM))["data"]

        def fake_urlopen(req, timeout=None):
            raise urllib.error.URLError("connection refused")

        orig = pub_routes.urllib.request.urlopen
        pub_routes.urllib.request.urlopen = fake_urlopen
        try:
            try:
                await pub_routes.publish_post(p["id"], {}, db=db, user=U_ADM)
                assert False
            except ConflictError as e:
                assert "недоступен" in str(e)
        finally:
            pub_routes.urllib.request.urlopen = orig
        row = (await db.execute(text("SELECT status, last_error FROM pub_posts WHERE id=:p"),
                                {"p": p["id"]})).first()
        assert row[0] == "failed" and "connection refused" in row[1]
    _run(body)


def test_schedule_lifecycle():
    async def body(db):
        from datetime import datetime, timezone, timedelta
        ca, _ = await _mk_channels(db)
        fut = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        # создание сразу запланированным
        p = (await pub_routes.create_post(
            {"body_md": "план", "channel_ids": [ca], "scheduled_at": fut},
            db=db, user=U_MGR))["data"]
        assert p["status"] == "scheduled" and p["scheduled_at"]
        # прошлое время нельзя
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        try:
            await pub_routes.update_post(p["id"], {"scheduled_at": past},
                                         db=db, user=U_MGR)
            assert False
        except ValidationError:
            pass
        # naive-время трактуется как DEFAULT_TZ (Europe/Moscow) — не падает
        r = await pub_routes.update_post(p["id"], {"scheduled_at": "2030-01-01 09:00"},
                                         db=db, user=U_MGR)
        assert r["data"]["status"] == "scheduled" and r["data"]["scheduled_at"]
        # sqlite-тест не сохраняет tz-суффикс (на проде timestamptz отдаёт offset)
        # снятие расписания → draft
        r = await pub_routes.update_post(p["id"], {"scheduled_at": None},
                                         db=db, user=U_MGR)
        assert r["data"]["status"] == "draft" and not r["data"]["scheduled_at"]
        # повторное планирование + удаление запланированного
        await pub_routes.update_post(p["id"], {"scheduled_at": fut}, db=db, user=U_MGR)
        d = await pub_routes.delete_post(p["id"], db=db, user=U_ADM)
        assert d["data"]["deleted"] == p["id"]
    _run(body)


def test_publish_clears_schedule():
    async def body(db):
        from datetime import datetime, timezone, timedelta
        ca, _ = await _mk_channels(db)
        fut = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        p = (await pub_routes.create_post(
            {"body_md": "x", "channel_ids": [ca], "scheduled_at": fut},
            db=db, user=U_ADM))["data"]

        def fake_urlopen(req, timeout=None):
            return _FakeResp(json.dumps(
                {"ok": True, "data": {"post_id": str(p["id"]), "post_status": "done",
                                      "results": []}}).encode())

        orig = pub_routes.urllib.request.urlopen
        pub_routes.urllib.request.urlopen = fake_urlopen
        try:
            r = await pub_routes.publish_post(p["id"], {}, db=db, user=U_ADM)
            assert r["ok"] is True
        finally:
            pub_routes.urllib.request.urlopen = orig
        row = (await db.execute(text("SELECT status, scheduled_at FROM pub_posts WHERE id=:p"),
                                {"p": p["id"]})).first()
        assert row[0] == "publishing" and row[1] is None  # расписание снято
        # правка опубликованного запрещена
        from backend.common.errors import ConflictError as CE
        try:
            await pub_routes.update_post(p["id"], {"body_md": "y"}, db=db, user=U_ADM)
            assert False
        except CE:
            pass
    _run(body)
