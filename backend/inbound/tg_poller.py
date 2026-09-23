#!/usr/bin/env python3
# backend/inbound/tg_poller.py -- коннектор входящих: Telegram -> inbounds (§22)
#
# Опрашивает getUpdates бота JARVIS_MONITOR раз в N минут (systemd timer),
# каждое входящее сообщение приватного чата становится обращением
# (channel=telegram). Дедуп по tg message_id (dedup_key).
# A4-классификация: включается TG_INBOX_AUTOCLASSIFY=1 (по умолчанию вкл).
#
# ВАЖНО: сервисные чаты (наш же бот шлёт сводки/алерты) фильтруются
# по is_bot и по TELEGRAM_CHAT_ID (чат владельца не превращается в лиды).
#
# Запуск: venv/bin/python -m backend.inbound.tg_poller (из /opt/agropilot-web)

import asyncio
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import select  # §35: нужен на уровне модуля (_sla_check/_handle_approval_callback)

STATE_FILE = "/opt/agropilot-data/tg_poller_offset.json"


def _tg(method: str, token: str, **params) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(params).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _load_offset() -> int:
    try:
        with open(STATE_FILE) as f:
            return int(json.load(f).get("offset", 0))
    except Exception:
        return 0


def _save_offset(offset: int) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({"offset": offset}, f)


async def main() -> int:
    from sqlalchemy import select
    from backend.inbound.models import Inbound
    from backend.common.deps import _AsyncSessionLocal

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN не задан"); return 2
    owner_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    autocal = os.environ.get("TG_INBOX_AUTOCLASSIFY", "1") == "1"

    offset = _load_offset()
    resp = _tg("getUpdates", token, offset=offset, timeout=0,
               allowed_updates=["message", "callback_query"])
    updates = resp.get("result") or []
    if not updates:
        # §35: даже без апдейтов проверяем SLA согласований (таймер раз в 5 мин)
        async with _AsyncSessionLocal() as s:
            await _sla_check(s, token)
            await s.commit()
        print(f"нет новых апдейтов (offset={offset})"); return 0

    async with _AsyncSessionLocal() as s:
        created = 0
        for u in updates:
            offset = max(offset, u["update_id"] + 1)
            # §35: callback-кнопки согласования постов (чат владельца)
            cb = u.get("callback_query")
            if cb:
                await _handle_approval_callback(s, token, cb)
                continue
            m = u.get("message") or {}
            if m.get("from", {}).get("is_bot"):
                continue
            chat_id = str(m.get("chat", {}).get("id", ""))
            if owner_chat and chat_id == owner_chat:
                continue  # служебный чат владельца
            text = (m.get("text") or "").strip()
            if not text:
                continue
            frm = m.get("from", {})
            contact = " ".join(filter(None, [
                frm.get("first_name"), frm.get("last_name"),
                "@" + frm["username"] if frm.get("username") else "",
            ])) or chat_id
            dedup = "tg:" + str(m.get("message_id"))
            dup = await s.execute(
                select(Inbound.id).where(Inbound.dedup_key == dedup).limit(1))
            if dup.first() is not None:
                continue
            s.add(Inbound(
                channel="telegram",
                contact=contact[:200],
                subject=(text.splitlines()[0] or "Обращение")[:500],
                body=text,
                received_at=datetime.now(timezone.utc),
                status="new",
                dedup_key=dedup,
                a4_class={},
            ))
            created += 1
        # §35: SLA по всем pending-согласованиям
        await _sla_check(s, token)
        await s.commit()

    _save_offset(offset)
    print(f"обработано {len(updates)} апдейтов, создано {created} обращений")
    return 0


# ---------- §35: согласование постов (callback-кнопки + SLA) ----------

BASE = os.environ.get("AGROPILOT_BASE", "http://127.0.0.1:5560/agropilot/api")


