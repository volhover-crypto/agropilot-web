# backend/sources/models.py -- AgroPILOT Sources model
#
# Table: sources (M10-2: реестр источников мониторинга)

from typing import Optional, List
from datetime import datetime

from sqlalchemy import String, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped

class Base(DeclarativeBase):
    pass

class Source(Base):
    __tablename__ = "sources"

    id:         Mapped[int]            = mapped_column(Integer, primary_key=True)
    type:       Mapped[str]            = mapped_column(String(16), nullable=False)
    url:        Mapped[str]            = mapped_column(String(500), nullable=False)
    handle:     Mapped[Optional[str]]  = mapped_column(String(200), nullable=True)
    keywords:   Mapped[list]           = mapped_column(JSONB, nullable=False, default=list)
    active:     Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "type":       self.type,
            "url":        self.url,
            "handle":     self.handle,
            "keywords":   self.keywords or [],
            "active":     self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
