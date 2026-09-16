# backend/agents/runlog_models.py -- §32: журнал запусков агентов
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, Numeric, DateTime
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class RunLog(Base):
    __tablename__ = "run_logs"

    id:                Mapped[int]             = mapped_column(Integer, primary_key=True)
    agent_code:        Mapped[str]             = mapped_column(String(16))
    started_at:        Mapped[datetime]        = mapped_column(TIMESTAMP(timezone=True))
    finished_at:       Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    status:            Mapped[str]             = mapped_column(String(8), default="ok")
    error:             Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    model:             Mapped[Optional[str]]   = mapped_column(String(64), nullable=True)
    prompt_tokens:     Mapped[int]             = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int]             = mapped_column(Integer, default=0)
    total_tokens:      Mapped[int]             = mapped_column(Integer, default=0)
    cost_usd:          Mapped[float]           = mapped_column(Numeric(10, 4), default=0)
    items:             Mapped[int]             = mapped_column(Integer, default=0)
    meta:              Mapped[dict]            = mapped_column(JSONB, default=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "agent_code": self.agent_code,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "status": self.status, "error": (self.error or "")[:200],
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": float(self.cost_usd) if self.cost_usd is not None else 0,
            "items": self.items, "meta": self.meta or {},
        }
