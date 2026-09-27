# backend/connectors/arxiv.py -- arXiv API коннектор (§39.1, auth: none)
#
# API: http://export.arxiv.org/api/query (Atom). Запрос строится из
# keywords источника; референс паттерна -- OpenAlex-коннектор Octop.

import re
import xml.etree.ElementTree as ET
from typing import Any, Optional
from urllib.parse import quote

from backend.connectors.base import Connector

_API_URL = "http://export.arxiv.org/api/query"
_ATOM = "{http://www.w3.org/2005/Atom}"


def build_query_url(keywords: list, max_results: int = 20) -> str:
    """search_query=all:"kw1"+AND+all:"kw2" -- как в веб-поиске arXiv."""
    terms = [f'all:"{quote(str(k))}"' for k in (keywords or []) if str(k).strip()]
    if not terms:
        search = "all:agriculture"  # пустые keywords -- нейтральный запрос
    else:
        search = "+AND+".join(terms)
    return f"{_API_URL}?search_query={search}&sortBy=submittedDate&max_results={max_results}"


def parse_arxiv_atom(data: bytes | str) -> list[dict]:
    """Atom-ответ -> материалы {title, summary, url, published_at} (пару чистую,
    тестируемо на фикстурах)."""
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    root = ET.fromstring(data)
    items = []
    for entry in root.iter(f"{_ATOM}entry"):
        title = (entry.findtext(f"{_ATOM}title") or "").strip()
        if not title:
            continue
        summary = (entry.findtext(f"{_ATOM}summary") or "").strip()
        link_el = entry.find(f"{_ATOM}id")
        pub = (entry.findtext(f"{_ATOM}published") or "").strip() or None
        items.append({
            "title": re.sub(r"\s+", " ", title)[:200],
            "summary": re.sub(r"\s+", " ", summary)[:1000] or None,
            "url": (link_el.text or "").strip() if link_el is not None else None,
            "published_at": pub,
        })
    return items


class ArxivConnector(Connector):
    key = "arxiv"
    kind = "api"
    auth = "none"

    def fetch(self, source: Any, params: Optional[dict] = None) -> list[dict]:
        import urllib.request

        url = build_query_url(source.keywords or [], max_results=(params or {}).get("max_results", 20))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AgroPILOT-A1"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return parse_arxiv_atom(r.read())
