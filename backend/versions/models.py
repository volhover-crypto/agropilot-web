# backend/versions/models.py -- AgroPILOT M9 ORM models
#
# Содержит две модели:
#   - DealVersion  (таблица deal_versions)
#   - TeamSkill    (таблица team_skills)
#
# Обе модели используются в одном модуле backend/versions/
# с двумя отдельными роутерами (deals_versions_router, skills_router).

import uuid
from sqlalchemy import String, Text, Integer, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# DealVersion
# ---------------------------------------------------------------------------

class DealVersion(Base):
    __tablename__ = "deal_versions"
    __table_args__ = (
        UniqueConstraint("deal_id", "version_num", name="uq_deal_version"),
    )

    id          = mapped_column(UUID(as_uuid=False), primary_key=True,
                                default=lambda: str(uuid.uuid4()))
    deal_id     = mapped_column(String, nullable=False, index=True)
    version_num = mapped_column(Integer, nullable=False)
    snapshot    = mapped_column(JSONB, nullable=False)
    comment     = mapped_column(Text, nullable=True)
    author_id   = mapped_column(String, nullable=False)
    author_name = mapped_column(String, nullable=False)
    created_at  = mapped_column(DateTime(timezone=True), nullable=False,
                                server_default=func.now())
    # Нет updated_at: версия иммутабельна после создания

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "deal_id":     self.deal_id,
            "version_num": self.version_num,
            "snapshot":    self.snapshot,
            "comment":     self.comment,
            "author_id":   self.author_id,
            "author_name": self.author_name,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# TeamSkill
# ---------------------------------------------------------------------------

class TeamSkill(Base):
    __tablename__ = "team_skills"
    __table_args__ = (
        UniqueConstraint("user_id", "skill", name="uq_user_skill"),
    )

    id         = mapped_column(UUID(as_uuid=False), primary_key=True,
                               default=lambda: str(uuid.uuid4()))
    user_id    = mapped_column(String, nullable=False, index=True)
    user_name  = mapped_column(String, nullable=False)
    skill      = mapped_column(String(100), nullable=False)
    level      = mapped_column(Integer, nullable=True, default=3)
    note       = mapped_column(Text, nullable=True)
    updated_at = mapped_column(DateTime(timezone=True), nullable=True,
                               server_default=func.now(), onupdate=func.now())
    # Нет created_at: upsert-семантика делает "время создания" неоднозначным

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "user_id":    self.user_id,
            "user_name":  self.user_name,
            "skill":      self.skill,
            "level":      self.level,
            "note":       self.note,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
