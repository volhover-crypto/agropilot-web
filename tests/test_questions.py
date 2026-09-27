# tests/test_questions.py -- О3 (§40): TTL, обучающие сигналы, идемпотентность

from datetime import datetime, timedelta, timezone

from backend.questions.models import (
    can_answer,
    compute_expires,
    is_learning_signal,
    question_ttl_hours,
)


class _Q:
    """Двойник AgentQuestion для чистых проверок логики."""

    def __init__(self, status="asked", expires_at=None, answered_at=None):
        self.status = status
        self.expires_at = expires_at
        self.answered_at = answered_at


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def test_compute_expires_default_ttl_and_custom():
    exp = compute_expires(NOW)
    assert exp - NOW == timedelta(hours=72)
    assert compute_expires(NOW, 5) - NOW == timedelta(hours=5)


def test_ttl_env_override(monkeypatch):
    monkeypatch.setenv("AGENT_QUESTION_TTL", "48")
    assert question_ttl_hours() == 48
    monkeypatch.setenv("AGENT_QUESTION_TTL", "мусор")  # мусор -> default 72
    assert question_ttl_hours() == 72


def test_can_answer_until_ttl():
    assert can_answer(_Q(expires_at=NOW + timedelta(hours=1)), NOW)
    assert can_answer(_Q(status="deferred", expires_at=NOW + timedelta(hours=1)), NOW)
    # истёк по времени -- не принимается, даже если статус ещё asked (ленивое TTL)
    assert not can_answer(_Q(expires_at=NOW - timedelta(minutes=1)), NOW)
    assert not can_answer(_Q(status="expired", expires_at=NOW + timedelta(hours=1)), NOW)
    assert not can_answer(_Q(status="answered", expires_at=NOW + timedelta(hours=1)), NOW)
    assert not can_answer(None, NOW)


def test_expired_question_is_not_learning_signal():
    # DoD О3-2: вопрос старше TTL в обучающие сигналы Q-метрики не попадает
    assert is_learning_signal(_Q(status="answered",
                                 expires_at=NOW + timedelta(hours=1),
                                 answered_at=NOW))
    assert not is_learning_signal(_Q(status="expired",
                                     expires_at=NOW - timedelta(hours=1),
                                     answered_at=NOW))
    # ответ «после истечения» -- тоже не сигнал
    assert not is_learning_signal(_Q(status="answered",
                                     expires_at=NOW - timedelta(minutes=5),
                                     answered_at=NOW))
    assert not is_learning_signal(_Q(status="asked", expires_at=NOW + timedelta(hours=1)))
    assert not is_learning_signal(None)
