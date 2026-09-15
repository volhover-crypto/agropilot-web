# backend/clients/egrul.py -- реквизиты юрлица по ИНН из открытого ЕГРЮЛ
# (ТЗ v1.1 п. 8.4, решение владельца: вариант 2 — открытый источник).
#
# Неофициальный разбор JSON egrul.nalog.ru: без ключей, без гарантий;
# при смене формата -- честная ошибка, оператор вводит реквизиты руками.
# Запросы синхронные (urllib), оборачивать в asyncio.to_thread.

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

_BASE = "https://egrul.nalog.ru"
_UA = {"User-Agent": "Mozilla/5.0 AgroPILOT-EGRUL"}


class EgrulError(Exception):
    pass


def fetch_requisites_by_inn(inn: str) -> dict:
    """ИНН -> реквизиты. Бросает EgrulError при любой проблеме."""
    inn = (inn or "").strip()
    if not re.fullmatch(r"\d{10}(\d{2})?", inn):
        raise EgrulError("ИНН должен быть 10 или 12 цифр")

    # шаг 1: токен поиска
    data = urllib.parse.urlencode({"query": inn}).encode()
    req = urllib.request.Request(_BASE + "/", data=data, headers=_UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        meta = json.loads(r.read().decode("utf-8"))
    if meta.get("captchaRequired"):
        raise EgrulError("ЕГРЮЛ запросил капчу — попробуйте позже")
    token = meta.get("t")
    if not token:
        raise EgrulError(f"ЕГРЮЛ не выдал токен поиска: {str(meta)[:120]}")

    # шаг 2: JSON-результат
    req = urllib.request.Request(_BASE + "/search-result/" + token, headers=_UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        result = json.loads(r.read().decode("utf-8"))
    rows = result.get("rows") or []
    if not rows:
        raise EgrulError("в ЕГРЮЛ нет записей по этому ИНН")
    row = rows[0]
    if row.get("i", "").strip() != inn:
        # точное совпадение не обязательно первый элемент
        row = next((x for x in rows if x.get("i", "").strip() == inn), row)

    return {
        "name": (row.get("n") or row.get("c") or "")[:300],
        "short_name": (row.get("c") or "")[:200] or None,
        "ogrn": (row.get("o") or "")[:15],
        "kpp": (row.get("p") or "")[:10],
        "reg_date": (row.get("r") or "")[:20],
        "ceo": (row.get("g") or "")[:200] or None,
        "region": (row.get("rn") or "")[:100] or None,
        "inn": inn,
        "source": "egrul.nalog.ru",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
