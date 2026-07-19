# backend/content/models.py -- AgroPILOT Content model
#
# Table: content (M10-3: архив контента/постов SMM)

from typing import Optional
from datetime import datetime

from sqlalchemy import String, Text, Integer
from sqlalchemy.dialects.postgresql import TIMESTAMP
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
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at:   Mapped[datetime]      = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "title":        self.title,
            "body":         self.body,
            "platform":     self.platform,
            "status":       self.status,
            "author_id":    self.author_id,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
        }
