# backend/strategy_tasks/models.py -- AgroPILOT Strategy Tasks model
#
# Table: strategy_tasks (Block C, CONTRACTS.md 12.1)

from typing import Optional
from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class StrategyTask(Base):
    __tablename__ = "strategy_tasks"

    id:               Mapped[str]                = mapped_column(String(64), primary_key=True)
    title:            Mapped[str]                = mapped_column(Text, nullable=False)
    description:      Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
    priority:         Mapped[str]                = mapped_column(String(16), nullable=False, default="medium")
    status:           Mapped[str]                = mapped_column(String(16), nullable=False, default="active")
    monitoring_focus: Mapped[list]               = mapped_column(JSONB, nullable=False, default=list)
    owner_id:         Mapped[str]                = mapped_column(String(16), nullable=False)
    added_by:         Mapped[str]                = mapped_column(String(16), nullable=False)
    linked_scenario:  Mapped[Optional[str]]      = mapped_column(String(64), nullable=True)
    created_at:       Mapped[datetime]           = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at:       Mapped[datetime]           = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "title":            self.title,
            "description":      self.description,
            "priority":         self.priority,
            "status":           self.status,
            "monitoring_focus": self.monitoring_focus if self.monitoring_focus is not None else [],
            "owner_id":         self.owner_id,
            "added_by":         self.added_by,
            "linked_scenario":  self.linked_scenario,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
            "updated_at":       self.updated_at.isoformat() if self.updated_at else None,
        }
