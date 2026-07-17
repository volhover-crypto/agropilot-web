# backend/team/models.py -- AgroPILOT SQLAlchemy model for team table
#
# Table: team
# Schema captured from prod DB after seed_prod.sql execution (fix issue#1-3).

from typing import Optional

from sqlalchemy import String, Integer, Boolean, Text
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class TeamMember(Base):
    __tablename__ = "team"

    id:          Mapped[str]           = mapped_column(String(64), primary_key=True)
    name:        Mapped[str]           = mapped_column(Text, nullable=False)
    role:        Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar:      Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cap:         Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    can_confirm: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "name":        self.name,
            "role":        self.role,
            "avatar":      self.avatar,
            "cap":         self.cap,
            "can_confirm": self.can_confirm,
        }
