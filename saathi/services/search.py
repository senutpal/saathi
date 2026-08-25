"""Keyless web search via ddgs metasearch, Wikipedia fallback, and an
Open-Meteo weather hook — all outbound HTTP proxied server-side (B10).

Every network path has a hard timeout; every result path degrades:
ddgs → Wikipedia opensearch → friendly error. Successful payloads are
cached in SQLite; errors are never cached.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlparse

import requests
from ddgs import DDGS
from sqlalchemy import delete as sa_delete

from ..extensions import db
from ..models import SearchCache, WeatherCache, utcnow
from ..utils import log_action

HTTP_TIMEOUT = (3.05, 7)
UA = {"User-Agent": "Saathi/1.0 (student project; keyless; contact via repo)"}
CACHE_TTL_SEARCH = timedelta(hours=6)
CACHE_TTL_WEATHER = timedelta(minutes=30)
PRUNE_AFTER = timedelta(days=7)
WIKI_OPENSEARCH = "https://en.wikipedia.org/w/api.php?action=opensearch&format=json&limit=5&search="
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Drizzle",
    53: "Drizzle",
    55: "Drizzle",
    61: "Rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Showers",
    81: "Showers",
    82: "Violent showers",
    85: "Snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm",
    99: "Thunderstorm",
}

_CACHE_KEY_FIELD = {SearchCache: "query_hash", WeatherCache: "city_key"}

_CacheModel = SearchCache | WeatherCache


def _cache_get(
    model: type[_CacheModel], key: str, ttl: timedelta
) -> tuple[object, datetime] | None:
    """Return (payload, fetched_at) while fresh, else None (stale rows linger
    until the next successful fetch overwrites them — re-reads stay cheap)."""
    row = db.session.get(model, key)
    if row is None or utcnow() - row.fetched_at >= ttl:
        return None
    return json.loads(row.payload_json), row.fetched_at


def _cache_put(
    model: type[_CacheModel],
    key: str,
    payload: object,
    *,
    source: str = "",
    query_text: str = "",
    user_id: int | None = None,
    action: str = "",
) -> None:
    """Upsert the payload and prune ancient rows in ONE transaction, so the
    audit row written alongside shares its fate (ADR-018 same-tx rule)."""
    fields: dict[str, object] = {_CACHE_KEY_FIELD[model]: key}
    if query_text:
        fields["query_text"] = query_text[:200]
    if source:
        fields["source"] = source
    fields["payload_json"] = json.dumps(payload, separators=(",", ":"))
    fields["fetched_at"] = utcnow()
    db.session.merge(model(**fields))
    db.session.execute(sa_delete(model.__table__).where(model.fetched_at < utcnow() - PRUNE_AFTER))
    if action and user_id is not None:
        log_action(user_id, action, title=(query_text or key)[:120])
    db.session.commit()


def _safe_href(href: object) -> str | None:
    """Scheme allowlist — javascript:/data:/vbscript: hrefs are XSS vectors,
    so bad URLs are dropped at ingestion rather than escaped at render time."""
    try:
        scheme = urlparse(str(href)).scheme
    except ValueError:
        return None
    return str(href) if scheme in ("http", "https") else None


def _clean_results(raw: list[dict]) -> list[dict]:
    return [r for r in raw if _safe_href(r.get("href"))]


def _wiki_fallback(q: str) -> list[dict]:
    """Wikipedia OpenSearch — rejects bare library User-Agents, hence UA."""
    r = requests.get(WIKI_OPENSEARCH + quote_plus(q), headers=UA, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    _, titles, snippets, urls = r.json()
    return [
        {"title": t, "href": u, "body": s} for t, s, u in zip(titles, snippets, urls, strict=False)
    ]


def lookup_cached(q: str) -> dict | None:
    """Fresh-cache probe used by the route so repeats bypass the throttle
    entirely (the limiter guards upstreams, not SQLite reads)."""
    key = hashlib.sha256(q.lower().strip().encode()).hexdigest()
    hit = _cache_get(SearchCache, key, CACHE_TTL_SEARCH)
    if hit is None:
        return None
    payload, fetched_at = hit
    return {"results": payload, "source": "cached", "error": False, "fetched_at": fetched_at}


def search_web(q: str, user_id: int | None = None) -> dict:
    """Search the web for q; never raises.

    Returns {"results", "source", "error", "fetched_at"} where source is one
    of web / wikipedia / cached / error. The error terminal state writes no
    cache row so a transient outage can't poison the hash for the TTL window.
    """
    key = hashlib.sha256(q.lower().strip().encode()).hexdigest()
    hit = _cache_get(SearchCache, key, CACHE_TTL_SEARCH)
    if hit is not None:
        payload, fetched_at = hit
        return {"results": payload, "source": "cached", "error": False, "fetched_at": fetched_at}

    try:
        raw = DDGS(timeout=8).text(q, max_results=8)
        results = _clean_results(raw)
        if not results:
            raise RuntimeError("ddgs returned nothing usable")
        source = "web"
    except Exception:
        try:
            results = _clean_results(_wiki_fallback(q))
            if not results:
                raise RuntimeError("wikipedia returned nothing usable") from None
            source = "wikipedia"
        except Exception:
            return {"results": [], "source": "error", "error": True, "fetched_at": None}

    fetched_at = utcnow()
    _cache_put(
        SearchCache,
        key,
        results,
        source=source,
        query_text=q,
        user_id=user_id,
        action=f"web_search_{source}",
    )
    return {"results": results, "source": source, "error": False, "fetched_at": fetched_at}


def get_weather(city: str) -> dict | None:
    """Current weather for city; fail-soft contract — ANY failure returns None
    so a future dashboard card renders nothing instead of breaking the page."""
    key = city.strip().lower()
    if not key:
        return None
    hit = _cache_get(WeatherCache, key, CACHE_TTL_WEATHER)
    if hit is not None:
        payload, _fetched_at = hit
        return payload
    try:
        geo = requests.get(
            GEOCODE_URL,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            headers=UA,
            timeout=HTTP_TIMEOUT,
        )
        loc = geo.json()["results"][0]
        forecast = requests.get(
            FORECAST_URL,
            params={
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "current_weather": True,
            },
            headers=UA,
            timeout=HTTP_TIMEOUT,
        )
        cur = forecast.json()["current_weather"]
        out = {
            "city": loc.get("name", city.title()),
            "temp_c": round(cur["temperature"]),
            "wind_kmh": round(cur["windspeed"]),
            "desc": WMO_CODES.get(int(cur["weathercode"]), "—"),
        }
    except Exception:
        return None
    _cache_put(WeatherCache, key, out)
    return out
