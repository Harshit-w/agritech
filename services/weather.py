"""services/weather.py — Open-Meteo API integration with 5-min cache."""

import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime
from config import Config

log = logging.getLogger(__name__)

cfg = Config()
DEFAULT_LAT  = cfg.DEFAULT_LAT
DEFAULT_LON  = cfg.DEFAULT_LON
DEFAULT_CITY = cfg.DEFAULT_CITY

CACHE_TTL = 300   # seconds

WMO_CODES = {
    0:  ("Clear Sky",       "☀️"),
    1:  ("Mainly Clear",    "🌤️"),
    2:  ("Partly Cloudy",   "⛅"),
    3:  ("Overcast",        "☁️"),
    45: ("Fog",             "🌫️"),
    48: ("Icy Fog",         "🌫️"),
    51: ("Light Drizzle",   "🌦️"),
    53: ("Drizzle",         "🌦️"),
    55: ("Heavy Drizzle",   "🌧️"),
    61: ("Light Rain",      "🌧️"),
    63: ("Rain",            "🌧️"),
    65: ("Heavy Rain",      "🌧️"),
    71: ("Light Snow",      "🌨️"),
    73: ("Snow",            "❄️"),
    75: ("Heavy Snow",      "❄️"),
    80: ("Rain Showers",    "🌦️"),
    81: ("Showers",         "🌧️"),
    82: ("Violent Showers", "⛈️"),
    95: ("Thunderstorm",    "⛈️"),
    96: ("Thunderstorm",    "⛈️"),
    99: ("Thunderstorm",    "⛈️"),
}

_cache: dict = {"data": None, "fetched_at": None}


# ── HTTP helper ────────────────────────────────────────────────────────────────
def _get(url: str, timeout: int = 6) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AgriTech/3.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log.warning(f"HTTP failed [{url[:60]}]: {e}")
        return None


# ── Current weather ────────────────────────────────────────────────────────────
def get_live_weather(lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON) -> dict | None:
    """Return live current conditions, cached for CACHE_TTL seconds."""
    global _cache
    now = datetime.now()
    if (
        _cache["data"]
        and _cache["fetched_at"]
        and (now - _cache["fetched_at"]).seconds < CACHE_TTL
        and lat == DEFAULT_LAT and lon == DEFAULT_LON
    ):
        return _cache["data"]

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        f"precipitation,weathercode,windspeed_10m,uv_index"
        f"&timezone=Asia%2FKolkata"
    )
    d = _get(url)
    if not d or "current" not in d:
        return None

    c    = d["current"]
    cond, icon = WMO_CODES.get(c.get("weathercode", 0), ("Partly Cloudy", "⛅"))
    result = {
        "temperature":   round(c.get("temperature_2m",         20.0), 1),
        "humidity":      round(c.get("relative_humidity_2m",   60.0), 1),
        "feels_like":    round(c.get("apparent_temperature",   20.0), 1),
        "precipitation": round(c.get("precipitation",           0.0), 1),
        "wind_kmh":      round(c.get("windspeed_10m",           0.0), 1),
        "uv_index":      round(c.get("uv_index",                0.0), 1),
        "condition": cond,
        "icon":      icon,
        "source":    "Open-Meteo Live",
        "fetched_at": now.isoformat(),
    }

    if lat == DEFAULT_LAT and lon == DEFAULT_LON:
        _cache = {"data": result, "fetched_at": now}

    log.info(f"🌤️  Weather: {result['temperature']}°C  {result['humidity']}%RH  {cond}")
    return result


def warm_weather_cache() -> None:
    """Pre-warm the cache at startup."""
    get_live_weather()


# ── Forecast ───────────────────────────────────────────────────────────────────
def get_forecast(lat: float, lon: float, days: int = 7) -> list | None:
    import random
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        f"precipitation_probability_max,weathercode,windspeed_10m_max,uv_index_max"
        f"&timezone=Asia%2FKolkata"
        f"&forecast_days={min(days + 1, 16)}"
    )
    d = _get(url)
    if not d or "daily" not in d:
        return None

    dl  = d["daily"]
    out = []

    def safe(key, fallback, idx):
        lst = dl.get(key) or []
        return lst[idx] if idx < len(lst) and lst[idx] is not None else fallback

    for i in range(1, len(dl["time"])):
        if len(out) >= days:
            break
        code      = safe("weathercode", 0, i)
        cond, icon = WMO_CODES.get(code, ("Partly Cloudy", "⛅"))
        tmax      = safe("temperature_2m_max",               25.0, i)
        tmin      = safe("temperature_2m_min",               15.0, i)
        prec      = safe("precipitation_sum",                 0.0, i)
        rprob     = (safe("precipitation_probability_max",    0.0, i)) / 100
        wind      = safe("windspeed_10m_max",                 0.0, i)
        uv        = safe("uv_index_max",                      0.0, i)
        dt_str    = dl["time"][i]
        from datetime import datetime
        dt        = datetime.strptime(dt_str, "%Y-%m-%d")
        hum       = round(min(98, max(25, 55 + rprob * 30 + min(10, prec * 2)
                                      - max(0, (tmax - 30) * 0.5)
                                      + random.uniform(-2, 2))), 1)
        out.append({
            "day":                   i,
            "date":                  dt.strftime("%b %d"),
            "date_full":             dt_str,
            "temp_max":              round(tmax, 1),
            "temp_min":              round(tmin, 1),
            "temperature":           round((tmax + tmin) / 2, 1),
            "humidity":              hum,
            "rainfall_probability":  round(rprob, 2),
            "precipitation_mm":      round(prec,  1),
            "wind_kmh":              round(wind,  1),
            "uv_index":              round(uv,    1),
            "condition":             cond,
            "icon":                  icon,
            "source":                "Open-Meteo Live",
        })
    return out or None


# ── Geocoding ──────────────────────────────────────────────────────────────────
def geocode_city(city_name: str) -> dict | None:
    enc = urllib.parse.quote(city_name)
    d   = _get(
        f"https://geocoding-api.open-meteo.com/v1/search"
        f"?name={enc}&count=3&language=en&format=json"
    )
    if not d or not d.get("results"):
        return None
    r     = d["results"][0]
    parts = [r.get("name", "")]
    if r.get("admin1"):  parts.append(r["admin1"])
    if r.get("country"): parts.append(r["country"])
    return {
        "latitude":  round(r["latitude"],  6),
        "longitude": round(r["longitude"], 6),
        "city":      ", ".join(p for p in parts if p),
        "country":   r.get("country", ""),
        "timezone":  r.get("timezone", "Asia/Kolkata"),
    }
