# backend/news/collectors.py -- сборщики материалов для A1 (§20)
#
# telegram-каналы: публичная веб-версия t.me/s/<channel> (без Bot API),
# rss: xml.etree, site: <title> страницы как минимум.
# Без внешних зависимостей (urllib + stdlib).

import re
import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import urlparse


def _strip(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def collect_telegram_web(url: str) -> list[dict]:
    """Публичный TG-канал через t.me/s/<name>. Возвращает [{title, url, published_at?}]."""
    import urllib.request

    parsed = urlparse(url)
    name = parsed.path.strip("/").split("/")[-1]
    if not name or name == "s":
        raise ValueError(f"не могу извлечь имя канала из {url}")
    page_url = f"https://t.me/s/{name}"
    req = urllib.request.Request(page_url, headers={"User-Agent": "Mozilla/5.0 AgroPILOT-A1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="replace")

    items = []
    # Каждый блок текста сообщения + ближайший data-post ПЕРЕД ним
    # (разметка t.me сильно вложенная, парсить блоки целиком ненадёжно).
    for tm in re.finditer(
        r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html, re.S
    ):
        text = _strip(tm.group(1))
        if not text:
            continue
        post_m = None
        for pm in re.finditer(r'data-post="([^"]+)"', html[: tm.start()]):
            post_m = pm
        post_id = post_m.group(1) if post_m else name
        items.append({
            "title": text[:200],
            "summary": text[:1000] if len(text) > 200 else None,
            "url": f"https://t.me/{post_id}",
        })
    return items


def collect_rss(url: str) -> list[dict]:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AgroPILOT-A1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read()
    root = ET.fromstring(data)

    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        if not title:
            continue
        items.append({
            "title": title[:200],
            "summary": (it.findtext("description") or "").strip()[:1000] or None,
            "url": (it.findtext("link") or "").strip() or None,
        })
    # atom
    if not items:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for it in root.iter("{http://www.w3.org/2005/Atom}entry"):
            title = (it.findtext("a:title", default="", namespaces=ns) or "").strip()
            if title:
                link_el = it.find("a:link", ns)
                items.append({
                    "title": title[:200],
                    "summary": None,
                    "url": link_el.get("href") if link_el is not None else None,
                })
    return items


def collect_site(url: str) -> list[dict]:
    """Минимум для сайта: один <title> страницы."""
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AgroPILOT-A1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="replace")[:200_000]
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if not m:
        return []
    return [{"title": _strip(m.group(1))[:200], "summary": None, "url": url}]


def collect(source_type: str, url: str) -> list[dict]:
    """Диспетчер сборщиков. Telegram-тип определяется и по типу, и по домену url."""
    is_tme = "t.me/" in url or "telegram.me/" in url
    if source_type == "telegram" or is_tme:
        return collect_telegram_web(url)
    if source_type == "rss":
        return collect_rss(url)
    return collect_site(url)
