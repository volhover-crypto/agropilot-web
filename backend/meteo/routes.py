# backend/meteo/routes.py -- §34: MIA-погодный агро-консультант
#
# Mount: app.include_router(meteo_router, prefix="/agropilot/api/v1")
# Справочники: /v1/meteo/points, /crops, /rules, /subs, /phases (CRUD)
# Прогон: POST /v1/meteo/run {point_id, crop_code, horizon_h, send}
# История: GET /v1/meteo/runs, GET /v1/meteo/latest
# Контракт: {"ok": true, "data": ...}; справочники/запуск — manager/admin.

import os
import json
import urllib.request
from typing import Optional, List

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.deps import get_db, get_current_user
from backend.common.errors import NotFoundError, ValidationError
from backend.common.llm import llm_configured, LLMError
from backend.agents.runlog import llm_call_logged
from backend.agents.registry import get_agent_prompt
from backend.meteo.models import (Crop, GeoPoint, CropPhase, CropRule,
                                  MeteoSubscription, WeatherRun)
from backend.meteo import provider
from backend.meteo.engine import evaluate, current_phase_month

meteo_router = APIRouter(prefix="/meteo", tags=["meteo"])

_ALLOWED_HORIZONS = (24, 72, 120)
_ALLOWED_METRICS = ("temp_min", "temp_max", "precip_sum", "humidity_avg", "wind_max")


def _ok(data):
    return {"ok": True, "data": data}


async def _is_manager(db: AsyncSession, user) -> bool:
    """Как в §11/§13: admin или роль manager (для краткости — member.role_key)."""
    from backend.team.models import TeamMember
    m = await db.get(TeamMember, user.id)
    return bool(m and m.role_key in ("admin", "manager"))


# ---------- справочник: гео-пункты ----------

class PointBody(BaseModel):
    name: str
    lat: float
    lon: float
    active: Optional[bool] = None


