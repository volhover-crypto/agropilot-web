# backend/petchannel/push.py -- §42: исходящие push по notify_mask (opt-in)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.petchannel.models import ChannelBinding
from backend.petchannel.tg import send_message


async def notify_mask(db: AsyncSession, kind: str, text: str) -> int:
    """Доставить text всем привязанным с включённой подпиской kind.
    Возвращает число успешных доставок. Недоставка не бросает исключение --
    повтор в следующем цикле (риск ТЗ §6: digest не теряется)."""
    rows = (await db.execute(select(ChannelBinding).where(
        ChannelBinding.channel == "telegram",
        ChannelBinding.verified_at.isnot(None),
    ))).scalars().all()
    sent = 0
    for row in rows:
        if kind not in row.masks():
            continue
        if send_message(row.chat_id, text):
            sent += 1
    return sent
