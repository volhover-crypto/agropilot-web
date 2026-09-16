# tests/test_agents_dashboard.py -- §33: юнит-тесты алертов лимитов и «молчания»
# Запуск: venv/bin/python -m pytest tests/ -q

from datetime import datetime, timedelta, timezone

from backend.agents.routes import (
    _LIMIT_DEFAULTS, _agent_limits, _limit_alerts, _staleness_hours,
)


def _day(cost=0.0, tokens=0, errors=0):
    return {"runs": 1, "errors": errors, "tokens": tokens,
            "cost_usd": cost, "items": 0}


def _week(cost=0.0):
    return {"runs": 2, "errors": 0, "tokens": 0, "cost_usd": cost, "items": 0}


class _Card:
    def __init__(self, limits=None):
        self.limits = limits


def test_agent_limits_merge():
    # пустая карточка -> дефолты
    assert _agent_limits(_Card(None)) == _LIMIT_DEFAULTS
    # карточка переопределяет только заданные ключи
    merged = _agent_limits(_Card({"cost_usd_day": 0.5}))
    assert merged["cost_usd_day"] == 0.5
    assert merged["cost_usd_week"] == _LIMIT_DEFAULTS["cost_usd_week"]


def test_limit_alerts_cost_day():
    alerts = _limit_alerts("a2", _day(cost=2.0), _week(), dict(_LIMIT_DEFAULTS))
    kinds = [a["kind"] for a in alerts]
    assert kinds == ["cost_day"]
    assert alerts[0]["agent_code"] == "a2"


def test_limit_alerts_none_when_within():
    assert _limit_alerts("a2", _day(cost=0.9, tokens=1000, errors=1),
                         _week(cost=4.0), dict(_LIMIT_DEFAULTS)) == []


def test_limit_alerts_custom_zero_disables():
    # лимит 0 в карточке = контроль отключён (нет сравнения >)
    limits = {"cost_usd_day": 0, "cost_usd_week": 0,
              "tokens_day": 0, "errors_day": 0}
    assert _limit_alerts("a2", _day(cost=99, tokens=10**9, errors=99),
                         _week(cost=99), limits) == []


def test_limit_alerts_multiple():
    alerts = _limit_alerts("a4", _day(cost=5.0, tokens=300_000, errors=6),
                           _week(cost=10.0), dict(_LIMIT_DEFAULTS))
    assert {a["kind"] for a in alerts} == {"cost_day", "cost_week",
                                           "tokens_day", "errors_day"}


def test_staleness_scheduled_agent():
    fresh = {"started_at": datetime.now(timezone.utc).isoformat()}
    old = {"started_at": (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()}
    assert _staleness_hours("a1", True, fresh) < 1      # a1 — ежечасный, только что
    assert _staleness_hours("a1", True, old) > 9        # молчит ~10 ч
    assert _staleness_hours("a1", True, None) == 24.0   # нет прогонов: every(1ч)*24
    # наивная строка времени трактуется как UTC
    naive = {"started_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}
    assert _staleness_hours("a6", True, naive) is not None


def test_staleness_unscheduled_and_paused():
    # без расписания (a2..a5, a7) и на паузе -> None
    assert _staleness_hours("a7", True, {"started_at": "2000-01-01T00:00:00+00:00"}) is None
    assert _staleness_hours("a1", False, None) is None
    assert _staleness_hours("a1", True, {"started_at": "мусор"}) is None
