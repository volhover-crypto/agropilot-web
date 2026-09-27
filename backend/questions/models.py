# backend/questions/models.py -- §40: agent_questions (§10.1 + механика О3)
#
# Table: agent_questions (миграция 037). Локальный Base без ORM-FK
# (протокол 4 дефектов).

import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def question_ttl_hours() -> int:
    """AGENT_QUESTION_TTL (§40.1), default 72 ч."""
    try:
        return max(1, int(os.environ.get("AGENT_QUESTION_TTL", "72")))
    except ValueError:
        return 72


def compute_expires(now: datetime, ttl_hours: Optional[int] = None) -> datetime:
    """expires_at = момент создания + TTL (aware-время)."""
    return now + timedelta(hours=ttl_hours or question_ttl_hours())


def can_answer(q, now: datetime) -> bool:
    """Отложенный ответ из лога валиден, пока вопрос не expired (§10.2/§40.4)."""
    return q is not None and q.status in ("asked", "deferred") and q.expires_at > now


def is_learning_signal(q) -> bool:
    """Обучающий сигнал Q-метрики (M9/RFC §4): только своевременный ответ.
    Просроченный (expired) вопрос в сигналы НЕ попадает (DoD О3-2)."""
    if q is None or q.status != "answered" or q.answered_at is None:
        return False
    return q.answered_at <= q.expires_at


class AgentQuestion(Base):
    __tablename__ = "agent_questions"

    id:           Mapped[int]              = mapped_column(Integer, primary_key=True)
    ts:           Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    user_id:      Mapped[str]              = mapped_column(String(16), nullable=False)
    question:     Mapped[str]              = mapped_column(Text, nullable=False)
    context_ref:  Mapped[Optional[str]]    = mapped_column(String(128), nullable=True)
    round_id:     Mapped[Optional[str]]    = mapped_column(String(64), nullable=True)
    status:       Mapped[str]              = mapped_column(String(16), nullable=False, default="asked")
    expires_at:   Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    presented_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    answered_at:  Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    answer_text:  Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    insight_id:   Mapped[Optional[int]]    = mapped_column(Integer, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ts": self.ts.isoformat() if self.ts else None,
            "user_id": self.user_id,
            "question": self.question,
            "context_ref": self.context_ref,
            "round_id": self.round_id,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "presented_at": self.presented_at.isoformat() if self.presented_at else None,
            "answered_at": self.answered_at.isoformat() if self.answered_at else None,
            "answer_text": self.answer_text,
            "insight_id": self.insight_id,
            "is_learning_signal": is_learning_signal(self),
        }
