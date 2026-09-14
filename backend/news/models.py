# backend/news/models.py -- §20: news_items + read-only отражение sources
#
# news_items наполняет A1 (POST /v1/news/scan, n8n-расписание §20.2);
# sources -- существующая таблица (§13), здесь только нужные колонки.

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, String, Integer, Numeric, Text, ForeignKey, DateTime
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class NewsItem(Base):
    __tablename__ = "news_items"

    id:               Mapped[int]                 = mapped_column(Integer, primary_key=True)
    source_id:        Mapped[int]                 = mapped_column(ForeignKey("sources.id"))
    title:            Mapped[str]                 = mapped_column(Text, nullable=False)
    summary:          Mapped[Optional[str]]       = mapped_column(Text, nullable=True)
    url:              Mapped[Optional[str]]       = mapped_column(String(1000), nullable=True)
    published_at:     Mapped[Optional[datetime]]  = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at:       Mapped[datetime]            = mapped_column(DateTime(timezone=True), nullable=False)
    status:           Mapped[str]                 = mapped_column(String(16), nullable=False, default="new")
    relevance:        Mapped[Optional[Decimal]]   = mapped_column(Numeric(4, 2), nullable=True)
    relevance_reason: Mapped[Optional[str]]       = mapped_column(Text, nullable=True)
    agent_run_id:     Mapped[Optional[str]]       = mapped_column(String(64), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "status": self.status,
            # numeric -> float для JSON
            "relevance": float(self.relevance) if self.relevance is not None else None,
            "relevance_reason": self.relevance_reason,
            "agent_run_id": self.agent_run_id,
        }


class Source(Base):
    """Read-only срез существующей таблицы sources (§13 + миграция 017)."""
    __tablename__ = "sources"

    id:               Mapped[int]      = mapped_column(Integer, primary_key=True)
    type:             Mapped[str]      = mapped_column(String(32))
    url:              Mapped[str]      = mapped_column(String(500))
    keywords:         Mapped[list]     = mapped_column(postgresql.JSONB)
    active:           Mapped[bool]     = mapped_column(Boolean)
    status:           Mapped[str]      = mapped_column(String(16))
    check_period_min: Mapped[int]      = mapped_column(Integer)
