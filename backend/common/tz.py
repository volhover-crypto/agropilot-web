# backend/common/tz.py -- единая дисциплина таймзон (О4 ТЗ_ИНТЕГРАЦИЯ_OCTOP)
#
# Слой таймзон проекта (см. AGENTS.md):
#   БД и код -- UTC; расписания -- только с явной зоной (systemd/n8n --
#   Europe/Moscow); DEFAULT_TZ -- конфиг-зона BFF.
#
# Переменные окружения:
#   DEFAULT_TZ -- зона по умолчанию для «голых» времён без offset
#                 (default: Europe/Moscow). НЕ зона хоста.

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_TZ_NAME = os.getenv("DEFAULT_TZ", "Europe/Moscow")
DEFAULT_TZ = ZoneInfo(DEFAULT_TZ_NAME)


def now_utc() -> datetime:
    """Текущее время UTC (aware). Хранение и внутренние расчёты -- только оно."""
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    """Текущее время в DEFAULT_TZ (aware) -- для расписаний и человекочитаемых лиц."""
    return datetime.now(DEFAULT_TZ)


def parse_dt(value) -> datetime:
    """ISO 8601 -> aware datetime. Время без offset трактуется как DEFAULT_TZ
    (паттерн Octop «date:/cron: -> default_timezone», не зона хоста).
    ValueError -- невалидная строка."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=DEFAULT_TZ)
    return dt


def api_dt(value) -> str:
    """Время для отдачи в API: всегда ISO 8601 С offset. Наивное время
    трактуется как DEFAULT_TZ."""
    return parse_dt(value).astimezone(timezone.utc).isoformat()
