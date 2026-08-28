# backend/monitoring/models.py -- AgroPILOT Monitoring (A-3, CONTRACTS.md §17)
#
# ВНИМАНИЕ: таблица field_alerts НЕ принадлежит этому репозиторию — её наполняют
# внешние процессы (mia_monitor.py и др., см. §17.1). Модель здесь — read-only
# отражение существующей схемы. Миграции на эту таблицу в проекте НЕТ и быть не
# должно; любые записи/изменения схемы делает владелец таблицы.
# Локальный Base БЕЗ ORM-ForeignKey (протокол 4 дефектов).

from typing import Optional
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


# §17.3: допустимые уровни. Сравнение и выдача — в нижнем регистре, потому что
# в таблице встречаются и CRITICAL/WARNING (§17.2 п.2). Данные НЕ правим.
VALID_LEVELS = ("info", "ok", "warning", "critical")


class FieldAlert(Base):
    __tablename__ = "field_alerts"

    id:         Mapped[int]                 = mapped_column(Integer, primary_key=True)
    source:     Mapped[Optional[str]]       = mapped_column(String(64), nullable=True)
    category:   Mapped[Optional[str]]       = mapped_column(String(32), nullable=True)
    parameter:  Mapped[Optional[str]]       = mapped_column(String(128), nullable=True)
    value:      Mapped[Optional[Decimal]]   = mapped_column(Numeric, nullable=True)
    unit:       Mapped[Optional[str]]       = mapped_column(String(16), nullable=True)
    level:      Mapped[Optional[str]]       = mapped_column(String(16), nullable=True)
    message:    Mapped[Optional[str]]       = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]]  = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    def to_dict(self, matched_focus=None) -> dict:
        return {
            "id":            self.id,
            "source":        self.source,
            "category":      self.category,
            "parameter":     self.parameter,
            # numeric -> float, чтобы не отдавать Decimal в JSON
            "value":         float(self.value) if self.value is not None else None,
            "unit":          self.unit,
            "level":         (self.level or "").lower() or None,
            "message":       self.message,
            "created_at":    self.created_at.isoformat() if self.created_at else None,
            "matched_focus": matched_focus or [],
        }
