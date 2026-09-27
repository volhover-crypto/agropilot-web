# backend/connectors/rss.py -- RSS/Atom коннектор (обёртка news/collectors)

from typing import Any, Optional

from backend.connectors.base import Connector
from backend.news.collectors import collect_rss


class RssConnector(Connector):
    key = "rss"
    kind = "rss"
    auth = "none"

    def fetch(self, source: Any, params: Optional[dict] = None) -> list[dict]:
        return collect_rss(source.url)
