# backend/strategy/direction_models.py -- §30: strategy_directions
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class StrategyDirection(Base):
    __tablename__ = "strategy_directions"

    id:          Mapped[str]            = mapped_column(String(16), primary_key=True)
    title:       Mapped[str]            = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
    keywords:    Mapped[list]           = mapped_column(JSONB, nullable=False, default=list)
    status:      Mapped[str]            = mapped_column(String(16), nullable=False, default="active")
    goal_ids:    Mapped[list]           = mapped_column(JSONB, nullable=False, default=list)
    owner_id:    Mapped[Optional[str]]  = mapped_column(String(16), nullable=True)
    created_at:  Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at:  Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title,
            "description": self.description,
            "keywords": self.keywords or [],
            "status": self.status,
            "goal_ids": self.goal_ids or [],
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
