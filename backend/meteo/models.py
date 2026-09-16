# backend/meteo/models.py -- §34: MIA-погодный агро-консультант (миграция 033)
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, Boolean, Numeric, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass


class Crop(Base):
    __tablename__ = "crops"

    id:         Mapped[int]            = mapped_column(Integer, primary_key=True)
    code:       Mapped[str]            = mapped_column(Text, unique=True, nullable=False)
    name:       Mapped[str]            = mapped_column(Text, nullable=False)
    active:     Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {"id": self.id, "code": self.code, "name": self.name,
                "active": self.active}


class GeoPoint(Base):
    __tablename__ = "geo_points"

    id:         Mapped[int]            = mapped_column(Integer, primary_key=True)
    name:       Mapped[str]            = mapped_column(Text, nullable=False)
    lat:        Mapped[float]          = mapped_column(Numeric(8, 5), nullable=False)
    lon:        Mapped[float]          = mapped_column(Numeric(8, 5), nullable=False)
    active:     Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name,
                "lat": float(self.lat) if self.lat is not None else None,
                "lon": float(self.lon) if self.lon is not None else None,
                "active": self.active}


class CropPhase(Base):
    __tablename__ = "crop_phases"
    __table_args__ = (UniqueConstraint("crop_code", "month", name="uq_crop_phase_month"),)

    id:         Mapped[int]            = mapped_column(Integer, primary_key=True)
    crop_code:  Mapped[str]            = mapped_column(Text, nullable=False)
    month:      Mapped[int]            = mapped_column(Integer, nullable=False)
    phase:      Mapped[str]            = mapped_column(Text, nullable=False)
    note:       Mapped[Optional[str]]  = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {"id": self.id, "crop_code": self.crop_code, "month": self.month,
                "phase": self.phase, "note": self.note}


class CropRule(Base):
    __tablename__ = "crop_rules"

    id:              Mapped[int]            = mapped_column(Integer, primary_key=True)
    crop_code:       Mapped[str]            = mapped_column(Text, nullable=False)
    phase:           Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
    kind:            Mapped[str]            = mapped_column(String(8), nullable=False, default="risk")
    metric:          Mapped[str]            = mapped_column(Text, nullable=False)
    op:              Mapped[str]            = mapped_column(String(2), nullable=False)
    threshold:       Mapped[float]          = mapped_column(Numeric, nullable=False)
    severity:        Mapped[str]            = mapped_column(String(10), nullable=False, default="info")
    recommendation:  Mapped[str]            = mapped_column(Text, nullable=False)
    active:          Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)

    def to_dict(self) -> dict:
        return {"id": self.id, "crop_code": self.crop_code, "phase": self.phase,
                "kind": self.kind, "metric": self.metric, "op": self.op,
                "threshold": float(self.threshold) if self.threshold is not None else None,
                "severity": self.severity,
                "recommendation": self.recommendation, "active": self.active}


class MeteoSubscription(Base):
    __tablename__ = "meteo_subscriptions"
    __table_args__ = (UniqueConstraint("point_id", "crop_code", name="uq_sub_point_crop"),)

    id:         Mapped[int]            = mapped_column(Integer, primary_key=True)
    point_id:   Mapped[int]            = mapped_column(Integer, nullable=False)
    crop_code:  Mapped[str]            = mapped_column(Text, nullable=False)
    horizons:   Mapped[list]           = mapped_column(ARRAY(Integer), nullable=False, default=[24])
    active:     Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {"id": self.id, "point_id": self.point_id, "crop_code": self.crop_code,
                "horizons": list(self.horizons or []), "active": self.active}


class WeatherRun(Base):
    __tablename__ = "weather_runs"

    id:            Mapped[int]            = mapped_column(Integer, primary_key=True)
    point_id:      Mapped[int]            = mapped_column(Integer, nullable=False)
    crop_code:     Mapped[str]            = mapped_column(Text, nullable=False)
    horizon_h:     Mapped[int]            = mapped_column(Integer, nullable=False)
    ran_at:        Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    metrics:       Mapped[dict]           = mapped_column(JSONB, nullable=False, default=dict)
    risks:         Mapped[list]           = mapped_column(JSONB, nullable=False, default=list)
    windows:       Mapped[list]           = mapped_column(JSONB, nullable=False, default=list)
    summary:       Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
    telegram_sent: Mapped[bool]           = mapped_column(Boolean, nullable=False, default=False)
    critical:      Mapped[bool]           = mapped_column(Boolean, nullable=False, default=False)

    def to_dict(self, point_name: str = None, crop_name: str = None) -> dict:
        return {"id": self.id, "point_id": self.point_id, "crop_code": self.crop_code,
                "point_name": point_name, "crop_name": crop_name,
                "horizon_h": self.horizon_h,
                "ran_at": self.ran_at.isoformat() if self.ran_at else None,
                "metrics": self.metrics or {}, "risks": self.risks or [],
                "windows": self.windows or [], "summary": self.summary,
                "telegram_sent": self.telegram_sent, "critical": self.critical}
