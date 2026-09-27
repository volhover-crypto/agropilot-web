# backend/connectors/base.py -- интерфейс коннектора (§39.1)
#
# Коннектор -- модуль backend/connectors/<name>.py, регистрируется в registry.py.
# Новый источник = строка в sources (+ при нестандартной механике -- новый
# коннектор в реестре), правок роутеров не требуется.

from typing import Any, Optional


class Connector:
    """Базовый класс: ключи реестра и конверсия «сырых» материалов в наблюдения.

    fetch() возвращает материалы {title, summary?, url?, published_at?};
    normalize() превращает материал в наблюдение -- ВСЕГДА с source_id
    (правило §39.2: наблюдение без source_id в UX-контур не попадает).
    """

    key: str = ""          # ключ реестра, напр. 'arxiv'
    kind: str = "web"      # rss | api | web | kb  (классификация механики)
    auth: str = "none"     # none | apikey | oauth

    def fetch(self, source: Any, params: Optional[dict] = None) -> list[dict]:
        raise NotImplementedError

    def normalize(self, raw: dict, source: Any) -> dict:
        return {
            "source_id": getattr(source, "id", None),
            "connector": self.key,
            "title": (raw.get("title") or "")[:200],
            "summary": (raw.get("summary") or None),
            "url": raw.get("url") or None,
            "published_at": raw.get("published_at"),
        }
