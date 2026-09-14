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

# Мок-сервис отдаёт готовый контракт наблюдения:
#   {source, category, parameter, value, unit, threshold_warning,
#    threshold_critical, norm, timestamp}
# Правило уровня:
#   - категории weather/frost: знаковые пороги (понижение температуры),
#     value <= threshold_critical -> critical; <= threshold_warning -> warning;
#   - остальные (ndvi/price/news): пороги по модулю отклонения,
#     |value| >= threshold_critical -> critical; >= threshold_warning -> warning.
SIGNED_CATEGORIES = {"weather", "frost"}

# Эндпоинты мока -> категория (для контроля; категорию берём из самого ответа)
ENDPOINTS = {
    "/weather":      "weather",
    "/weather/frost": "frost",
    "/ndvi":         "ndvi",
    "/prices":       "price",
    "/news":         "news",
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


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _level_for(item: dict, value: float) -> str:
    tw = _num(item.get("threshold_warning"))
    tc = _num(item.get("threshold_critical"))
    signed = str(item.get("category", "")).lower() in SIGNED_CATEGORIES
    if signed:
        if tc is not None and value <= tc:
            return "critical"
        if tw is not None and value <= tw:
            return "warning"
        return "ok"
    mag = abs(value)
    if tc is not None and mag >= tc:
        return "critical"
    if tw is not None and mag >= tw:
        return "warning"
    return "ok"


def analyze(endpoint: str, payload) -> list[dict]:
    """Мок-контракт -> наблюдения field_alerts (схема §17).

    Один элемент ответа = одно наблюдение. level по threshold_warning/
    threshold_critical из самого ответа (знаково для weather/frost,
    по модулю для ndvi/price/news).
    """
    mode = os.environ.get("MIA_MODE", "info").strip().lower()
    out = []
    items = payload if isinstance(payload, list) else [payload]
    for item in items:
        if not isinstance(item, dict):
            continue
        value = _num(item.get("value"))
        if value is None:
            continue
        category = str(item.get("category") or ENDPOINTS.get(endpoint, "system")).lower()
        level = _level_for(item, value)
        if mode == "critical" and level in ("info", "ok"):
            continue
        if level not in VALID_LEVELS:
            continue
        parameter = str(item.get("parameter") or category)[:128]
        out.append({
            "source": str(item.get("source") or "mia_monitor")[:64],
            "category": category[:32],
            "parameter": parameter,
            "value": value,
            "unit": str(item.get("unit") or "")[:16],
            "level": level,
            "message": f"{parameter} = {value} {item.get('unit', '')} (норма: {item.get('norm', '—')})",
            "dedup_key": f"{category}:{parameter}:{level}",
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
    for endpoint in ENDPOINTS:
        try:
            payload = fetch_json(base_url, endpoint)
            observations.extend(analyze(endpoint, payload))
        except Exception as e:
            errors += 1
            log.error("Не удалось получить %s%s: %s", base_url, endpoint, e)
    if errors == len(ENDPOINTS):
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
