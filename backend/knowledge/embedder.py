# backend/knowledge/embedder.py -- §41.1: эмбеддинги (EMBED_PROVIDER)
#
# Решение D4 (заказчик, 27.09.2026): локальный fastembed без внешних ключей.
#   EMBED_PROVIDER=fastembed -- модель sentence-transformers/paraphrase-
#     multilingual-MiniLM-L12-v2 (мультиязычная, вкл. русский, dim 384);
#     модель скачивается при первом использовании (кеш fastembed).
#   EMBED_PROVIDER=fake -- детерминированный bag-of-words хэш (dim 64):
#     только для тестов/разработки без зависимостей.
# Импорт heavy-зависимостей ленивый: без fastembed код контура работает
# на fake-провайдере (юнит-тесты не тянут onnx).

import hashlib
import math
import os
import re

_FAKE_DIM = 64


class FakeEmbedder:
    """Детерминированный хэш-эмбеддер: одинаковые слова -> одинаковые
    координаты. Для тестов конвейера, НЕ для прода."""

    def dim(self) -> int:
        return _FAKE_DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * _FAKE_DIM
            for w in re.findall(r"[а-яёa-z0-9]+", (t or "").lower()):
                h = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16)
                v[h % _FAKE_DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([round(x / norm, 6) for x in v])
        return out


class FastEmbedder:
    """Локальный fastembed (D4). Ленивый импорт + ленивая загрузка модели."""

    _MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    _model = None

    def dim(self) -> int:
        return 384

    def _get(self):
        if FastEmbedder._model is None:
            from fastembed import TextEmbedding  # лениво: heavy-зависимость

            FastEmbedder._model = TextEmbedding(model_name=self._MODEL)
        return FastEmbedder._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._get()
        return [[float(x) for x in vec] for vec in model.embed(texts)]


def get_embedder():
    provider = os.environ.get("EMBED_PROVIDER", "fastembed").strip().lower()
    if provider == "fake":
        return FakeEmbedder()
    if provider == "fastembed":
        try:
            import fastembed  # noqa: F401 -- проверка доступности

            return FastEmbedder()
        except ImportError:
            # fastembed не установлен (локальная разработка) -- деградация
            # до fake, чтобы конвейер оставался тестируемым. В проде
            # EMBED_PROVIDER=fastembed + установленный пакет.
            return FakeEmbedder()
    raise ValueError(f"unknown EMBED_PROVIDER: {provider}")