@meteo_router.get("/points")
async def list_points(db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    rows = (await db.execute(select(GeoPoint).order_by(GeoPoint.id))).scalars().all()
    return _ok([r.to_dict() for r in rows])


@meteo_router.post("/points")
async def create_point(payload: PointBody, db: AsyncSession = Depends(get_db),
                       user=Depends(get_current_user)):
    if not await _is_manager(db, user):
        raise ValidationError("справочники погоды — только менеджер/админ")
    if not (-90 <= payload.lat <= 90 and -180 <= payload.lon <= 180):
        raise ValidationError("широтa/долгота вне диапазона")
    p = GeoPoint(name=payload.name.strip(), lat=payload.lat, lon=payload.lon,
                 active=payload.active if payload.active is not None else True,
                 created_at=datetime.now(timezone.utc))
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _ok(p.to_dict())


@meteo_router.delete("/points/{point_id}")
async def delete_point(point_id: int, db: AsyncSession = Depends(get_db),
                       user=Depends(get_current_user)):
    if not await _is_manager(db, user):
        raise ValidationError("справочники погоды — только менеджер/админ")
    p = await db.get(GeoPoint, point_id)
    if not p:
        raise NotFoundError(f"пункт {point_id} не найден")
    await db.delete(p)
    await db.commit()
    return _ok({"deleted": point_id})


# ---------- справочник: культуры ----------

class CropBody(BaseModel):
    code: str
    name: str
    active: Optional[bool] = None


@meteo_router.get("/crops")
async def list_crops(db: AsyncSession = Depends(get_db),
                     user=Depends(get_current_user)):
    rows = (await db.execute(select(Crop).order_by(Crop.id))).scalars().all()
    return _ok([r.to_dict() for r in rows])


@meteo_router.post("/crops")
async def create_crop(payload: CropBody, db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    if not await _is_manager(db, user):
        raise ValidationError("справочники погоды — только менеджер/админ")
    code = payload.code.strip().lower()
    if not code or not code.replace("_", "").isalnum():
        raise ValidationError("код культуры: латиница/цифры/подчёркивание")
    if (await db.execute(select(Crop).where(Crop.code == code))).scalars().first():
        raise ValidationError(f"культура с кодом {code} уже есть")
    c = Crop(code=code, name=payload.name.strip(),
             active=payload.active if payload.active is not None else True,
             created_at=datetime.now(timezone.utc))
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return _ok(c.to_dict())


@meteo_router.delete("/crops/{crop_id}")
async def delete_crop(crop_id: int, db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    if not await _is_manager(db, user):
        raise ValidationError("справочники погоды — только менеджер/админ")
    c = await db.get(Crop, crop_id)
    if not c:
        raise NotFoundError(f"культура {crop_id} не найдена")
    await db.delete(c)
    await db.commit()
    return _ok({"deleted": crop_id})


# ---------- фенофазы ----------

class PhaseBody(BaseModel):
    crop_code: str
    month: int
    phase: str
    note: Optional[str] = None


@meteo_router.get("/phases")
async def list_phases(crop_code: Optional[str] = None,
                      db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    q = select(CropPhase).order_by(CropPhase.crop_code, CropPhase.month)
    if crop_code:
        q = q.where(CropPhase.crop_code == crop_code)
    rows = (await db.execute(q)).scalars().all()
    return _ok([r.to_dict() for r in rows])


@meteo_router.put("/phases")
async def put_phase(payload: PhaseBody, db: AsyncSession = Depends(get_db),
                    user=Depends(get_current_user)):
    """Создать/обновить фенофазу месяца (одна на месяц)."""
    if not await _is_manager(db, user):
        raise ValidationError("справочники погоды — только менеджер/админ")
    if not (1 <= payload.month <= 12):
        raise ValidationError("месяц 1..12")
    row = (await db.execute(select(CropPhase).where(
        CropPhase.crop_code == payload.crop_code,
        CropPhase.month == payload.month))).scalars().first()
    if row:
        row.phase = payload.phase.strip()
        row.note = payload.note
    else:
        db.add(CropPhase(crop_code=payload.crop_code, month=payload.month,
                         phase=payload.phase.strip(), note=payload.note))
    await db.commit()
    return _ok({"crop_code": payload.crop_code, "month": payload.month})


# ---------- правила ----------

class RuleBody(BaseModel):
    crop_code: str
    phase: Optional[str] = None
    kind: str = "risk"
    metric: str
    op: str
    threshold: float
    severity: str = "info"
    recommendation: str
    active: Optional[bool] = None


@meteo_router.get("/rules")
async def list_rules(crop_code: Optional[str] = None,
                     db: AsyncSession = Depends(get_db),
                     user=Depends(get_current_user)):
    q = select(CropRule).order_by(CropRule.crop_code, CropRule.id)
    if crop_code:
        q = q.where(CropRule.crop_code == crop_code)
    rows = (await db.execute(q)).scalars().all()
    return _ok([r.to_dict() for r in rows])


@meteo_router.post("/rules")
async def create_rule(payload: RuleBody, db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    if not await _is_manager(db, user):
        raise ValidationError("справочники погоды — только менеджер/админ")
    if payload.kind not in ("risk", "window"):
        raise ValidationError("kind: risk | window")
    if payload.metric not in _ALLOWED_METRICS:
        raise ValidationError(f"metric: одна из {', '.join(_ALLOWED_METRICS)}")
    if payload.op not in ("<", ">", "<=", ">=", "="):
        raise ValidationError("op: < > <= >= =")
    if payload.kind == "window" and payload.severity == "critical":
        raise ValidationError("окно не может быть critical")
    r = CropRule(crop_code=payload.crop_code, phase=payload.phase,
                 kind=payload.kind, metric=payload.metric, op=payload.op,
                 threshold=payload.threshold, severity=payload.severity,
                 recommendation=payload.recommendation.strip(),
                 active=payload.active if payload.active is not None else True)
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _ok(r.to_dict())


@meteo_router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    if not await _is_manager(db, user):
        raise ValidationError("справочники погоды — только менеджер/админ")
    r = await db.get(CropRule, rule_id)
    if not r:
        raise NotFoundError(f"правило {rule_id} не найдено")
    await db.delete(r)
    await db.commit()
    return _ok({"deleted": rule_id})


# ---------- подписки ----------

class SubBody(BaseModel):
    point_id: int
    crop_code: str
    horizons: List[int] = [24]
    active: Optional[bool] = None


@meteo_router.get("/subs")
async def list_subs(db: AsyncSession = Depends(get_db),
                    user=Depends(get_current_user)):
    rows = (await db.execute(select(MeteoSubscription).order_by(MeteoSubscription.id))).scalars().all()
    return _ok([r.to_dict() for r in rows])


@meteo_router.post("/subs")
async def create_sub(payload: SubBody, db: AsyncSession = Depends(get_db),
                     user=Depends(get_current_user)):
    if not await _is_manager(db, user):
        raise ValidationError("подписки погоды — только менеджер/админ")
    if not payload.horizons:
        raise ValidationError("укажите хотя бы один горизонт")
    bad = [h for h in payload.horizons if h not in _ALLOWED_HORIZONS]
    if bad:
        raise ValidationError(f"горизонты только {list(_ALLOWED_HORIZONS)}")
    if not await db.get(GeoPoint, payload.point_id):
        raise NotFoundError(f"пункт {payload.point_id} не найден")
    dup = (await db.execute(select(MeteoSubscription).where(
        MeteoSubscription.point_id == payload.point_id,
        MeteoSubscription.crop_code == payload.crop_code))).scalars().first()
    if dup:
        raise ValidationError("подписка на эту пару уже есть")
    s = MeteoSubscription(point_id=payload.point_id, crop_code=payload.crop_code,
                          horizons=sorted(set(payload.horizons)),
                          active=payload.active if payload.active is not None else True,
                          created_at=datetime.now(timezone.utc))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return _ok(s.to_dict())


@meteo_router.delete("/subs/{sub_id}")
async def delete_sub(sub_id: int, db: AsyncSession = Depends(get_db),
                     user=Depends(get_current_user)):
    if not await _is_manager(db, user):
        raise ValidationError("подписки погоды — только менеджер/админ")
    s = await db.get(MeteoSubscription, sub_id)
    if not s:
        raise NotFoundError(f"подписка {sub_id} не найдена")
    await db.delete(s)
    await db.commit()
    return _ok({"deleted": sub_id})


# ---------- прогон ----------

async def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return False
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat, "text": text[:4000]}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8")).get("ok", False)
    except Exception:
        return False


class RunBody(BaseModel):
    point_id: int
    crop_code: str
    horizon_h: int = 24
    send: bool = False


@meteo_router.post("/run")
async def run_forecast(payload: RunBody, db: AsyncSession = Depends(get_db),
                       user=Depends(get_current_user)):
    """Прогон пайплайна: Open-Meteo -> правила -> LLM-резюме -> (Telegram)."""
    if not await _is_manager(db, user):
        raise ValidationError("прогон погоды — только менеджер/админ")
    if payload.horizon_h not in _ALLOWED_HORIZONS:
        raise ValidationError(f"горизонт только {list(_ALLOWED_HORIZONS)}")
    point = await db.get(GeoPoint, payload.point_id)
    if not point:
        raise NotFoundError(f"пункт {payload.point_id} не найден")

    days = 2 if payload.horizon_h <= 24 else 5
    raw = provider.fetch_hourly(float(point.lat), float(point.lon), forecast_days=days)
    metrics = provider.aggregate(raw, payload.horizon_h)

    month = current_phase_month()
    phase_row = (await db.execute(select(CropPhase).where(
        CropPhase.crop_code == payload.crop_code,
        CropPhase.month == month))).scalars().first()
    phase = phase_row.phase if phase_row else "фаза не задана"
    metrics["phase"] = phase

    rules = (await db.execute(select(CropRule).where(
        CropRule.crop_code == payload.crop_code))).scalars().all()
    risks, windows = evaluate(rules, metrics, phase)
    critical = any(r["severity"] == "critical" for r in risks)

    run = WeatherRun(point_id=point.id, crop_code=payload.crop_code,
                     horizon_h=payload.horizon_h,
                     ran_at=datetime.now(timezone.utc),
                     metrics=metrics, risks=risks, windows=windows,
                     critical=critical)
    db.add(run)
    await db.flush()

    summary = None
    if llm_configured():
        try:
            prompt = (
                f"Регион: {point.name}\nКультура: {payload.crop_code}\n"
                f"Фенофаза: {phase}\nГоризонт прогноза: {payload.horizon_h} ч\n"
                f"Агрегаты погоды: {json.dumps(metrics, ensure_ascii=False)}\n"
                f"Рассчитанные риски: {json.dumps(risks, ensure_ascii=False)}\n"
                f"Рассчитанные окна: {json.dumps(windows, ensure_ascii=False)}\n")
            system = await get_agent_prompt(db, "a-mia") or ""
            summary = await llm_call_logged(db, "a-mia", prompt, system,
                                            max_tokens=600, items=1,
                                            meta={"send": payload.send,
                                                  "point": point.name})
        except LLMError as e:
            summary = f"LLM недоступна ({str(e)[:100]}) — агрегат без резюме."
    run.summary = summary

    if payload.send and summary:
        head = ("‼️ КРИТИЧЕСКОЕ\n" if critical else "") + \
               f"🌡 MIA · {point.name} · {payload.crop_code} · {phase}\n" \
               f"Прогноз на {payload.horizon_h} ч: {metrics.get('temp_min')}…{metrics.get('temp_max')} °C, " \
               f"осадки {metrics.get('precip_sum')} мм, ветер до {metrics.get('wind_max')} м/с\n\n"
        run.telegram_sent = await send_telegram(head + (summary or ""))
    await db.commit()
    await db.refresh(run)
    return _ok(run.to_dict(point_name=point.name))


@meteo_router.get("/runs")
async def list_runs(point_id: Optional[int] = None, crop_code: Optional[str] = None,
                    limit: int = 20, db: AsyncSession = Depends(get_db),
                    user=Depends(get_current_user)):
    q = select(WeatherRun).order_by(WeatherRun.ran_at.desc()).limit(min(limit, 100))
    if point_id:
        q = q.where(WeatherRun.point_id == point_id)
    if crop_code:
        q = q.where(WeatherRun.crop_code == crop_code)
    rows = (await db.execute(q)).scalars().all()
    points = {p.id: p.name for p in (await db.execute(select(GeoPoint))).scalars()}
    return _ok([r.to_dict(point_name=points.get(r.point_id)) for r in rows])


@meteo_router.get("/latest")
async def latest_runs(db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    """Последний прогон по каждой активной подписке (для UI-карточек)."""
    subs = (await db.execute(select(MeteoSubscription).where(
        MeteoSubscription.active.is_(True)))).scalars().all()
    points = {p.id: p.name for p in (await db.execute(select(GeoPoint))).scalars()}
    out = []
    for s in subs:
        last = (await db.execute(select(WeatherRun).where(
            WeatherRun.point_id == s.point_id,
            WeatherRun.crop_code == s.crop_code)
            .order_by(WeatherRun.ran_at.desc()).limit(1))).scalars().first()
        out.append({
            "sub": s.to_dict(),
            "point_name": points.get(s.point_id),
            "last_run": last.to_dict(point_name=points.get(s.point_id)) if last else None,
        })
    return _ok(out)
