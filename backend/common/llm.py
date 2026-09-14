# backend/common/llm.py -- LLM-шлюз через OpenRouter (§24)
#
# Единая точка LLM-вызовов для агентов (A2-генерация, A3-адаптация, далее A4/A7).
# Конфигурация в окружении (никаких ключей в коде):
#   OPENROUTER_API_KEY -- ключ OpenRouter
#   LLM_MODEL          -- модель по умолчанию (openai/gpt-4o-mini)
#   LLM_TIMEOUT_SEC    -- таймаут запроса (60)
#
# Вызовы синхронные (urllib), оборачивать в asyncio.to_thread.

import json
import os
import urllib.request

_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMNotConfigured(Exception):
    """Ключ/модель не заданы — вызывающий код решает, что делать (fallback)."""


class LLMError(Exception):
    """OpenRouter вернул ошибку или таймаут."""


def llm_configured() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


def llm_chat(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    max_tokens: int = 800,
) -> str:
    """Один chat-completion запрос. Возвращает текст ответа.

    Бросает LLMNotConfigured / LLMError; ретраи и fallback — на вызывающем.
    """
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise LLMNotConfigured("OPENROUTER_API_KEY не задан")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = json.dumps({
        "model": model or os.environ.get("LLM_MODEL", "openai/gpt-4o-mini"),
        "max_tokens": max_tokens,
        "messages": messages,
    }).encode("utf-8")
    req = urllib.request.Request(
        _API_URL, data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://mdked.hlab.kz/agropilot/",
            "X-Title": "AgroPILOT",
        },
    )
    timeout = float(os.environ.get("LLM_TIMEOUT_SEC", "60"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise LLMError(str(e)[:200])
    try:
        return resp["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"неожиданный ответ OpenRouter: {str(resp)[:200]}")


# ---------------------------------------------------------------------------
# Промты агентов (§6.4 ТЗ: промт — единица конфигурации; до появления
# реестра prompts в БД живут здесь, вынос — Этап 4 без смены вызовов)
# ---------------------------------------------------------------------------

A2_SYSTEM = (
    "Ты — контент-мейкер агро-компании (ирригация, виноградники, плодовые, "
    "цифровизация агробизнеса). Пиши посты для Telegram на русском: живой "
    "экспертный тон, конкретика, без воды и без выдуманных фактов. "
    "Верни ТОЛЬКО текст поста (до 1200 знаков), без пояснений."
)

A3_SYSTEM = (
    "Ты — редактор-адаптер постов под конкретный канал. Сохрани факты и смысл, "
    "подстрой длину, стиль, форматирование и эмодзи под канал. "
    "Верни ТОЛЬКО адаптированный текст поста."
)
