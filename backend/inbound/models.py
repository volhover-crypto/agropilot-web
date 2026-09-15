# backend/inbound/models.py -- §22: таблица inbounds (миграция 019)

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class Inbound(Base):
    __tablename__ = "inbounds"

    id:          Mapped[int]            = mapped_column(Integer, primary_key=True)
    channel:     Mapped[str]            = mapped_column(String(16))
    contact:     Mapped[Optional[str]]  = mapped_column(String(200))
    subject:     Mapped[Optional[str]]  = mapped_column(String(500))
    body:        Mapped[Optional[str]]  = mapped_column(Text)
    received_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True))
    status:      Mapped[str]            = mapped_column(String(16), default="new")
    assigned_to: Mapped[Optional[str]]  = mapped_column(String(16))
    client_id:   Mapped[Optional[str]]  = mapped_column(String(16))
    lead_id:     Mapped[Optional[str]]  = mapped_column(String(16))
    dedup_key:   Mapped[Optional[str]]  = mapped_column(String(200))
    a4_class:    Mapped[dict]           = mapped_column(JSONB, default=dict)

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "channel":     self.channel,
            "contact":     self.contact,
            "subject":     self.subject,
            "body":        self.body,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "status":      self.status,
            "assigned_to": self.assigned_to,
            "client_id":   self.client_id,
            "lead_id":     self.lead_id,
            "dedup_key":   self.dedup_key,
            "a4_class":    self.a4_class or {},
        }
