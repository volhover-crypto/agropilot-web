# backend/goals/models.py -- AgroPILOT SQLAlchemy model for goals table
#
# Table: goals
# Schema captured from prod DB after seed_prod.sql execution (fix issue#1-3).
# metric — JSONB: {"name","target","current","unit"}.

from datetime import date
from typing import Optional

from sqlalchemy import String, Integer, Date, Text, JSON
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class Goal(Base):
    __tablename__ = "goals"

    id:           Mapped[str]            = mapped_column(String(64), primary_key=True)
    title:        Mapped[str]            = mapped_column(Text, nullable=False)
    description:  Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
    kind:         Mapped[Optional[str]]  = mapped_column(String(32), nullable=True)
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end:   Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    owner_id:     Mapped[Optional[str]]  = mapped_column(String(64), nullable=True)
    status:       Mapped[Optional[str]]  = mapped_column(String(32), nullable=True)
    progress:     Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    metric:       Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    signal:       Mapped[Optional[str]]  = mapped_column(String(32), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "title":        self.title,
            "description":  self.description,
            "kind":         self.kind,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end":   self.period_end.isoformat() if self.period_end else None,
            "owner_id":     self.owner_id,
            "status":       self.status,
            "progress":     self.progress,
            "metric":       self.metric,
            "signal":       self.signal,
        }
