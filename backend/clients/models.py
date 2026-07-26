# backend/clients/models.py -- AgroPILOT Clients model
#
# Table: clients (A-6: Входящие клиенты)
# API-слой поверх СУЩЕСТВУЮЩЕЙ таблицы. FK deals->clients уже в БД (не в модели).

from typing import Optional
from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    id:         Mapped[str]                 = mapped_column(String(16), primary_key=True)
    name:       Mapped[str]                 = mapped_column(String(255), nullable=False)
    industry:   Mapped[Optional[str]]       = mapped_column(String(100), nullable=True)
    region:     Mapped[Optional[str]]       = mapped_column(String(100), nullable=True)
    need:       Mapped[Optional[list]]      = mapped_column(ARRAY(Text), nullable=True)
    health:     Mapped[Optional[str]]       = mapped_column(String(20), nullable=True)
    source:     Mapped[Optional[str]]       = mapped_column(String(32), nullable=True)
    status:     Mapped[Optional[str]]       = mapped_column(String(16), nullable=True)
    created_at: Mapped[Optional[datetime]]  = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "name":       self.name,
            "industry":   self.industry,
            "region":     self.region,
            "need":       self.need or [],
            "health":     self.health,
            "source":     self.source,
            "status":     self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
