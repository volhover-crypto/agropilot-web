# backend/connectors/cyberleninka.py -- КиберЛенинка, веб-поиск (§39.1, auth: none)
#
# Best effort: разметка публичного поиска меняется, парсер толерантен
# (ссылки вида /article/n/<id> + текст внутри <a>); пустой результат --
# валидный исход (наблюдений нет), не ошибка.

import re
from html import unescape
from typing import Any, Optional
from urllib.parse import quote

from backend.connectors.base import Connector

_SEARCH_URL = "https://cyberleninka.ru/search?q="


def _strip(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def parse_cyberleninka_html(html: str, max_items: int = 20) -> list[dict]:
    """HTML страницы поиска -> материалы {title, url}. Ссылки на статьи --
    /article/n/<slug>; заголовок берём из текста <a> (или ближайшего h2)."""
    items, seen = [], set()
    for m in re.finditer(
        r'<a[^>]+href="([^"]*?/article/n/[^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I
    ):
        href, inner = m.group(1), m.group(2)
        title = _strip(inner)[:200]
        if not title:
            continue
        if href not in seen:
            seen.add(href)
            url = href if href.startswith("http") else f"https://cyberleninka.ru{href}"
            items.append({"title": title, "summary": None, "url": url})
        if len(items) >= max_items:
            break
    return items


class CyberleninkaConnector(Connector):
    key = "cyberleninka"
    kind = "web"
    auth = "none"

    def fetch(self, source: Any, params: Optional[dict] = None) -> list[dict]:
        import urllib.request

        q = " ".join(str(k) for k in (source.keywords or []) if str(k).strip())
        if not q:
            q = source.url  # fallback: строка поиска из url
        req = urllib.request.Request(
            _SEARCH_URL + quote(q), headers={"User-Agent": "Mozilla/5.0 AgroPILOT-A1"}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")[:500_000]
        return parse_cyberleninka_html(html)
