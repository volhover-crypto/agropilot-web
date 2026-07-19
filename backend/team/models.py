# backend/team/models.py -- AgroPILOT SQLAlchemy model for team table
#
# Table: team (Stage 2 / Блок E: +competencies, permissions, status, role_key)
# Schema captured from prod DB after 004_team_rbac.sql.

from typing import Optional

from sqlalchemy import String, Integer, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class TeamMember(Base):
    __tablename__ = "team"

    id:           Mapped[str]            = mapped_column(String(16), primary_key=True)
    name:         Mapped[str]            = mapped_column(Text, nullable=False)
    role:         Mapped[str]            = mapped_column(Text, nullable=False)
    avatar:       Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
    cap:          Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    can_confirm:  Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # Stage 2 / Блок E
    competencies: Mapped[list]           = mapped_column(JSONB, nullable=False, default=list)
    permissions:  Mapped[list]           = mapped_column(JSONB, nullable=False, default=list)
    status:       Mapped[str]            = mapped_column(String(16), nullable=False, default="active")
    role_key:     Mapped[Optional[str]]  = mapped_column(String(32), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "name":         self.name,
            "role":         self.role,
            "avatar":       self.avatar,
            "cap":          self.cap,
            "can_confirm":  self.can_confirm,
            "competencies": self.competencies if self.competencies is not None else [],
            "permissions":  self.permissions if self.permissions is not None else [],
            "status":       self.status,
            "role_key":     self.role_key,
        }
