# backend/segments/models.py -- §37: сегменты аудитории + рубрики (миграция 035)
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, Boolean
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class AudienceSegment(Base):
    __tablename__ = "audience_segments"

    id:          Mapped[int]            = mapped_column(Integer, primary_key=True)
    code:        Mapped[str]            = mapped_column(Text, unique=True, nullable=False)
    name:        Mapped[str]            = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
    prompt_addon: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # аддон к промту A2
    active:      Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    created_at:  Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {"id": self.id, "code": self.code, "name": self.name,
                "description": self.description, "prompt_addon": self.prompt_addon,
                "active": self.active}


class Rubric(Base):
    __tablename__ = "rubrics"

    id:          Mapped[int]            = mapped_column(Integer, primary_key=True)
    code:        Mapped[str]            = mapped_column(Text, unique=True, nullable=False)
    title:       Mapped[str]            = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
    active:      Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    created_at:  Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {"id": self.id, "code": self.code, "title": self.title,
                "description": self.description, "active": self.active}
