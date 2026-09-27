# backend/connectors/registry.py -- реестр коннекторов (§39.1)
#
# Единая точка: (1) выбор коннектора для источника -- явный ключ
# sources.connector или эвристика по типу/url (паритет news/collectors.py);
# (2) правило поставки данных §39.2 -- только активные источники.

from sqlalchemy import select

from backend.connectors.arxiv import ArxivConnector
from backend.connectors.base import Connector
from backend.connectors.cyberleninka import CyberleninkaConnector
from backend.connectors.legacy import SiteConnector, TelegramWebConnector
from backend.connectors.rss import RssConnector
from backend.news.models import Source

REGISTRY: dict[str, Connector] = {
    c.key: c
    for c in (
        RssConnector(),
        TelegramWebConnector(),
        SiteConnector(),
        ArxivConnector(),
        CyberleninkaConnector(),
    )
}


def resolve_connector(source) -> Connector:
    """Явный sources.connector побеждает; иначе эвристика уровня A1."""
    key = getattr(source, "connector", None)
    if key:
        if key not in REGISTRY:
            raise ValueError(
                f"unknown connector '{key}' for source {getattr(source, 'id', '?')}; "
                f"registry: {sorted(REGISTRY)}"
            )
        return REGISTRY[key]
    url = source.url or ""
    stype = source.type or ""
    if stype == "telegram" or "t.me/" in url or "telegram.me/" in url:
        return REGISTRY["telegram-web"]
    if stype == "rss":
        return REGISTRY["rss"]
    return REGISTRY["site"]


def is_eligible(source) -> bool:
    """§39.2 (правило «verified-only», адаптация ТЗ О2 п.3 к фактической
    статусной модели §13.1): данные поставляют только источники со статусом
    active И active=true. proposed/disabled/rejected данных не поставляют."""
    return bool(source.active) and source.status == "active"


def eligible_sources_stmt():
    """Готовый select активных источников (для POST /v1/news/scan и др.)."""
    return select(Source).where(Source.active.is_(True), Source.status == "active")


def fetch_for_source(source) -> list[dict]:
    """Материалы коннектора (без нормализации -- её делает вызывающий
    конвейер, чтобы прокинуть relevance/segment)."""
    return resolve_connector(source).fetch(source)
