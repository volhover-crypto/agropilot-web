# backend/channels/models.py -- §21.1: channels (миграция 018)
from datetime import datetime

from sqlalchemy import String, Text, Integer, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class Channel(Base):
    __tablename__ = "channels"

    id:           Mapped[int]       = mapped_column(Integer, primary_key=True)
    type:         Mapped[str]       = mapped_column(String(16))
    name:         Mapped[str]       = mapped_column(Text)
    connection:   Mapped[dict]      = mapped_column(JSONB, default=dict)
    adapt_prompt: Mapped[str]       = mapped_column(Text, nullable=True)
    active:       Mapped[bool]      = mapped_column(Boolean, default=True)
    segment_code: Mapped[str | None] = mapped_column(Text, nullable=True)  # §37
    stats:        Mapped[dict]      = mapped_column(JSONB, default=dict)
    created_at:   Mapped[datetime]  = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id, "type": self.type, "name": self.name,
            "connection": self.connection or {},
            "adapt_prompt": self.adapt_prompt,
            "active": self.active,
            "segment_code": self.segment_code,
            "stats": self.stats or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
