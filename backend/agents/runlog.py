# backend/agents/runlog.py -- §32: логирование запусков агентов (дашборд)
#
# llm_call_logged: оборачивает LLM-вызов, пишет run_logs с usage/cost.
# log_run: факт процессного прогона (A1-скан, A5-генерация) с items.

import os
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.llm import llm_chat
from backend.agents.runlog_models import RunLog

# Грубая оценка стоимости (USD за 1М токенов) — только для gpt-4o-mini;
# прочие модели логируются с нулевой стоимостью до настройки прайса.
_PRICE = {("openai/gpt-4o-mini", "prompt"): 0.15, ("openai/gpt-4o-mini", "completion"): 0.60}


def _cost(model: str, pt: int, ct: int) -> float:
    return round(
        pt / 1_000_000 * _PRICE.get((model, "prompt"), 0)
        + ct / 1_000_000 * _PRICE.get((model, "completion"), 0), 6)


async def llm_call_logged(
    db: AsyncSession,
    agent_code: str,
    prompt: str,
    system: str | None = None,
    max_tokens: int = 800,
    items: int = 1,
    meta: dict | None = None,
) -> str:
    """LLM-вызов с записью run_logs (токены/стоимость/ошибка)."""
    import asyncio

    started = datetime.now(timezone.utc)
    log = RunLog(agent_code=agent_code, started_at=started, status="ok",
                 meta=meta or {})
    db.add(log)
    await db.flush()
    try:
        import json as _json
        import urllib.request
        from backend.common.llm import _API_URL
        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        model = os.environ.get("LLM_MODEL", "openai/gpt-4o-mini")
        messages = ([{"role": "system", "content": system}] if system else []) \
            + [{"role": "user", "content": prompt}]
        body = _json.dumps({"model": model, "max_tokens": max_tokens,
                            "messages": messages}).encode("utf-8")
        req = urllib.request.Request(
            _API_URL, data=body,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "HTTP-Referer": "https://mdked.hlab.kz/agropilot/",
                     "X-Title": "AgroPILOT"})
        def _call():
            with urllib.request.urlopen(req, timeout=60) as r:
                return _json.loads(r.read().decode("utf-8"))
        resp = await asyncio.to_thread(_call)
        text = resp["choices"][0]["message"]["content"].strip()
        usage = resp.get("usage") or {}
        log.model = model
        log.prompt_tokens = int(usage.get("prompt_tokens") or 0)
        log.completion_tokens = int(usage.get("completion_tokens") or 0)
        log.total_tokens = int(usage.get("total_tokens")
                               or (log.prompt_tokens + log.completion_tokens))
        log.cost_usd = _cost(model, log.prompt_tokens, log.completion_tokens)
        log.items = items
        log.finished_at = datetime.now(timezone.utc)
        await db.commit()
        return text
    except Exception as e:
        log.status = "error"
        log.error = str(e)[:500]
        log.finished_at = datetime.now(timezone.utc)
        await db.commit()
        raise


async def log_run(
    db: AsyncSession,
    agent_code: str,
    items: int = 0,
    status: str = "ok",
    error: str | None = None,
    meta: dict | None = None,
) -> None:
    """Факт прогона процессного агента (без LLM): A1-скан, A5-генерация."""
    now = datetime.now(timezone.utc)
    db.add(RunLog(agent_code=agent_code, started_at=now, finished_at=now,
                  status=status, error=error, items=items, meta=meta or {}))
    await db.commit()
