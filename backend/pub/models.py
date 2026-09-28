# backend/pub/models.py -- §46: SQLAlchemy-модели кросспостинга (миграция 046)
#
# pub_channels -- реестр каналов публикаций (статус active/frozen,
# секреты платформ в secrets JSONB -- наружу никогда не отдаются);
# pub_posts/pub_post_channels -- посты и результаты по каналам (Ф3+).

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import JSONB

# JSONB на проде, JSON на sqlite (тесты); BIGINT id на проде (см. §45)
JsonType = JSONB().with_variant(JSON(), "sqlite")
IdType = Integer().with_variant(BigInteger(), "postgresql")


class Base(DeclarativeBase):
    pass


class PubChannel(Base):
    __tablename__ = "pub_channels"

    id: Mapped[int] = mapped_column(IdType, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    target: Mapped[Optional[str]] = mapped_column(Text)
    secrets: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    template: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    frozen_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class PubPost(Base):
    __tablename__ = "pub_posts"

    id: Mapped[int] = mapped_column(IdType, primary_key=True, autoincrement=True)
    body_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media: Mapped[list] = mapped_column(JsonType, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class PubPostChannel(Base):
    __tablename__ = "pub_post_channels"

    post_id: Mapped[int] = mapped_column(
        IdType, primary_key=True, autoincrement=False)
    channel_id: Mapped[int] = mapped_column(
        IdType, primary_key=True, autoincrement=False)
    body_override: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    platform_post_id: Mapped[Optional[str]] = mapped_column(Text)
    error: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
