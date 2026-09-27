# backend/connectors/legacy.py -- обёртки существующих сборщиков A1 (§20)
#
# telegram-web: публичная веб-версия t.me/s/<name>; site: <title> страницы.
# Поведение идентично news/collectors.py (паритет до перехода всех
# источников на явный connector).

from typing import Any, Optional

from backend.connectors.base import Connector
from backend.news.collectors import collect_site, collect_telegram_web


class TelegramWebConnector(Connector):
    key = "telegram-web"
    kind = "web"
    auth = "none"

    def fetch(self, source: Any, params: Optional[dict] = None) -> list[dict]:
        return collect_telegram_web(source.url)


class SiteConnector(Connector):
    key = "site"
    kind = "web"
    auth = "none"

    def fetch(self, source: Any, params: Optional[dict] = None) -> list[dict]:
        return collect_site(source.url)
