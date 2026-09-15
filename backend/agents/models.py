# backend/agents/models.py -- §29: agent_cards + prompts
from datetime import datetime

from sqlalchemy import String, Text, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class AgentCard(Base):
    __tablename__ = "agent_cards"

    code:       Mapped[str]       = mapped_column(String(16), primary_key=True)
    name:       Mapped[str]       = mapped_column(Text, nullable=False)
    role:       Mapped[str]       = mapped_column(Text, nullable=True)
    model:      Mapped[str]       = mapped_column(String(64), nullable=False, default="openai/gpt-4o-mini")
    limits:     Mapped[dict]      = mapped_column(JSONB, nullable=False, default=dict)
    active:     Mapped[bool]      = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime]  = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    def to_dict(self, current_prompt=None, prompt_version=None) -> dict:
        return {
            "code": self.code, "name": self.name, "role": self.role,
            "model": self.model, "limits": self.limits or {},
            "active": self.active,
            "current_prompt": current_prompt,
            "prompt_version": prompt_version,
        }


class Prompt(Base):
    __tablename__ = "prompts"

    id:         Mapped[int]            = mapped_column(Integer, primary_key=True)
    agent_code: Mapped[str]            = mapped_column(String(16), nullable=False)
    version:    Mapped[int]            = mapped_column(Integer, nullable=False)
    text:       Mapped[str]            = mapped_column(Text, nullable=False)
    note:       Mapped[str]            = mapped_column(Text, nullable=True)
    author_id:  Mapped[str]            = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "agent_code": self.agent_code,
            "version": self.version, "text": self.text,
            "note": self.note, "author_id": self.author_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
