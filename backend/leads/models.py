# backend/leads/models.py -- AgroPILOT Leads model (A-6.1, CONTRACTS.md 14)
# FK leads.converted_client_id -> clients(id) создан в миграции 014_leads.sql,
# в ORM-модели ForeignKey НЕТ (протокол 4 дефектов).

from typing import Optional
from datetime import date, datetime

from sqlalchemy import String, Text, Date
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"

    id:                  Mapped[str]                = mapped_column(String(16), primary_key=True)
    name:                Mapped[str]                = mapped_column(String(255), nullable=False)
    status:              Mapped[str]                = mapped_column(String(16), nullable=False)
    contact_person:      Mapped[Optional[str]]      = mapped_column(String(255), nullable=True)
    phone:               Mapped[Optional[str]]      = mapped_column(String(32), nullable=True)
    phone_extra:         Mapped[Optional[list]]     = mapped_column(ARRAY(Text), nullable=True)
    email:               Mapped[Optional[str]]      = mapped_column(String(255), nullable=True)
    owner:               Mapped[Optional[str]]      = mapped_column(String(64), nullable=True)
    region:              Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)
    industry:            Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)
    ext_id:              Mapped[Optional[str]]      = mapped_column(String(32), nullable=True)
    comment:             Mapped[Optional[str]]      = mapped_column(String(255), nullable=True)
    source:              Mapped[Optional[str]]      = mapped_column(String(32), nullable=True)
    converted_client_id: Mapped[Optional[str]]      = mapped_column(String(16), nullable=True)
    created_at:          Mapped[Optional[date]]     = mapped_column(Date, nullable=True)
    imported_at:         Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    next_action:         Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
    next_action_at:      Mapped[Optional[date]]     = mapped_column(Date, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":                  self.id,
            "name":                self.name,
            "status":              self.status,
            "contact_person":      self.contact_person,
            "phone":               self.phone,
            "phone_extra":         self.phone_extra or [],
            "email":               self.email,
            "owner":               self.owner,
            "region":              self.region,
            "industry":            self.industry,
            "ext_id":              self.ext_id,
            "comment":             self.comment,
            "source":              self.source,
            "converted_client_id": self.converted_client_id,
            "created_at":          self.created_at.isoformat() if self.created_at else None,
            "imported_at":         self.imported_at.isoformat() if self.imported_at else None,
            "next_action":         self.next_action,
            "next_action_at":      self.next_action_at.isoformat() if self.next_action_at else None,
        }
