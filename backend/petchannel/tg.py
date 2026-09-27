# backend/petchannel/tg.py -- §42: клиент Bot API отдельного бота ПЕТРУШКИ
#
# Отдельный токен (PETRUSHKA_TG_BOT_TOKEN) -- webhook несовместим с polling
# бота JARVIS_MONITOR на том же токене (решение D7). Секреты -- только в .env
# сервера, в репо и .env.example -- имена и плейсхолдеры.

import json
import os
import urllib.request


def tg_enabled() -> bool:
    return bool(os.environ.get("PETRUSHKA_TG_BOT_TOKEN", "").strip())


def bot_username() -> str:
    return os.environ.get("PETRUSHKA_TG_BOT_NAME", "PETRUHKA_A_bot")


def send_message(chat_id: str, text: str) -> bool:
    token = os.environ.get("PETRUSHKA_TG_BOT_TOKEN", "").strip()
    if not token or not chat_id:
        return False
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": (text or "")[:4000]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8")).get("ok", False)
    except Exception:
        return False