def _api_login() -> str:
    """Сервисный вход u7 (U7_PASSWORD в окружении) — действия кнопок от админа."""
    password = os.environ.get("U7_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("U7_PASSWORD не задан")
    data = json.dumps({"login": "u7", "password": password}).encode()
    req = urllib.request.Request(
        f"{BASE}/v1/auth/login", data=data,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())["data"]["access_token"]


def _api(tok: str, method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(body or {}).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {tok}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return True, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode())
        except Exception:
            return False, {"error": {"message": str(e)}}


def _edit_message(token: str, chat_id: str, message_id: int, note: str) -> None:
    """Дописать решение к сообщению согласования (кнопки убираются)."""
    try:
        _tg("editMessageText", token,
            chat_id=chat_id, message_id=message_id,
            text=f"Согласование завершено — {note}")
    except Exception:
        pass  # сообщение могло быть удалено; решение уже зафиксировано


async def _handle_approval_callback(s, token: str, cb: dict) -> None:
    """Кнопка согласования: ctnap:app|edt|def:{content_id}:{v}."""
    from backend.content.approvals import ContentApproval
    data = (cb.get("data") or "").strip()
    cb_id = cb.get("id")
    parts = data.split(":")
    def ok_answer(txt):
        # ответ на кнопку живёт секунды, а цикл poller — до 5 минут:
        # просроченный answerCallbackQuery даёт 400, это не ошибка бизнеса
        try:
            _tg("answerCallbackQuery", token, callback_query_id=cb_id, text=txt)
        except Exception:
            pass
        print(f"[approval] пост {cid}: {txt}", flush=True)
    if len(parts) != 4 or parts[0] != "ctnap":
        ok_answer("неизвестная кнопка"); return
    action, cid = parts[1], int(parts[2])
    appr = (await s.execute(
        select(ContentApproval)
        .where(ContentApproval.content_id == cid)
        .order_by(ContentApproval.id.desc()).limit(1))).scalars().first()
    if not appr:
        ok_answer("согласование не найдено"); return
    if appr.status != "pending":
        ok_answer(f"уже обработано ({appr.status})"); return

    try:
        tok = _api_login()
    except Exception as e:
        ok_answer(f"ошибка сервисного входа: {str(e)[:80]}"); return

    if action == "app":
        # кнопка согласует пост: in_review -> approved, затем публикация
        if not _api(tok, "PATCH", f"/v1/content/{cid}", {"status": "approved"})[0]:
            ok, resp = False, {"error": {"message": "не удалось согласовать пост"}}
        else:
            ok, resp = _api(tok, "POST", f"/v1/content/{cid}/publish",
                            {"channel_id": appr.channel_id})
        if ok:
            appr.status, appr.decided_by = "approved", "tg:owner"
            appr.decided_at = datetime.now(timezone.utc)
            ok_answer("✅ Опубликовано")
            _edit_message(token, str(cb.get("message", {}).get("chat", {}).get("id", "")),
                          appr.tg_message_id or 0, f"✅ ОПУБЛИКОВАНО (пост #{cid})")
        else:
            msg = ((resp.get("error") or {}).get("message") or "ошибка")[:140]
            ok_answer(f"публикация не удалась: {msg}")
    elif action == "edt":
        ok, resp = _api(tok, "PATCH", f"/v1/content/{cid}", {"status": "draft"})
        if ok:
            appr.status, appr.decided_by = "edited", "tg:owner"
            appr.decided_at = datetime.now(timezone.utc)
            ok_answer("✏️ Отправлено на правку")
            _edit_message(token, str(cb.get("message", {}).get("chat", {}).get("id", "")),
                          appr.tg_message_id or 0, f"✏️ НА ПРАВКЕ (пост #{cid})")
        else:
            msg = ((resp.get("error") or {}).get("message") or "ошибка")[:140]
            ok_answer(f"не удалось: {msg}")
    elif action == "def":
        ok, resp = _api(tok, "PATCH", f"/v1/content/{cid}", {"status": "approved"})
        if ok:
            appr.status, appr.decided_by = "deferred", "tg:owner"
            appr.decided_at = datetime.now(timezone.utc)
            ok_answer("⏰ Отложено — назначьте слот в календаре")
            _edit_message(token, str(cb.get("message", {}).get("chat", {}).get("id", "")),
                          appr.tg_message_id or 0, f"⏰ ОТЛОЖЕНО (пост #{cid}, слот — в календаре)")
        else:
            msg = ((resp.get("error") or {}).get("message") or "ошибка")[:140]
            ok_answer(f"не удалось: {msg}")
    else:
        ok_answer("неизвестное действие")


async def _sla_check(s, token: str) -> None:
    """§35: истёкшие pending -> expired; пост остаётся in_review (ручное решение)."""
    from backend.content.approvals import ContentApproval
    pend = (await s.execute(
        select(ContentApproval).where(ContentApproval.status == "pending"))).scalars().all()
    for a in pend:
        if a.deadline_at < datetime.now(timezone.utc):
            a.status, a.decided_by = "expired", "sla"
            a.decided_at = datetime.now(timezone.utc)
            if a.tg_message_id:
                _edit_message(token, os.environ.get("TELEGRAM_CHAT_ID", ""),
                              a.tg_message_id,
                              f"⏰ SLA ИСТЁК (пост #{a.content_id}) — решение в системе")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
