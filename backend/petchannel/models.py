# backend/petchannel/models.py -- §42: channel_bindings

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import Integer, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

VALID_MASKS = ("digest", "questions", "insights")


class Base(DeclarativeBase):
    pass


def parse_mask(mask: str) -> set[str]:
    return {m for m in (mask or "").split(",") if m in VALID_MASKS}


def render_mask(masks: set[str] | list[str]) -> str:
    return ",".join(sorted(set(masks) & set(VALID_MASKS)))


def gen_bind_code() -> str:
    import secrets

    return f"{secrets.randbelow(1_000_000):06d}"


def code_expires(now: datetime, minutes: int = 15) -> datetime:
    return now + timedelta(minutes=minutes)


def session_key(user_id: str, chat_id: str) -> str:
    """Ключ сессии ПЕТРУШКИ (§42, паттерн ключей Octop): отдельная нить,
    не пересекается с веб-чатом (<user_id>:web, §41.3)."""
    return f"{user_id}:telegram:{chat_id}"


class ChannelBinding(Base):
    __tablename__ = "channel_bindings"

    id:                Mapped[int]              = mapped_column(Integer, primary_key=True)
    user_id:           Mapped[str]              = mapped_column(String(16), nullable=False)
    channel:           Mapped[str]              = mapped_column(String(16), nullable=False, default="telegram")
    chat_id:           Mapped[Optional[str]]    = mapped_column(String(64), nullable=True)
    verified_at:       Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    notify_mask:       Mapped[str]              = mapped_column(String(64), nullable=False, default="")
    bind_code:         Mapped[Optional[str]]    = mapped_column(String(8), nullable=True)
    bind_code_expires: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at:        Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    def masks(self) -> set[str]:
        return parse_mask(self.notify_mask)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "channel": self.channel,
            "chat_id": self.chat_id,
            "verified": self.verified_at is not None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "notify_mask": sorted(self.masks()),
            "has_pending_code": bool(
                self.bind_code and self.bind_code_expires
                and self.bind_code_expires > datetime.now(timezone.utc)
            ),
        }
