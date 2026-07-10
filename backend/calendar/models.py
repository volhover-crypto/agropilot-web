# backend/calendar/models.py -- AgroPILOT M7 Calendar ORM
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, Text, Boolean, DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column

class Base(DeclarativeBase):
      pass

class EventKind(str, PyEnum):
      meeting  = "meeting"
      call     = "call"
      deadline = "deadline"
      other    = "other"

class CalendarEvent(Base):
      __tablename__ = "calendar_events"
      id         = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
      title      = mapped_column(String(255), nullable=False)
      description= mapped_column(Text, nullable=True)
      start_at   = mapped_column(DateTime(timezone=True), nullable=False)
      end_at     = mapped_column(DateTime(timezone=True), nullable=True)
      all_day    = mapped_column(Boolean, default=False)
      deal_id    = mapped_column(String(64), nullable=True)
      owner_id   = mapped_column(String(64), nullable=False, index=True)
      owner_name = mapped_column(String(255), nullable=False)
      kind       = mapped_column(Enum(EventKind, name="event_kind"), default=EventKind.other)
      created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
      updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
              return {
                            "id": self.id, "title": self.title, "description": self.description,
                            "start_at": self.start_at.isoformat() if self.start_at else None,
                            "end_at": self.end_at.isoformat() if self.end_at else None,
                            "all_day": self.all_day, "deal_id": self.deal_id,
                            "owner_id": self.owner_id, "owner_name": self.owner_name, "kind": self.kind,
                            "created_at": self.created_at.isoformat() if self.created_at else None,
                            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                        }
