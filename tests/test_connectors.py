# tests/test_connectors.py -- О2 (§39): реестр коннекторов, парсеры, PKCE


class _StubSource:
    """Мини-двойник Source: type/url/connector/keywords/status/active/id."""

    def __init__(self, id=1, type="rss", url="https://example.com/feed.xml",
                 connector=None, keywords=None, status="active", active=True):
        self.id = id
        self.type = type
        self.url = url
        self.connector = connector
        self.keywords = keywords or []
        self.status = status
        self.active = active


# ---------- реестр и правило active-only (§39.2) ----------

def test_registry_resolution_explicit_key_wins():
    from backend.connectors.registry import resolve_connector
    src = _StubSource(type="news", url="https://arxiv.org", connector="arxiv")
    assert resolve_connector(src).key == "arxiv"


def test_registry_resolution_by_type_and_url():
    from backend.connectors.registry import resolve_connector
    assert resolve_connector(_StubSource(type="rss")).key == "rss"
    assert resolve_connector(_StubSource(type="telegram", url="https://t.me/s/foo")).key == "telegram-web"
    # эвристика домена: t.me в url побеждает даже с другим типом (паритет collect())
    assert resolve_connector(_StubSource(type="news", url="https://t.me/foo")).key == "telegram-web"
    # всё остальное -- site (паритет collect())
    assert resolve_connector(_StubSource(type="news", url="https://vst.ru")).key == "site"
    assert resolve_connector(_StubSource(type="supplier", url="https://vst.ru")).key == "site"


def test_registry_unknown_connector_raises():
    from backend.connectors.registry import resolve_connector
    try:
        resolve_connector(_StubSource(connector="nope"))
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_eligible_only_active_sources():
    from backend.connectors.registry import is_eligible
    assert is_eligible(_StubSource(status="active", active=True))
    # proposed не поставляет данные (DoD О2-2)
    assert not is_eligible(_StubSource(status="proposed", active=True))
    assert not is_eligible(_StubSource(status="disabled", active=True))
    assert not is_eligible(_StubSource(status="rejected", active=True))
    assert not is_eligible(_StubSource(status="active", active=False))


def test_normalize_carries_source_id():
    from backend.connectors.rss import RssConnector
    obs = RssConnector().normalize(
        {"title": "Заголовок", "summary": "текст", "url": "https://x/1"}, _StubSource(id=42))
    assert obs["source_id"] == 42 and obs["connector"] == "rss"
    assert obs["title"] == "Заголовок" and obs["url"] == "https://x/1"


# ---------- arXiv ----------

_ARXIV_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>ArXiv Query</title>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <updated>2026-09-20T00:00:00Z</updated>
    <published>2026-09-19T00:00:00Z</published>
    <title> NDVI recovery
      after drought </title>
    <summary> We study vegetation recovery. </summary>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <published>2026-09-18T00:00:00Z</published>
    <title></title>
    <summary>пустой титул -- пропуск</summary>
  </entry>
</feed>"""


def test_arxiv_parse():
    from backend.connectors.arxiv import build_query_url, parse_arxiv_atom
    items = parse_arxiv_atom(_ARXIV_FIXTURE)
    assert len(items) == 1
    assert items[0]["title"] == "NDVI recovery after drought"  # нормализация пробелов
    assert items[0]["url"] == "http://arxiv.org/abs/2401.00001v1"
    assert items[0]["published_at"] == "2026-09-19T00:00:00Z"
    url = build_query_url(["ndvi", "drought"], max_results=5)
    assert "search_query=" in url and "max_results=5" in url
    assert "ndvi" in url and "drought" in url


# ---------- КиберЛенинка ----------

_CYBER_FIXTURE = """
<div class="results">
  <h2><a href="/article/n/abc-123"> Влияние засухи  на урожай </a></h2>
  <a href="/article/n/def-456"><span>Второе исследование</span></a>
  <a href="/article/n/abc-123">дубль ссылки -- будет дедуп</a>
  <a href="/about">не статья</a>
</div>
"""


def test_cyberleninka_parse():
    from backend.connectors.cyberleninka import parse_cyberleninka_html
    items = parse_cyberleninka_html(_CYBER_FIXTURE)
    assert len(items) == 2  # дубль по href отброшен, /about не статья
    assert items[0]["title"] == "Влияние засухи на урожай"
    assert items[0]["url"] == "https://cyberleninka.ru/article/n/abc-123"
    assert items[1]["url"].endswith("/def-456")


def test_cyberleninka_empty_html_is_valid_outcome():
    from backend.connectors.cyberleninka import parse_cyberleninka_html
    assert parse_cyberleninka_html("<html>ничего</html>") == []


# ---------- PKCE S256 (§39.3) ----------

def test_pkce_rfc7636_vector():
    # Приложение B RFC 7636: известная пара verifier -> challenge
    from backend.connectors.oauth import make_code_challenge
    v = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert make_code_challenge(v) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_pkce_verifier_bounds():
    from backend.connectors.oauth import make_code_verifier
    ok = make_code_verifier(64)
    assert 43 <= len(ok) <= 128
    try:
        make_code_verifier(10)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_redirect_uri_whitelist_exact_match():
    from backend.connectors.oauth import check_redirect_uri
    allowed = ["https://erp.example.com/oauth/callback"]
    assert check_redirect_uri("https://erp.example.com/oauth/callback", allowed)
    # Точное совпадение: поддомен/путь-вариация/пусто -- запрещены
    assert not check_redirect_uri("https://evil.com/oauth/callback", allowed)
    assert not check_redirect_uri("https://erp.example.com/oauth/callback/x", allowed)
    assert not check_redirect_uri("", allowed)
    assert not check_redirect_uri("https://erp.example.com/oauth/callback", [])
