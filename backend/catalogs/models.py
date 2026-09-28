# backend/catalogs/models.py -- §45: SQLAlchemy-модели НСИ (миграция 041)
#
# Гибридная архитектура: реальная таблица на каждый справочник (целостность,
# UNIQUE, FK) + generic-движок поверх декларативного реестра (registry.py).
# Служебные колонки всех справочников — в CatalogMixin (код/статус/аудит-поля).

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Float, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB

# JSONB на проде, JSON на sqlite (тесты гоняются на sqlite+aiosqlite)
JsonType = JSONB().with_variant(JSON(), "sqlite")
# BIGINT id на проде; на sqlite BIGINT-PK не автоинкрементится (нужен INTEGER)
IdType = Integer().with_variant(BigInteger(), "postgresql")


class _NumericCompat(TypeDecorator):
    """NUMERIC(p,s) на проде (asyncpg ждёт Decimal); на sqlite — float
    (sqlite3 не умеет биндить Decimal — конвертим в process_bind_param)."""
    impl = Numeric()
    cache_ok = True

    def __init__(self, precision: int = 14, scale: int = 2):
        super().__init__()
        self._precision, self._scale = precision, scale

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(Float())
        return dialect.type_descriptor(Numeric(self._precision, self._scale))

    def process_bind_param(self, value, dialect):
        if value is None or dialect.name != "sqlite":
            return value
        return float(value)


PriceType = _NumericCompat(14, 2)
RateType = _NumericCompat(5, 2)


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


class Contractor(CatalogMixin, Base):
    """Контрагенты: юрлица/ИП/физлица (§45, фаза 1b, миграция 042).
    Фаза 1d (045): иерархия — группы-подразделы (виноградники/сады/…)."""

    __tablename__ = "nsi_contractors"

    parent_id:     Mapped[Optional[int]] = mapped_column(IdType, nullable=True)  # FK self RESTRICT в 045
    is_group:      Mapped[bool]          = mapped_column(Boolean, nullable=False, default=False)
    name_full:     Mapped[str]           = mapped_column(Text, nullable=False, default="")
    kind:          Mapped[str]           = mapped_column(Text, nullable=False, default="jur")
    bin_iin:       Mapped[str]           = mapped_column(Text, nullable=False, default="")
    bank_name:     Mapped[str]           = mapped_column(Text, nullable=False, default="")
    bic_iban:      Mapped[str]           = mapped_column(Text, nullable=False, default="")
    account:       Mapped[str]           = mapped_column(Text, nullable=False, default="")
    legal_address: Mapped[str]           = mapped_column(Text, nullable=False, default="")
    region_id:     Mapped[Optional[int]] = mapped_column(IdType, nullable=True)  # FK в 042
    phone:         Mapped[str]           = mapped_column(Text, nullable=False, default="")
    email:         Mapped[str]           = mapped_column(Text, nullable=False, default="")
    website:       Mapped[str]           = mapped_column(Text, nullable=False, default="")
    comment:       Mapped[str]           = mapped_column(Text, nullable=False, default="")


class NomenclatureItem(CatalogMixin, Base):
    """Номенклатура: группы + элементы в одной таблице, 1С-стиль (§45, фаза 1b, 043)."""

    __tablename__ = "nsi_nomenclature"

    parent_id:   Mapped[Optional[int]]    = mapped_column(IdType, nullable=True)  # FK self RESTRICT в 043
    is_group:    Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    article:     Mapped[str]              = mapped_column(Text, nullable=False, default="")
    kind:        Mapped[str]              = mapped_column(Text, nullable=False, default="goods")
    unit_id:     Mapped[Optional[int]]    = mapped_column(IdType, nullable=True)  # FK units RESTRICT в 043
    vat_rate:    Mapped[Optional[Decimal]] = mapped_column(RateType, nullable=True)
    price_base:  Mapped[Optional[Decimal]] = mapped_column(PriceType, nullable=True)
    currency_id: Mapped[Optional[int]]    = mapped_column(IdType, nullable=True)  # FK currencies SET NULL


class CatalogType(Base):
    """Реестр пользовательских справочников (§45, фаза 1d, миграция 045).
    Создаются администратором из UI; записи — в nsi_user_items."""

    __tablename__ = "catalog_types"

    id:            Mapped[int]              = mapped_column(IdType, primary_key=True, autoincrement=True)
    key:           Mapped[str]              = mapped_column(Text, unique=True, nullable=False)
    title:         Mapped[str]              = mapped_column(Text, nullable=False)
    group_name:    Mapped[str]              = mapped_column(Text, nullable=False, default="Мои справочники")
    icon:          Mapped[str]              = mapped_column(Text, nullable=False, default="📁")
    hierarchical:  Mapped[bool]             = mapped_column(Boolean, nullable=False, default=True)
    code_prefix:   Mapped[str]              = mapped_column(Text, nullable=False, default="NSI")
    fields_schema: Mapped[list]             = mapped_column(JsonType, nullable=False, default=list)
    status:        Mapped[str]              = mapped_column(String(16), nullable=False, default="active")
    sort_order:    Mapped[int]              = mapped_column(Integer, nullable=False, default=0)
    created_by:    Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    created_at:    Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_utcnow)
    updated_by:    Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    updated_at:    Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_utcnow)


class UserItem(Base):
    """Записи пользовательских справочников (§45, фаза 1d, миграция 045).
    Значения пользовательских полей — в attrs JSONB; code уникален в пределах
    catalog_id (составной индекс в миграции), поэтому без CatalogMixin —
    он объявляет глобальный UNIQUE(code), который здесь не нужен."""

    __tablename__ = "nsi_user_items"

    id:         Mapped[int]              = mapped_column(IdType, primary_key=True, autoincrement=True)
    catalog_id: Mapped[int]              = mapped_column(IdType, nullable=False, index=True)
    code:       Mapped[str]              = mapped_column(Text, nullable=False)
    name:       Mapped[str]              = mapped_column(Text, nullable=False)
    parent_id:  Mapped[Optional[int]]    = mapped_column(IdType, nullable=True)  # FK self RESTRICT в 045
    is_group:   Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    is_system:  Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    status:     Mapped[str]              = mapped_column(String(16), nullable=False, default="active")
    sort_order: Mapped[int]              = mapped_column(Integer, nullable=False, default=0)
    attrs:      Mapped[dict]             = mapped_column(JsonType, nullable=False, default=dict)
    created_by: Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_utcnow)
    updated_by: Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_utcnow)


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
