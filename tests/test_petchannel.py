# tests/test_petchannel.py -- О6 (§42): маски, коды привязки, команды webhook

import asyncio
import os
from datetime import datetime, timedelta, timezone

os.environ["EMBED_PROVIDER"] = "fake"
os.environ["QDRANT_URL"] = ""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from backend.petchannel.models import (  # noqa: E402
    Base, ChannelBinding, code_expires, gen_bind_code, parse_mask,
    render_mask, session_key,
)
from backend.petchannel.routes import parse_answer_command, parse_mask_command  # noqa: E402

NOW = datetime(2026, 9, 27, 15, 0, tzinfo=timezone.utc)


def _run_with_session(coro_fn):
    async def wrap():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            return await coro_fn(session)

    return asyncio.run(wrap())


# ---------- маски ----------

def test_parse_and_render_mask():
    assert parse_mask("digest,questions") == {"digest", "questions"}
    assert parse_mask("digest,мусор,") == {"digest"}
    assert parse_mask("") == set()
    assert render_mask(["insights", "digest", "мусор"]) == "digest,insights"


def test_session_key_pattern():
    assert session_key("u1", "12345") == "u1:telegram:12345"


def test_bind_code_format_and_expiry():
    code = gen_bind_code()
    assert len(code) == 6 and code.isdigit()
    assert code_expires(NOW) == NOW + timedelta(minutes=15)


# ---------- команды webhook ----------

def test_parse_answer_command():
    assert parse_answer_command("/ans 42 Мой ответ") == (42, "Мой ответ")
    assert parse_answer_command("/ans 7 многострочный\nответ") == (7, "многострочный\nответ")
    assert parse_answer_command("/ans 42") is None        # без текста
    assert parse_answer_command("просто текст") is None
    assert parse_answer_command("/ans abc текст") is None


def test_parse_mask_command():
    assert parse_mask_command("/mask") == (None, None)
    assert parse_mask_command("/mask digest on") == ("digest", "on")
    assert parse_mask_command("/mask questions off") == ("questions", "off")
    assert parse_mask_command("не команда") is None


# ---------- webhook: привязка по коду и игнор посторонних ----------

def _update(chat_id, text):
    return {"message": {"chat": {"id": chat_id}, "text": text}}


def test_webhook_unbound_chat_ignored():
    """DoD О6-2: текст от постороннего chat_id не попадает в orchChat --
    handle_update возвращает '' без вызова ассистента."""
    async def scenario(session):
        from unittest.mock import patch

        from backend.petchannel.routes import handle_update

        with patch("backend.orchestrator.routes.orchestrator_chat") as orch:
            reply = await handle_update(session, _update(999, "привет, взломщик"))
            return reply, orch.called

    reply, called = _run_with_session(scenario)
    assert reply == "" and called is False


def test_webhook_bind_by_code_and_mask_toggle():
    async def scenario(session):
        from backend.petchannel.routes import handle_update

        # 1) пользователь взял код в вебе
        row = ChannelBinding(user_id="u1", channel="telegram",
                             bind_code="123456",
                             bind_code_expires=NOW + timedelta(minutes=10))
        session.add(row)
        await session.commit()
        # 2) прислал его боту с чужого (своего) chat_id
        r1 = await handle_update(session, _update(777, "/start 123456"))
        await session.refresh(row)
        # 3) испорченный код больше не работает
        r2 = await handle_update(session, _update(888, "/start 123456"))
        # 4) подписки через /mask
        r3 = await handle_update(session, _update(777, "/mask digest on"))
        await session.refresh(row)
        # 5) посторонний теперь всё ещё игнор (chat 888 не привязан)
        r4 = await handle_update(session, _update(888, "ещё раз"))
        return r1, row, r2, r3, r4

    r1, row, r2, r3, r4 = _run_with_session(scenario)
    assert "Привязка выполнена" in r1
    assert row.chat_id == "777" and row.verified_at is not None
    assert row.bind_code is None  # код одноразовый
    assert "не найден" in r2      # повтор кода отклонён
    assert "digest" in r3 and "digest" in row.masks()
    assert r4 == ""               # посторонний игнор


def test_webhook_answer_command_writes_unified_log():
    """DoD О6-3: ответ из TG пишется в тот же agent_questions."""
    async def scenario(session):
        from backend.petchannel.models import Base as PCBase  # noqa: F401
        from backend.petchannel.routes import handle_update
        from backend.questions.models import AgentQuestion, Base as QBase, compute_expires

        # обе таблицы в одной сессии: создаём их в одном engine нельзя,
        # поэтому -- отдельная таблица через raw SQL в этой же sqlite-БД
        await session.execute(__import__("sqlalchemy").text(
            "CREATE TABLE IF NOT EXISTS agent_questions ("
            "id INTEGER PRIMARY KEY, ts TEXT, user_id TEXT, question TEXT, "
            "context_ref TEXT, round_id TEXT, status TEXT, expires_at TEXT, "
            "presented_at TEXT, answered_at TEXT, answer_text TEXT, insight_id INTEGER)"))
        await session.commit()

        row = ChannelBinding(user_id="u1", channel="telegram", chat_id="777",
                             verified_at=NOW)
        session.add(row)
        q = AgentQuestion(user_id="u1", question="Какая норма полива?",
                          status="asked",
                          expires_at=compute_expires(datetime.now(timezone.utc)))
        session.add(q)
        await session.commit()
        await session.refresh(q)

        r = await handle_update(session, _update(777, f"/ans {q.id} 550 м3/га"))
        await session.refresh(q)
        return r, q

    r, q = _run_with_session(scenario)
    assert "записан" in r
    assert q.status == "answered" and q.answer_text == "550 м3/га"


def test_webhook_answer_expired_question_rejected():
    async def scenario(session):
        from datetime import datetime as dt, timezone as tz

        from backend.petchannel.routes import handle_update
        from backend.questions.models import AgentQuestion, compute_expires

        await session.execute(__import__("sqlalchemy").text(
            "CREATE TABLE IF NOT EXISTS agent_questions ("
            "id INTEGER PRIMARY KEY, ts TEXT, user_id TEXT, question TEXT, "
            "context_ref TEXT, round_id TEXT, status TEXT, expires_at TEXT, "
            "presented_at TEXT, answered_at TEXT, answer_text TEXT, insight_id INTEGER)"))
        await session.commit()

        session.add(ChannelBinding(user_id="u1", channel="telegram", chat_id="777",
                                   verified_at=dt.now(tz.utc)))
        q = AgentQuestion(
            user_id="u1", question="Старый вопрос", status="asked",
            expires_at=dt.now(tz.utc) - timedelta(hours=1))  # уже истёк
        session.add(q)
        await session.commit()
        await session.refresh(q)

        r = await handle_update(session, _update(777, f"/ans {q.id} ответ"))
        await session.refresh(q)
        return r, q

    r, q = _run_with_session(scenario)
    assert "истёк" in r
    assert q.status == "expired" and q.answer_text is None
