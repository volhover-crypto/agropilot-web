# backend/content/approvals.py -- §35: модель content_approvals (миграция 034)
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import String, Text, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class ContentApproval(Base):
    __tablename__ = "content_approvals"

    id:            Mapped[int]            = mapped_column(Integer, primary_key=True)
    content_id:    Mapped[int]            = mapped_column(Integer, nullable=False)
    urgent:        Mapped[bool]           = mapped_column(Boolean, nullable=False, default=False)
    auto_urgent:   Mapped[bool]           = mapped_column(Boolean, nullable=False, default=False)
    channel_id:    Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    sent_at:       Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    deadline_at:   Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    status:        Mapped[str]            = mapped_column(String(12), nullable=False, default="pending")
    tg_message_id: Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    decided_at:    Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    decided_by:    Mapped[Optional[str]]  = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        def msk(t):
            return t.astimezone(timezone(timedelta(hours=3))).strftime("%d.%m %H:%M") if t else None
        return {
            "id": self.id, "content_id": self.content_id,
            "urgent": self.urgent, "auto_urgent": self.auto_urgent,
            "channel_id": self.channel_id,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
            "deadline_msk": msk(self.deadline_at),
            "status": self.status,
            "tg_message_id": self.tg_message_id,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decided_by": self.decided_by,
        }
