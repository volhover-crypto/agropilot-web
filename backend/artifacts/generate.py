# backend/artifacts/generate.py -- A5: рендер артефакта по шаблону (§27)
#
# Контекст переменных: карточка сделки (deal.*) + клиента (client.*,
# включая реквизиты ЕГРЮЛ из §26). Подстановка {{a.b}}; отсутствующие
# переменные остаются как есть и перечисляются в missing — оператор
# дозаполняет руками (human-in-the-loop по ТЗ п. 8.6).

import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.artifacts.models import Artifact
from backend.artifacts.template_models import ArtifactTemplate
from backend.deals.models import Deal
from backend.clients.models import Client

_VAR = re.compile(r"\{\{\s*([a-z_][a-z0-9_.]*)\s*\}\}")


def _ctx_from(deal: Optional[Deal], client: Optional[Client]) -> dict:
    req = (getattr(client, "requisites", None) or {}) if client else {}
    return {
        "deal": {
            "id": deal.id if deal else "",
            "name": deal.name if deal else "",
            "stage": deal.stage if deal else "",
            "need_type": deal.need_type or "" if deal else "",
            "region": deal.region or "" if deal else "",
            "score": deal.score or "" if deal else "",
        },
        "client": {
            "id": client.id if client else "",
            "name": client.name if client else "",
            "inn": (client.inn or "") if client else "",
            "address": req.get("address") or "",
            "ogrn": req.get("ogrn") or "",
            "kpp": req.get("kpp") or "",
            "ceo": (req.get("ceo") or "").replace(":", ", ").split(",")[-1].strip()
                   if req.get("ceo") else "",
            "region": (client.region or "") if client else "",
        },
    }


def render(template: str, ctx: dict) -> tuple[str, list]:
    missing = []

    def sub(m):
        path = m.group(1).split(".")
        val = ctx
        for p in path:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                missing.append(m.group(1))
                return m.group(0)
        return str(val)

    return _VAR.sub(sub, template), missing


async def generate_artifact(
    db: AsyncSession, template_code: str, deal_id: Optional[str]
) -> tuple[Artifact, list]:
    """Шаблон + контекст -> черновик Artifact (status=draft)."""
    tpl = (await db.execute(
        __import__("sqlalchemy").select(ArtifactTemplate)
        .where(ArtifactTemplate.code == template_code)
    )).scalars().first()
    if tpl is None:
        raise KeyError(f"шаблон {template_code!r} не найден")

    deal = await db.get(Deal, deal_id) if deal_id else None
    client = None
    if deal and deal.client_id:
        client = await db.get(Client, deal.client_id)

    ctx = _ctx_from(deal, client)
    title, miss_t = render(tpl.title_template, ctx)
    body, miss_b = render(tpl.body_template, ctx)

    art = Artifact(
        kind=tpl.kind,
        title=title[:300],
        body=body,
        deal_id=deal_id,
        client_id=(client.id if client else None),
        status="draft",
        type="generated",
    )
    db.add(art)
    await db.flush()
    return art, miss_t + miss_b
