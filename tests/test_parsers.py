# tests/test_parsers.py -- юнит-тесты чистых функций (без БД/сети)
# Запуск: venv/bin/python -m pytest tests/ -q

import json
import types

import pytest


# ---------- collectors: telegram web ----------

def test_telegram_web_parse(monkeypatch):
    import backend.news.collectors as c

    html = """
    <div class="tgme_widget_message_wrap"><div class="tgme_widget_message js-widget_message"
      data-post="Ch/101"><div class="tgme_widget_message_text js-message-text">Пост про
      <b>орошение</b> сада</div></div></div>
    <div class="tgme_widget_message_wrap"><div class="tgme_widget_message"
      data-post="Ch/102"><div class="tgme_widget_message_text">Второй пост</div></div></div>
    """
    monkeypatch.setattr(c.urllib.request, "urlopen",
                        lambda *a, **k: types.SimpleNamespace(
                            read=lambda: html.encode(), __enter__=lambda s: s,
                            __exit__=lambda s, *x: None))
    items = c.collect_telegram_web("https://t.me/Ch")
    assert len(items) == 2
    assert items[0]["url"].endswith("Ch/101")
    assert "орошение" in items[0]["title"]
    assert " Second" not in items[0]["title"]


def test_rss_parse(monkeypatch):
    import backend.news.collectors as c

    xml = ("<rss><channel>"
           "<item><title>Новость 1</title><description>текст</description><link>http://a</link></item>"
           "<item><title>Новость 2</title></item>"
           "</channel></rss>")
    monkeypatch.setattr(c.urllib.request, "urlopen",
                        lambda *a, **k: types.SimpleNamespace(
                            read=lambda: xml.encode(), __enter__=lambda s: s,
                            __exit__=lambda s, *x: None))
    items = c.collect_rss("http://feed")
    assert len(items) == 2
    assert items[0]["title"] == "Новость 1"
    assert items[1]["url"] is None


# ---------- egrul ----------

def test_egrul_inn_validation():
    from backend.clients.egrul import fetch_requisites_by_inn, EgrulError
    with pytest.raises(EgrulError):
        fetch_requisites_by_inn("12345")
    with pytest.raises(EgrulError):
        fetch_requisites_by_inn("abc")


def test_egrul_parse(monkeypatch):
    import backend.clients.egrul as e

    def fake_post(url, data, headers=None, timeout=None):
        return types.SimpleNamespace(
            read=lambda: json.dumps({"t": "TOKEN", "captchaRequired": False}).encode(),
            __enter__=lambda s: s, __exit__=lambda s, *x: None)

    def fake_get(url, headers=None, timeout=None):
        assert url.endswith("/search-result/TOKEN")
        return types.SimpleNamespace(
            read=lambda: json.dumps({"rows": [{
                "c": "ООО Тест", "n": "ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ «Тест»",
                "i": "7707083893", "o": "1027700132195", "p": "773601001",
                "r": "16.08.2002", "g": "ГЕНЕРАЛЬНЫЙ ДИРЕКТОР: Иванов Иван Иванович",
                "rn": "Г.Москва"}]}).encode(),
            __enter__=lambda s: s, __exit__=lambda s, *x: None)

    monkeypatch.setattr(e.urllib.request, "Request", lambda url, data=None, headers=None: (url, data))
    def fake_urlopen(req, timeout=None):
        url, data = req
        return fake_post(url, data, timeout=timeout) if data else fake_get(url, timeout=timeout)
    monkeypatch.setattr(e.urllib.request, "urlopen", fake_urlopen)

    rec = e.fetch_requisites_by_inn("7707083893")
    assert rec["ogrn"] == "1027700132195"
    assert rec["kpp"] == "773601001"
    assert "Иванов" in rec["ceo"]


# ---------- artifacts render ----------

def test_artifact_render():
    from backend.artifacts.generate import render

    ctx = {"deal": {"name": "Орошение"}, "client": {"name": "КФХ Заря", "inn": "123"}}
    out, missing = render("{{deal.name}} для {{client.name}} ({{client.inn}})", ctx)
    assert out == "Орошение для КФХ Заря (123)"
    assert missing == []
    out2, missing2 = render("{{client.ogrn}}", ctx)
    assert missing2 == ["client.ogrn"]
    assert out2 == "{{client.ogrn}}"


# ---------- news analyze: уровни ----------

def test_mia_analyze_levels():
    import backend.monitoring.producer.mia_monitor as m

    items = m.analyze("/weather", {
        "source": "S", "category": "weather", "parameter": "T",
        "value": -3.0, "unit": "°C", "threshold_warning": 3, "threshold_critical": 0})
    assert items and items[0]["level"] == "critical"

    items = m.analyze("/prices", {
        "source": "S", "category": "price", "parameter": "P",
        "value": -15.0, "unit": "%", "threshold_warning": 8, "threshold_critical": 12})
    assert items and items[0]["level"] == "critical"

    items = m.analyze("/news", {
        "source": "S", "category": "news", "parameter": "N",
        "value": 0, "unit": "шт", "threshold_warning": 5, "threshold_critical": 8})
    assert items and items[0]["level"] == "ok"


# ---------- security: password hashing ----------

def test_bcrypt_roundtrip():
    from backend.auth.security import hash_password, verify_password
    h = hash_password("secret123")
    assert h != "secret123" and h.startswith("$2")
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


# ---------- assistant word-stem matching ----------

def test_assistant_context_import():
    from backend.assistant import routes  # noqa: F401 — синтаксис/импорты живы
