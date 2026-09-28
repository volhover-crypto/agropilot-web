# backend/catalogs/models.py -- §45: SQLAlchemy-модели НСИ (миграция 041)
#
# Гибридная архитектура: реальная таблица на каждый справочник (целостность,
# UNIQUE, FK) + generic-движок поверх декларативного реестра (registry.py).
# Служебные колонки всех справочников — в CatalogMixin (код/статус/аудит-поля).

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import JSONB

# JSONB на проде, JSON на sqlite (тесты гоняются на sqlite+aiosqlite)
JsonType = JSONB().with_variant(JSON(), "sqlite")
# BIGINT id на проде; на sqlite BIGINT-PK не автоинкрементится (нужен INTEGER)
IdType = Integer().with_variant(BigInteger(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CatalogMixin:
    """Служебные колонки всех справочников НСИ (§45.5)."""

    id:         Mapped[int]              = mapped_column(IdType, primary_key=True, autoincrement=True)
    code:       Mapped[str]              = mapped_column(Text, unique=True, nullable=False)
    name:       Mapped[str]              = mapped_column(Text, nullable=False)
    is_system:  Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    status:     Mapped[str]              = mapped_column(String(16), nullable=False, default="active")
    sort_order: Mapped[int]              = mapped_column(Integer, nullable=False, default=0)
    attrs:      Mapped[dict]             = mapped_column(JsonType, nullable=False, default=dict)
    created_by: Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_utcnow)
    updated_by: Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_utcnow)


class Unit(CatalogMixin, Base):
    __tablename__ = "nsi_units"

    symbol:     Mapped[str] = mapped_column(Text, nullable=False, default="")
    kind:       Mapped[str] = mapped_column(Text, nullable=False, default="шт")
    intl_code:  Mapped[str] = mapped_column(Text, nullable=False, default="")


class Currency(CatalogMixin, Base):
    __tablename__ = "nsi_currencies"

    symbol:     Mapped[str] = mapped_column(Text, nullable=False, default="")
    minor_unit: Mapped[int] = mapped_column(Integer, nullable=False, default=2)


class Region(CatalogMixin, Base):
    __tablename__ = "nsi_regions"

    level:      Mapped[str] = mapped_column(Text, nullable=False, default="region")
    parent_id:  Mapped[Optional[int]] = mapped_column(
        IdType, nullable=True)  # FK self RESTRICT живёт в миграции 041


class Tag(CatalogMixin, Base):
    __tablename__ = "nsi_tags"

    color:       Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")


class CatalogAuditEntry(Base):
    """Журнал изменений НСИ — append-only, общий для всех справочников (§45.4)."""

    __tablename__ = "catalog_audit"

    id:         Mapped[int]              = mapped_column(IdType, primary_key=True, autoincrement=True)
    entity:     Mapped[str]              = mapped_column(Text, nullable=False, index=True)
    entity_id:  Mapped[int]              = mapped_column(IdType, nullable=False)
    action:     Mapped[str]              = mapped_column(Text, nullable=False)
    diff:       Mapped[dict]             = mapped_column(JsonType, nullable=False, default=dict)
    user_id:    Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    user_name:  Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_utcnow)
