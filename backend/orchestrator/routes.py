# backend/orchestrator/routes.py -- §41.3: orchChat (M11, О1)
#
# Mount: app.include_router(orchestrator_router, prefix="/agropilot/api/v1")
# POST /v1/orchestrator/chat {message, kb_id?} -- knowledge-aware чат:
#   ретрив по активным KB -> ответ С обязательными citations[] (§9.2/§41);
#   пустой ретрив или ответ без валидных ссылок -> unverified-деградация
#   до обычного чата (knowledge: false, без значка «знание» в UI).
# corpus_version фиксируется в meta run_logs (принцип версий M9).
# session_key (О6: "<user_id>:telegram:<chat_id>") -- в meta run_logs.

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.knowledge.models import KnowledgeBase
from backend.knowledge.retrieval import retrieve, validate_citations
from backend.common.deps import get_db, get_current_user
from backend.common.errors import ValidationError
from backend.common.llm import LLMError, llm_configured
from backend.agents.registry import get_agent_prompt
from backend.agents.runlog import llm_call_logged

orchestrator_router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])

ORCH_SYSTEM = (
    "Ты — ПЕТРУШКА, оркестратор агро-ERP AgroPILOT. Отвечай НА РУССКОМ, кратко "
    "и по делу. Если ниже даны ИСТОЧНИКИ ЗНАНИЙ, отвечай строго по ним: КАЖДОЕ "
    "фактическое утверждение (цифра, норма, срок, факт) обязано иметь номер "
    "источника в квадратных скобках, например: «Норма полива — 500-650 м3/га "
    "за сезон [1]». Ответ без номеров источников [n] НЕ ПРИНИМАЕТСЯ. Если "
    "источники не покрывают вопрос — скажи честно, чего не хватает. До 8 "
    "предложений."
)


def _ok(data):
    return {"ok": True, "data": data}


class ChatBody(BaseModel):
    message: str
    kb_id: Optional[int] = None
    session_key: Optional[str] = None  # О6: <user_id>:telegram:<chat_id>


async def _active_kb_ids(db: AsyncSession, kb_id: Optional[int]) -> list[int]:
    q = select(KnowledgeBase.id).where(KnowledgeBase.status == "active")
    if kb_id is not None:
        q = q.where(KnowledgeBase.id == kb_id)
    return list((await db.execute(q)).scalars().all())


async def _corpus_version(db: AsyncSession, kb_ids: list[int]) -> int:
    if not kb_ids:
        return 0
    return int((await db.execute(
        select(func.max(KnowledgeBase.corpus_version)).where(KnowledgeBase.id.in_(kb_ids))
    )).scalar() or 0)


async def orchestrator_chat(
    db: AsyncSession, user, message: str,
    kb_id: Optional[int] = None, session_key: Optional[str] = None,
) -> dict:
    """Переиспользуется веб-чатом (§41.3) и Telegram-каналом (§42)."""
    q = (message or "").strip()
    if not q:
        raise ValidationError("message пуст")
    if not llm_configured():
        raise ValidationError("LLM-шлюз не настроен (OPENROUTER_API_KEY)")

    kb_ids = await _active_kb_ids(db, kb_id)
    hits = await retrieve(db, q, kb_ids=kb_ids or None, limit=6)

    meta: dict = {"kind": "knowledge_chat"}
    if session_key:
        meta["session_key"] = session_key

    if hits:
        corpus_v = await _corpus_version(db, kb_ids)
        meta["corpus_version"] = corpus_v
        fragments = "\n\n".join(
            f"ИСТОЧНИК [{i+1}] «{h['doc_title']}»:\n{h['text'][:1200]}"
            for i, h in enumerate(hits)
        )
        prompt = f"ИСТОЧНИКИ ЗНАНИЙ:\n{fragments}\n\nВопрос пользователя: {q}"
        try:
            system = await get_agent_prompt(db, "a7", ORCH_SYSTEM)
            answer = await llm_call_logged(
                db, "a7", prompt, system, max_tokens=700,
                items=len(hits), meta=meta)
        except LLMError as e:
            raise ValidationError(f"LLM сбой: {str(e)[:150]}")
        used = validate_citations(answer, len(hits))
        if not used:
            # один retry: LLM без [n] -- требуем разметку (риск ТЗ §6:
            # цитирование не должно убивать значок «знание» на ровном месте)
            try:
                answer2 = await llm_call_logged(
                    db, "a7",
                    prompt + "\n\nПРЕДЫДУЩИЙ ОТВЕТ (без ссылок на источники, "
                    "НЕ ПРИНЯТ):\n" + answer
                    + "\n\nПерепиши ответ, помечая каждое утверждение номером "
                    "источника в квадратных скобках: [1], [2]...",
                    system, max_tokens=700,
                    items=len(hits), meta={**meta, "retry": True})
                used2 = validate_citations(answer2, len(hits))
                if used2:
                    answer, used = answer2, used2
            except LLMError:
                pass  # останемся unverified
        if used:
            # валидные citations: только реально процитированные источники
            citations = [
                {"doc_id": hits[i - 1]["doc_id"],
                 "title": hits[i - 1]["doc_title"],
                 "chunk_id": hits[i - 1]["chunk_id"],
                 "quote": hits[i - 1]["text"][:240],
                 "score": hits[i - 1]["score"]}
                for i in used
            ]
            return {"reply": answer, "knowledge": True,
                    "citations": citations, "corpus_version": corpus_v}
        # ответ без валидных ссылок -> unverified-деградация (§41.3)
        return {"reply": answer, "knowledge": False, "citations": [],
                "corpus_version": corpus_v}

    # обычный чат: знаний по вопросу нет -- без значка «знание»
    from backend.assistant.routes import build_context
    import json as _json

    ctx = await build_context(db, q)
    prompt = ("Контекст системы (JSON):\n"
              + _json.dumps(ctx, ensure_ascii=False, indent=1)
              + "\n\nВопрос пользователя: " + q)
    try:
        system = await get_agent_prompt(db, "a7", ORCH_SYSTEM)
        answer = await llm_call_logged(db, "a7", prompt, system,
                                       max_tokens=500, meta=meta)
    except LLMError as e:
        raise ValidationError(f"LLM сбой: {str(e)[:150]}")
    return {"reply": answer, "knowledge": False, "citations": []}


@orchestrator_router.post("/chat")
async def chat(
    body: ChatBody,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    session = body.session_key or f"{user.id}:web"
    result = await orchestrator_chat(db, user, body.message, body.kb_id, session)
    return _ok(result)
