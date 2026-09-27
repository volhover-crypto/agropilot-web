# backend/knowledge/chunking.py -- §41.1: чанкинг текста документа
#
# CHUNK_SIZE (симв.) и CHUNK_OVERLAP (%) -- конфиг BFF (env).
# Чанк знает свой порядковый номер и quote-диапазон [start, end) в тексте
# документа -- клик по цитате ведёт к подсветке диапазона.

import os


def chunk_params() -> tuple[int, float]:
    try:
        size = max(200, int(os.environ.get("CHUNK_SIZE", "1000")))
    except ValueError:
        size = 1000
    try:
        overlap = min(0.5, max(0.0, float(os.environ.get("CHUNK_OVERLAP", "0.15"))))
    except ValueError:
        overlap = 0.15
    return size, overlap


def chunk_text(text: str, size: int | None = None, overlap: float | None = None) -> list[dict]:
    """Режет текст на чанки [{ord, start, end, text}]. Пустой текст -> [].
    Границы выравниваются по предложениям/переносам, где это возможно."""
    size, ovl = chunk_params() if size is None else (size, overlap or 0.15)
    text = (text or "").strip()
    if not text:
        return []
    step = max(1, int(size * (1 - ovl)))
    chunks = []
    start = 0
    n = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # попытка дотянуть границу до конца предложения/слова
            window = text[start:end]
            cut = max(window.rfind(". "), window.rfind(".\n"), window.rfind("\n\n"))
            if cut < int(size * 0.5):
                cut = window.rfind(" ")
            if cut >= int(size * 0.5):
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append({
                "ord": n,
                "start": start,
                "end": end,
                "text": piece,
            })
            n += 1
        if end >= len(text):
            break
        start = max(end - int(size * ovl), start + 1)
    return chunks
