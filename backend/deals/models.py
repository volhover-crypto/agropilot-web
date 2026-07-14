# backend/deals/models.py -- AgroPILOT SQLAlchemy model for deals table
#
# Table: deals
# Created by Comet on 2026-07-14 (manual migration, no alembic yet).
# Schema captured from prod DB after seed_prod.sql execution.

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, JSON, Text
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class Deal(Base):
    __tablename__ = "deals"

    id:          Mapped[str]           = mapped_column(String(64), primary_key=True)
    name:        Mapped[str]           = mapped_column(Text, nullable=False)
    stage:       Mapped[str]           = mapped_column(String(32), nullable=False, default="lead")
    client_id:   Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    owner_id:    Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    owner_sales: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    finance:     Mapped[Optional[dict]]= mapped_column(JSON, nullable=True)
    need_type:   Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    industry:    Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    region:      Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score:       Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    signal:      Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    goal_id:     Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "name":        self.name,
            "stage":       self.stage,
            "client_id":   self.client_id,
            "owner_id":    self.owner_id,
            "owner_sales": self.owner_sales,
            "finance":     self.finance,
            "need_type":   self.need_type,
            "industry":    self.industry,
            "region":      self.region,
            "score":       self.score,
            "signal":      self.signal,
            "goal_id":     self.goal_id,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
            "updated_at":  self.updated_at.isoformat() if self.updated_at else None,
        }
