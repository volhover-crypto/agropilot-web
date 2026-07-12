# backend/strategy/models.py -- AgroPILOT M4 Strategy ORM
# Single-row table: id == "strategy_main" (CONTRACTS §4)
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    pass


STRATEGY_ID = "strategy_main"


class Strategy(Base):
    __tablename__ = "strategy"

    id         = mapped_column(String(64), primary_key=True, default=STRATEGY_ID)
    scenarios  = mapped_column(JSONB, nullable=False, server_default="[]")
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = mapped_column(String(64), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "scenarios": self.scenarios if self.scenarios is not None else [],
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by,
        }
