# backend/tasks/models.py -- AgroPILOT SQLAlchemy model for tasks table
#
# Table: tasks
# Created by Comet on 2026-07-14 (manual migration, no alembic yet).

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    id:         Mapped[str]              = mapped_column(String(64), primary_key=True)
    title:      Mapped[str]              = mapped_column(Text, nullable=False)
    status:     Mapped[str]              = mapped_column(String(32), nullable=False, default="active")
    assignee:   Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    owner_id:   Mapped[Optional[str]]    = mapped_column(String(64), nullable=True)
    goal_id:    Mapped[Optional[str]]    = mapped_column(String(64), nullable=True)
    due_at:     Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    priority:   Mapped[Optional[str]]    = mapped_column(String(16), nullable=True)
    deal_id:    Mapped[Optional[str]]    = mapped_column(String(64), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "title":      self.title,
            "status":     self.status,
            "assignee":   self.assignee,
            "owner_id":   self.owner_id,
            "goal_id":    self.goal_id,
            "due_at":     self.due_at.isoformat() if self.due_at else None,
            "priority":   self.priority,
            "deal_id":    self.deal_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
