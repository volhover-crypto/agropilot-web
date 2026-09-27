# backend/knowledge/models.py -- §41: knowledge_bases / docs / chunks

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id:             Mapped[int]              = mapped_column(Integer, primary_key=True)
    title:          Mapped[str]              = mapped_column(String(200), nullable=False)
    corpus_version: Mapped[int]              = mapped_column(Integer, nullable=False, default=0)
    doc_count:      Mapped[int]              = mapped_column(Integer, nullable=False, default=0)
    indexed_at:     Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    verified_by:    Mapped[Optional[str]]    = mapped_column(String(16), nullable=True)
    status:         Mapped[str]              = mapped_column(String(16), nullable=False, default="active")
    created_at:     Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "corpus_version": self.corpus_version,
            "doc_count": self.doc_count,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "verified_by": self.verified_by,
            "status": self.status,
        }


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id:          Mapped[int]              = mapped_column(Integer, primary_key=True)
    kb_id:       Mapped[int]              = mapped_column(Integer, nullable=False)
    title:       Mapped[str]              = mapped_column(String(300), nullable=False)
    status:      Mapped[str]              = mapped_column(String(16), nullable=False, default="uploaded")
    fail_reason: Mapped[Optional[str]]    = mapped_column(String(64), nullable=True)
    charset:     Mapped[Optional[str]]    = mapped_column(String(16), nullable=True)
    size_bytes:  Mapped[Optional[int]]    = mapped_column(Integer, nullable=True)
    created_at:  Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at:  Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kb_id": self.kb_id,
            "title": self.title,
            "status": self.status,
            "fail_reason": self.fail_reason,
            "charset": self.charset,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id:              Mapped[int]              = mapped_column(Integer, primary_key=True)
    doc_id:          Mapped[int]              = mapped_column(Integer, nullable=False)
    kb_id:           Mapped[int]              = mapped_column(Integer, nullable=False)
    ord:             Mapped[int]              = mapped_column(Integer, nullable=False)
    quote_start:     Mapped[int]              = mapped_column(Integer, nullable=False)
    quote_end:       Mapped[int]              = mapped_column(Integer, nullable=False)
    qdrant_point_id: Mapped[Optional[str]]    = mapped_column(String(64), nullable=True)
    text:            Mapped[str]              = mapped_column(Text, nullable=False)
