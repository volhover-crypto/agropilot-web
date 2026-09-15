# backend/agents/registry.py -- реестр агентов и промтов (§29)
#
# Источник промтов — таблица prompts (текущая версия = max(version)).
# Если у агента нет строк (например, A1/A5 без LLM-промта) — fallback
# на константы вызывающего модуля. Кэш в процессе на 60 секунд.

import time
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.models import AgentCard, Prompt

_cache: dict = {}  # agent_code -> (expires, text)
_TTL = 60


async def get_agent_prompt(db: AsyncSession, agent_code: str,
                           fallback: Optional[str] = None) -> str:
    now = time.time()
    hit = _cache.get(agent_code)
    if hit and hit[0] > now:
        return hit[1] or fallback or ""
    row = (await db.execute(
        select(Prompt.text)
        .where(Prompt.agent_code == agent_code)
        .order_by(Prompt.version.desc())
        .limit(1)
    )).scalars().first()
    text = row or fallback or ""
    _cache[agent_code] = (now + _TTL, text)
    return text


def invalidate_cache(agent_code: Optional[str] = None) -> None:
    if agent_code:
        _cache.pop(agent_code, None)
    else:
        _cache.clear()


async def next_version(db: AsyncSession, agent_code: str) -> int:
    v = (await db.execute(
        select(func.max(Prompt.version))
        .where(Prompt.agent_code == agent_code)
    )).scalar()
    return (v or 0) + 1
