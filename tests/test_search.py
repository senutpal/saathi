"""Web search coverage: every outbound HTTP path mocked, zero real network."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import timedelta

from saathi.blueprints.search import SEARCH_MIN_INTERVAL_SECONDS
from saathi.extensions import db
from saathi.models import ActivityLog, SearchCache, WeatherCache, utcnow
from saathi.services import search as search_service


def _hash(q: str) -> str:
    return hashlib.sha256(q.lower().strip().encode()).hexdigest()


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _Net:
    """Scriptable stand-in for every outbound call site in services/search."""

    def __init__(self):
        self.calls = {"ddgs": 0, "wiki": 0, "geo": 0, "forecast": 0}
        self.ddgs_payload = [
            {"title": "DDG Result", "href": "https://example.com/ddg", "body": "ddg body"}
        ]
        self.ddgs_error = None
        self.wiki_payload = [
            "q",
            ["Wiki Page"],
            ["wiki snippet"],
            ["https://en.wikipedia.org/wiki/Wiki_Page"],
        ]
        self.wiki_error = None
        self.geo_payload = {"results": [{"latitude": 51.5, "longitude": -0.12, "name": "London"}]}
        self.geo_error = None
        self.forecast_payload = {
            "current_weather": {"temperature": 15.4, "windspeed": 12.3, "weathercode": 2}
        }
        self.forecast_error = None


def _install_net(monkeypatch: object, net: _Net) -> None:
    # ddgs.DDGS is a lazy _DDGSProxy whose metaclass swaps the real class in at
    # instantiation, so patching .text on it never sticks — replace the whole
    # symbol at our service seam instead.
    class _FakeDDGS:
        def __init__(self, timeout: int | None = None) -> None:
            self.timeout = timeout

        def text(self, query: str, **_kwargs):
            net.calls["ddgs"] += 1
            if net.ddgs_error is not None:
                raise net.ddgs_error
            return net.ddgs_payload

    def fake_get(url, **_kwargs):
        if "geocoding-api" in url:
            net.calls["geo"] += 1
            if net.geo_error is not None:
                raise net.geo_error
            return _Resp(net.geo_payload)
        if "open-meteo" in url:
            net.calls["forecast"] += 1
            if net.forecast_error is not None:
                raise net.forecast_error
            return _Resp(net.forecast_payload)
        net.calls["wiki"] += 1
        if net.wiki_error is not None:
            raise net.wiki_error
        return _Resp(net.wiki_payload)

    monkeypatch.setattr(search_service, "DDGS", _FakeDDGS)
    monkeypatch.setattr(search_service.requests, "get", fake_get)


def test_anon_search_redirects_to_login(client):
    r = client.get("/search?q=anything")

    assert r.status_code == 302
    assert r.headers["Location"].startswith("/auth/login")


def test_blank_and_whitespace_q_never_reach_the_network(logged_in_client, app, monkeypatch):
    net = _Net()
    _install_net(monkeypatch, net)

    first = logged_in_client.get("/search")
    second = logged_in_client.get("/search?q=%20%20")

    assert first.status_code == 200
    assert second.status_code == 200
    assert net.calls == {"ddgs": 0, "wiki": 0, "geo": 0, "forecast": 0}
    with app.app_context():
        assert SearchCache.query.count() == 0


def test_overlong_q_rejected_with_hint(logged_in_client, app, monkeypatch):
    net = _Net()
    _install_net(monkeypatch, net)

    r = logged_in_client.get("/search?q=" + "x" * 201)

    assert r.status_code == 200
    assert b"under 200 characters" in r.data
    assert net.calls["ddgs"] == 0


def test_ddgs_raises_wikipedia_fallback_serves(logged_in_client, app, monkeypatch):
    net = _Net()
    net.ddgs_error = RuntimeError("202 Ratelimit")
    _install_net(monkeypatch, net)

    r = logged_in_client.get("/search?q=wiki%20time")

    assert r.status_code == 200
    assert b"Wikipedia" in r.data
    assert b"Wiki Page" in r.data
    assert net.calls["wiki"] == 1
    with app.app_context():
        row = db.session.get(SearchCache, _hash("wiki time"))
        assert row is not None
        assert row.source == "wikipedia"
        assert (
            db.session.scalar(
                db.select(db.func.count())
                .select_from(ActivityLog)
                .where(ActivityLog.activity_type == "web_search_wikipedia")
            )
            == 1
        )


def test_second_identical_query_hits_cache(logged_in_client, monkeypatch):
    net = _Net()
    _install_net(monkeypatch, net)

    first = logged_in_client.get("/search?q=cacheme").data
    second = logged_in_client.get("/search?q=cacheme").data

    assert net.calls["ddgs"] == 1
    assert net.calls["wiki"] == 0
    assert b"Cached" in second
    assert b"DDG Result" in first
    assert b"DDG Result" in second


def test_rate_limit_blocks_rapid_second_query(logged_in_client, monkeypatch):
    net = _Net()
    _install_net(monkeypatch, net)

    logged_in_client.get("/search?q=one")
    blocked = logged_in_client.get("/search?q=two")

    assert b"One search every few seconds" in blocked.data
    assert net.calls["ddgs"] == 1

    with logged_in_client.session_transaction() as s:
        s["last_search_ts"] = time.time() - SEARCH_MIN_INTERVAL_SECONDS - 1
    allowed = logged_in_client.get("/search?q=three")

    assert allowed.status_code == 200
    assert net.calls["ddgs"] == 2


def test_script_tag_title_rendered_escaped(logged_in_client, monkeypatch):
    net = _Net()
    net.ddgs_payload = [
        {"title": "<script>alert(1)</script>", "href": "https://example.com/x", "body": "ok"}
    ]
    _install_net(monkeypatch, net)

    html = logged_in_client.get("/search?q=xss").data.decode()

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)" not in html


def test_unsafe_href_dropped_https_sibling_survives(logged_in_client, app, monkeypatch):
    net = _Net()
    net.ddgs_payload = [
        {"title": "evil", "href": "javascript:alert(1)", "body": "b"},
        {"title": "good", "href": "https://example.com/ok", "body": "g"},
    ]
    _install_net(monkeypatch, net)

    html = logged_in_client.get("/search?q=mixed").data.decode()

    assert "javascript:" not in html
    assert "https://example.com/ok" in html
    with app.app_context():
        payload = json.loads(db.session.get(SearchCache, _hash("mixed")).payload_json)
        assert [r["title"] for r in payload] == ["good"]


def test_all_upstreams_down_friendly_error_no_poisoning(logged_in_client, app, monkeypatch):
    net = _Net()
    net.ddgs_error = RuntimeError("down")
    net.wiki_error = ConnectionError("down")
    _install_net(monkeypatch, net)

    r = logged_in_client.get("/search?q=doomed")

    assert r.status_code == 200
    assert b"unavailable right now" in r.data
    assert b"Traceback" not in r.data
    with app.app_context():
        assert SearchCache.query.count() == 0
        assert ActivityLog.query.filter(ActivityLog.activity_type.like("web_search%")).count() == 0


def test_expired_cache_row_refetches_and_refreshes(logged_in_client, app, monkeypatch):
    net = _Net()
    _install_net(monkeypatch, net)
    key = _hash("stale")
    with app.app_context():
        db.session.add(
            SearchCache(
                query_hash=key,
                query_text="stale",
                source="web",
                payload_json=json.dumps(
                    [{"title": "Old", "href": "https://old.example/x", "body": "old"}]
                ),
                fetched_at=utcnow() - timedelta(hours=7),
            )
        )
        db.session.commit()

    logged_in_client.get("/search?q=stale")

    assert net.calls["ddgs"] == 1
    with app.app_context():
        row = db.session.get(SearchCache, key)
        assert utcnow() - row.fetched_at < timedelta(minutes=5)
        assert "DDG Result" in row.payload_json


def test_weather_fail_soft_none_on_geocode_failure(app, monkeypatch):
    net = _Net()
    net.geo_error = ConnectionError("nope")
    _install_net(monkeypatch, net)

    with app.app_context():
        assert search_service.get_weather("Nowhereville") is None
        assert search_service.get_weather("   ") is None


def test_weather_cached_within_ttl_refetched_after(app, monkeypatch):
    net = _Net()
    _install_net(monkeypatch, net)

    with app.app_context():
        first = search_service.get_weather("London")
        second = search_service.get_weather("London")

        assert first == second
        assert net.calls["geo"] == 1
        assert net.calls["forecast"] == 1

        db.session.get(WeatherCache, "london").fetched_at = utcnow() - timedelta(minutes=31)
        db.session.commit()

        third = search_service.get_weather("London")

        assert third == first
        assert net.calls["geo"] == 2
