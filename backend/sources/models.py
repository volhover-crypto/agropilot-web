# backend/sources/models.py -- AgroPILOT Sources model
#
# Table: sources (Block D, CONTRACTS.md §13.1, revision 1a)
# Локальный Base(DeclarativeBase) БЕЗ ORM-ForeignKey; FK только в миграции (протокол 4 дефектов).

from typing import Optional, List
from datetime import datetime

from sqlalchemy import String, Boolean, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped

class Base(DeclarativeBase):
    pass

class Source(Base):
    __tablename__ = "sources"

    id:                   Mapped[int]            = mapped_column(Integer, primary_key=True)
    type:                 Mapped[str]            = mapped_column(String(16), nullable=False)
    url:                  Mapped[str]            = mapped_column(String(500), nullable=False)
    handle:               Mapped[Optional[str]]  = mapped_column(String(200), nullable=True)
    keywords:             Mapped[list]           = mapped_column(JSONB, nullable=False, default=list)
    active:               Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    status:               Mapped[str]            = mapped_column(String(16), nullable=False, default="active")
    linked_strategy_task: Mapped[Optional[str]]  = mapped_column(String(64), nullable=True)
    added_by:             Mapped[Optional[str]]  = mapped_column(String(16), nullable=True)
    receiver_user_id:     Mapped[Optional[str]]  = mapped_column(String(16), nullable=True)
    routing_reason:       Mapped[Optional[str]]  = mapped_column(String(16), nullable=True)
    created_at:           Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id":                   self.id,
            "type":                 self.type,
            "url":                  self.url,
            "handle":               self.handle,
            "keywords":             self.keywords or [],
            "active":               self.active,
            "status":               self.status,
            "linked_strategy_task": self.linked_strategy_task,
            "added_by":             self.added_by,
            "receiver_user_id":     self.receiver_user_id,
            "routing_reason":       self.routing_reason,
            "created_at":           self.created_at.isoformat() if self.created_at else None,
        }
