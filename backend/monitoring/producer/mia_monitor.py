#!/usr/bin/env python3
# backend/monitoring/producer/mia_monitor.py -- поставщик наблюдений MIA (§17.1, вариант A)
#
# Замена старого gbrain-скрипта: пишет ТОЛЬКО в agropilot.public.field_alerts --
# единственную таблицу, которую читает ERP (/v1/monitoring, контракт §17).
# Чинит дефекты аудита D1-D9 (docs/MONITORING_PRODUCER_AUDIT.md):
#   D1/D2 -- INSERT строго по схеме таблицы, плейсхолдеры 1:1
#   D3   -- ошибки не глотаются: лог + ненулевой код возврата
#   D4   -- база только agropilot (никакого gbrain)
#   D5   -- Telegram опционален, включается переменной окружения
#   D6   -- notify_agents не пишем (колонки нет в этой таблице)
#   D7   -- дедупликация по ключу перед вставкой (dedup_minutes)
#   D8   -- все секреты в окружении, в коде их нет
#   D9   -- MIA_MODE: info (все наблюдения) | critical (только пороговые)
#
# Запуск (cron или systemd timer, например раз в час):
#   venv/bin/python -m backend.monitoring.producer.mia_monitor
#
# Переменные окружения:
#   DATABASE_URL      --postgresql://...  (обязательно; БД = agropilot)
#   MOCK_BASE_URL     -- базовый URL мок-сервиса (http://127.0.0.1:3001)
#   MIA_MODE          -- info | critical (по умолчанию info)
#   MIA_DEDUP_MINUTES -- окно дедупликации в минутах (по умолчанию 60)
#   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID -- если заданы, шлём critical-алерты в TG

import asyncio
import json
import logging
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

import asyncpg

log = logging.getLogger("mia_monitor")

VALID_LEVELS = ("info", "ok", "warning", "critical")

# Пороги срабатывания: endpoint -> (категория, параметр, единица, правила)
# Правило: ключ поля в ответе мока -> (мин, уровень_ниже, макс, уровень_выше)
THRESHOLDS = {
    "/weather": {
        "category": "weather",
        "rules": {
            "temperature": {"min": 5.0, "below": "warning", "max": 35.0, "above": "critical"},
            "wind_speed":  {"min": None, "below": None,     "max": 15.0, "above": "warning"},
            "humidity":    {"min": 25.0, "below": "warning", "max": None, "above": None},
        },
    },
    "/weather/frost": {
        "category": "frost",
        "rules": {
            "temperature": {"min": 0.0, "below": "critical", "max": None, "above": None},
        },
    },
    "/ndvi": {
        "category": "ndvi",
        "rules": {
            "ndvi": {"min": 0.3, "below": "warning", "max": None, "above": None},
        },
    },
    "/prices": {
        "category": "prices",
        "rules": {
            "price": {"min": None, "below": None, "max": None, "above": None, "any": "info"},
        },
    },
    "/news": {
        "category": "news",
        "rules": {
            "title": {"any": "info"},
        },
    },
}


def fetch_json(base_url: str, path: str, timeout: float = 10.0):
    url = base_url.rstrip("/") + path
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def analyze(endpoint: str, payload: dict) -> list[dict]:
    """Превращает ответ мока в список наблюдений по правилам THRESHOLDS."""
    spec = THRESHOLDS[endpoint]
    category = spec["category"]
    out = []
    mode = os.environ.get("MIA_MODE", "info").strip().lower()

    items = payload if isinstance(payload, list) else [payload]
    for item in items:
        if not isinstance(item, dict):
            continue
        for field, rule in spec["rules"].items():
            if field not in item:
                continue
            raw = item.get(field)
            value = _num(raw)
            level, message = None, None
            unit = item.get("unit") or ""

            if rule.get("any"):
                level = rule["any"]
                message = f"{category}/{field}: {raw}"
            elif value is not None:
                if rule.get("min") is not None and value < rule["min"]:
                    level = rule["below"]
                    message = f"{field}={value} ниже порога {rule['min']}"
                elif rule.get("max") is not None and value > rule["max"]:
                    level = rule["above"]
                    message = f"{field}={value} выше порога {rule['max']}"
                else:
                    level = "ok"
                    message = f"{field}={value} в норме"
            else:
                continue

            if mode == "critical" and level in ("info", "ok"):
                continue
            if level not in VALID_LEVELS:
                continue

            out.append({
                "source": "mia_monitor",
                "category": category,
                "parameter": str(item.get("title") or item.get("parameter") or field)[:128],
                "value": value,
                "unit": str(unit)[:16],
                "level": level,
                "message": message,
                "dedup_key": f"{category}:{item.get('id', field)}:{field}",
            })
    return out


async def send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as r:
            if r.status != 200:
                log.warning("Telegram ответил %s", r.status)
    except Exception as e:
        # D3/D5: сбой TG не роняет запись в БД, но и не глотается молча
        log.warning("Telegram send failed: %s", e)


async def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        log.error("DATABASE_URL не задан")
        return 2
    # asyncpg-драйверу нужен чистый postgresql:// (без +asyncpg из SQLAlchemy-строки)
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if "/agropilot" not in db_url:
        log.error("DATABASE_URL должен указывать на базу agropilot, получено: %s",
                  db_url.split("@")[-1])
        return 2

    base_url = os.environ.get("MOCK_BASE_URL", "http://127.0.0.1:3001").strip()
    dedup_minutes = int(os.environ.get("MIA_DEDUP_MINUTES", "60"))

    observations: list[dict] = []
    errors = 0
    for endpoint in THRESHOLDS:
        try:
            payload = fetch_json(base_url, endpoint)
            observations.extend(analyze(endpoint, payload))
        except Exception as e:
            errors += 1
            log.error("Не удалось получить %s%s: %s", base_url, endpoint, e)
    if errors == len(THRESHOLDS):
        log.error("Все источники недоступны -- запись в БД не выполнялась")
        return 1

    if not observations:
        log.info("Нет наблюдений для записи")
        return 0

    conn = await asyncpg.connect(db_url)
    try:
        inserted = 0
        since = datetime.now(timezone.utc) - timedelta(minutes=dedup_minutes)
        for obs in observations:
            # D7: дедупликация -- пропускаем, если такое наблюдение уже есть
            dup = await conn.fetchval(
                """SELECT id FROM field_alerts
                   WHERE source = $1 AND category = $2 AND parameter = $3
                     AND level  = $4 AND created_at >= $5
                   LIMIT 1""",
                obs["source"], obs["category"], obs["parameter"], obs["level"], since,
            )
            if dup is not None:
                continue
            await conn.execute(
                """INSERT INTO field_alerts
                       (source, category, parameter, value, unit, level, message, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, now())""",
                obs["source"], obs["category"], obs["parameter"],
                obs["value"], obs["unit"] or None, obs["level"], obs["message"],
            )
            inserted += 1
            if obs["level"] == "critical":
                tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
                tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "")
                if tg_token and tg_chat:
                    await send_telegram(
                        tg_token, tg_chat,
                        f"[AgroPILOT/{obs['category']}] {obs['message']}",
                    )
        log.info("Записано %d наблюдений (из %d, дедуп %d мин), ошибок источников: %d",
                 inserted, len(observations), dedup_minutes, errors)
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
