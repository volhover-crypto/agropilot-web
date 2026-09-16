# backend/meteo/engine.py -- §34: детерминированные правила поверх агрегатов
#
# Правила из crop_rules (БД, редактируемые): risk -> минусы/угрозы,
# window -> благоприятные окна. Оценка кодом, LLM — только текст резюме.

from datetime import timedelta

_OPS = {
    "<":  lambda a, b: a is not None and a < b,
    ">":  lambda a, b: a is not None and a > b,
    "<=": lambda a, b: a is not None and a <= b,
    ">=": lambda a, b: a is not None and a >= b,
    "=":  lambda a, b: a is not None and abs(a - b) < 1e-9,
}


def current_phase_month() -> int:
    """Месяц фенофазы — по московскому времени (рабочее время системы)."""
    from datetime import datetime, timezone
    return datetime.now(timezone(timedelta(hours=3))).month


def evaluate(rules: list, metrics: dict, phase: str | None) -> tuple[list, list]:
    """rules — ORM-строки CropRule. Возвращает (risks, windows)."""
    risks, windows = [], []
    for r in rules:
        if not r.active:
            continue
        if r.phase and phase and r.phase != phase:
            continue
        value = metrics.get(r.metric)
        if value is None:
            continue
        threshold = float(r.threshold)
        if not _OPS.get(r.op, lambda a, b: False)(value, threshold):
            continue
        item = {
            "metric": r.metric, "value": value,
            "op": r.op, "threshold": threshold,
            "severity": r.severity, "text": r.recommendation,
        }
        (risks if r.kind == "risk" else windows).append(item)
    order = {"critical": 0, "warn": 1, "info": 2}
    risks.sort(key=lambda x: order.get(x["severity"], 3))
    return risks, windows
