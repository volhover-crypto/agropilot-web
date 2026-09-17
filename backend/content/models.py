# backend/content/models.py -- AgroPILOT Content model
#
# Table: content (M10-3: архив контента; §21: конвейер контента A2/A3)

from typing import Optional
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class Content(Base):
    __tablename__ = "content"

    id:           Mapped[int]           = mapped_column(Integer, primary_key=True)
    title:        Mapped[str]           = mapped_column(String(300), nullable=False)
    body:         Mapped[str]           = mapped_column(Text, nullable=False)
    platform:     Mapped[str]           = mapped_column(String(32), nullable=False)
    status:       Mapped[str]           = mapped_column(String(16), nullable=False, default="draft")
    author_id:    Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    published_at: Mapped[Optional[datetime]]  = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at:   Mapped[datetime]      = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    published_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    # §21 — конвейер
    news_item_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    editor_id:    Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    tags:         Mapped[list]          = mapped_column(JSONB, nullable=False, default=list)
    channel_ids:  Mapped[list]          = mapped_column(JSONB, nullable=False, default=list)
    updated_at:   Mapped[datetime]      = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # §37 — сегмент аудитории и рубрика
    segment_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rubric_code:  Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "title":        self.title,
            "body":         self.body,
            "platform":     self.platform,
            "status":       self.status,
            "author_id":    self.author_id,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "published_url": self.published_url,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
            "news_item_id": self.news_item_id,
            "editor_id":    self.editor_id,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "tags":         self.tags or [],
            "channel_ids":  self.channel_ids or [],
            "updated_at":   self.updated_at.isoformat() if self.updated_at else None,
            "segment_code": self.segment_code,
            "rubric_code":  self.rubric_code,
        }


class ContentVersion(Base):
    """История правок текста (§21.1): черновик A2 → правки редактора → публикация."""
    __tablename__ = "content_versions"

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int]           = mapped_column(Integer, nullable=False)
    title:      Mapped[str]           = mapped_column(String(300), nullable=False)
    body:       Mapped[str]           = mapped_column(Text, nullable=False)
    author_id:  Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    comment:    Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "content_id": self.content_id,
            "title":      self.title,
            "body":       self.body,
            "author_id":  self.author_id,
            "comment":    self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
