# backend/packages/models.py -- AgroPILOT Packages model
#
# Table: packages (M10-4: пакеты услуг/КП)

from typing import Optional
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Text, Integer, Numeric
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped

class Base(DeclarativeBase):
    pass

class Package(Base):
    __tablename__ = "packages"

    id:          Mapped[int]              = mapped_column(Integer, primary_key=True)
    title:       Mapped[str]              = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    price:       Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    status:      Mapped[str]              = mapped_column(String(16), nullable=False, default="draft")
    deal_id:     Mapped[Optional[str]]    = mapped_column(String(16), nullable=True)
    created_at:  Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "title":       self.title,
            "description": self.description,
            "price":       float(self.price) if self.price is not None else None,
            "status":      self.status,
            "deal_id":     self.deal_id,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
        }
