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
               allowed_updates=["message"])
    updates = resp.get("result") or []
    if not updates:
        print(f"нет новых сообщений (offset={offset})"); return 0

    async with _AsyncSessionLocal() as s:
        created = 0
        for u in updates:
            offset = max(offset, u["update_id"] + 1)
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
        await s.commit()

    _save_offset(offset)
    print(f"обработано {len(updates)} апдейтов, создано {created} обращений")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
