# backend/questions/routes.py -- §40: вопросы агента ПЕТРУШКИ (О3, §10.2)
#
# Mount: app.include_router(questions_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/petrushka
#
# Эндпоинты (§10.2 + §40):
#   GET   /petrushka/questions?all=1   — лог вопросов (свои; все — isManager)
#   POST  /petrushka/questions         — создание (агент/сервис, менеджер)
#   PATCH /petrushka/questions/{id}    — answer|defer (валидация «не expired»)
#   POST  /petrushka/questions/expire  — джоба asked->expired (systemd-таймер)
#   POST  /petrushka/questions/close_round — гашение asked предыдущих раундов

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.deps import get_db, get_current_user
from backend.common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from backend.questions.models import AgentQuestion, can_answer, compute_expires
from backend.team.models import TeamMember

questions_router = APIRouter(prefix="/petrushka", tags=["petrushka"])

_MANAGER_ROLE_KEYS = {"manager", "admin"}


def _ok(data):
    return {"ok": True, "data": data}


async def _is_manager(db: AsyncSession, user) -> bool:
    member = await db.get(TeamMember, user.id)
    return bool(member and member.role_key in _MANAGER_ROLE_KEYS)


async def _lazy_expire(db: AsyncSession, user_id: Optional[str] = None):
    """Ленивое истечение (§40.1): asked старше expires_at -> expired.
    Срабатывает при чтении лога -- просроченные не висят «живыми» до джобы."""
    stmt = (
        update(AgentQuestion)
        .where(
            AgentQuestion.status == "asked",
            AgentQuestion.expires_at < datetime.now(timezone.utc),
        )
        .values(status="expired")
    )
    if user_id is not None:
        stmt = stmt.where(AgentQuestion.user_id == user_id)
    await db.execute(stmt)
    await db.commit()


@questions_router.get("/questions")
async def list_questions(
    all: int = Query(0, ge=0, le=1),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    see_all = bool(all) and await _is_manager(db, user)
    await _lazy_expire(db, user_id=None if see_all else user.id)

    q = select(AgentQuestion).order_by(AgentQuestion.ts.desc())
    if not see_all:
        q = q.where(AgentQuestion.user_id == user.id)
    rows = (await db.execute(q.limit(limit))).scalars().all()

    # Идемпотентность показа (§40.2): сервер помечает первый фетч fresh-вопросов;
    # фронт дополнительно дедуплицирует по id (localStorage) на рестарте сессии.
    now = datetime.now(timezone.utc)
    fresh_ids = [
        r.id for r in rows
        if r.presented_at is None and r.status in ("asked", "deferred")
        and r.expires_at > now
    ]
    if fresh_ids:
        await db.execute(
            update(AgentQuestion)
            .where(AgentQuestion.id.in_(fresh_ids))
            .values(presented_at=now)
        )
        await db.commit()
        rows = (await db.execute(
            select(AgentQuestion).where(AgentQuestion.id.in_([r.id for r in rows]))
            .order_by(AgentQuestion.ts.desc())
        )).scalars().all()
    return _ok({"items": [r.to_dict() for r in rows], "all": see_all})


class QuestionCreate(BaseModel):
    user_id: str
    question: str
    context_ref: Optional[str] = None
    round_id: Optional[str] = None
    ttl_hours: Optional[int] = None


@questions_router.post("/questions")
async def create_question(
    body: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Создание вопроса агентом/сервисом (менеджер или сервисная учётка).
    Старт нового раунда (round_id) гасит asked-вопросы прежних раундов (§40.3)."""
    if not await _is_manager(db, user):
        raise ForbiddenError("создание вопросов — менеджеры/админ и сервис агента")
    if not body.question or not body.question.strip():
        raise ValidationError("question must be non-empty")
    now = datetime.now(timezone.utc)
    if body.round_id:
        await db.execute(
            update(AgentQuestion)
            .where(
                AgentQuestion.user_id == body.user_id,
                AgentQuestion.status == "asked",
                AgentQuestion.round_id != body.round_id,
            )
            .values(status="expired")
        )
    q = AgentQuestion(
        user_id=body.user_id,
        question=body.question.strip()[:2000],
        context_ref=body.context_ref,
        round_id=body.round_id,
        expires_at=compute_expires(now, body.ttl_hours),
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return _ok(q.to_dict())


class QuestionPatch(BaseModel):
    answer: Optional[str] = None
    defer: bool = False


@questions_router.patch("/questions/{question_id}")
async def patch_question(
    question_id: int,
    body: QuestionPatch,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Ответ или отложенный ответ из лога (§10.2). Просроченный вопрос --
    409 Conflict, обучающим сигналом не становится (§40.4)."""
    q = await db.get(AgentQuestion, question_id)
    if q is None:
        raise NotFoundError(f"question {question_id} не найден")
    member = await db.get(TeamMember, user.id)
    if q.user_id != user.id and not (member and member.role_key in _MANAGER_ROLE_KEYS):
        raise ForbiddenError("отвечать может адресат или менеджер")

    now = datetime.now(timezone.utc)
    if body.defer:
        if not can_answer(q, now):
            raise ConflictError("вопрос истёк (TTL) -- ответ не принимается")
        q.status = "deferred"
    else:
        if not body.answer or not body.answer.strip():
            raise ValidationError("answer must be non-empty")
        if not can_answer(q, now):
            raise ConflictError("вопрос истёк (TTL) -- ответ не принимается")
        q.status = "answered"
        q.answer_text = body.answer.strip()[:4000]
        q.answered_at = now
    await db.commit()
    await db.refresh(q)
    return _ok(q.to_dict())


@questions_router.post("/questions/expire")
async def expire_questions(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Джоба expired (systemd-таймер agropilot-questions-expire, ежечасно):
    массовый перевод asked->expired по TTL."""
    if not await _is_manager(db, user):
        raise ForbiddenError("только менеджеры/сервис")
    res = await db.execute(
        update(AgentQuestion)
        .where(
            AgentQuestion.status == "asked",
            AgentQuestion.expires_at < datetime.now(timezone.utc),
        )
        .values(status="expired")
    )
    await db.commit()
    return _ok({"expired": int(res.rowcount or 0)})


class RoundClose(BaseModel):
    round_id: str
    user_id: Optional[str] = None


@questions_router.post("/questions/close_round")
async def close_round(
    body: RoundClose,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Явное гашение раунда (§40.3): все asked с ДРУГИМ round_id -> expired."""
    if not await _is_manager(db, user):
        raise ForbiddenError("только менеджеры/сервис")
    stmt = (
        update(AgentQuestion)
        .where(
            AgentQuestion.status == "asked",
            AgentQuestion.round_id != body.round_id,
        )
        .values(status="expired")
    )
    if body.user_id:
        stmt = stmt.where(AgentQuestion.user_id == body.user_id)
    res = await db.execute(stmt)
    await db.commit()
    return _ok({"expired": int(res.rowcount or 0), "round_id": body.round_id})
