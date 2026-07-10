# backend/versions/models.py -- AgroPILOT M9 ORM: DealVersion + TeamSkill
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# DealVersion
# ---------------------------------------------------------------------------
class DealVersion(Base):
    """Snapshot / version of a deal.

    Unique constraint: uq_deal_version (deal_id, version_number)
    Used by create_version() with ON CONFLICT / retry logic.
    """
    __tablename__ = "deal_versions"
    __table_args__ = (
        UniqueConstraint("deal_id", "version_number", name="uq_deal_version"),
    )

    id             = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id        = mapped_column(String(64), nullable=False, index=True)
    version_number = mapped_column(Integer, nullable=False)
    title          = mapped_column(String(255), nullable=False)
    description    = mapped_column(Text, nullable=True)
    created_by     = mapped_column(String(64), nullable=False)   # owner_id from JWT sub
    created_at     = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self):
        return {
            "id":             self.id,
            "deal_id":        self.deal_id,
            "version_number": self.version_number,
            "title":          self.title,
            "description":    self.description,
            "created_by":     self.created_by,
            "created_at":     self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# TeamSkill
# ---------------------------------------------------------------------------
class TeamSkill(Base):
    """Skill entry per user.

    PK: (user_id, skill_name)  -- natural composite key, enables ON CONFLICT upsert.
    """
    __tablename__ = "team_skills"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_name", name="uq_team_skill"),
    )

    id         = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = mapped_column(String(64), nullable=False, index=True)
    user_name  = mapped_column(String(255), nullable=False)   # denormalised from JWT
    skill_name = mapped_column(String(128), nullable=False)
    level      = mapped_column(Integer, nullable=False, default=1)  # 1..5
    notes      = mapped_column(Text, nullable=True)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(),
                               onupdate=func.now(), nullable=False)

    def to_dict(self):
        return {
            "id":         self.id,
            "user_id":    self.user_id,
            "user_name":  self.user_name,
            "skill_name": self.skill_name,
            "level":      self.level,
            "notes":      self.notes,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
