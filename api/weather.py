"""api/weather.py — Live weather and forecast endpoints."""

from flask import Blueprint, jsonify, request
from services.weather import (
    get_live_weather, get_forecast, geocode_city,
    DEFAULT_LAT, DEFAULT_LON, DEFAULT_CITY,
)
from api.rate_limit import rate_limit
from datetime import datetime
import random

bp = Blueprint("weather", __name__)


CITY_FALLBACKS = {
    "dehradun": {"latitude": 30.3165, "longitude": 78.0322, "city": "Dehradun, Uttarakhand, India", "country": "India", "timezone": "Asia/Kolkata"},
    "bageshwar": {"latitude": 29.8370, "longitude": 79.7710, "city": "Bageshwar, Uttarakhand, India", "country": "India", "timezone": "Asia/Kolkata"},
    "almora": {"latitude": 29.5892, "longitude": 79.6469, "city": "Almora, Uttarakhand, India", "country": "India", "timezone": "Asia/Kolkata"},
    "nainital": {"latitude": 29.3919, "longitude": 79.4542, "city": "Nainital, Uttarakhand, India", "country": "India", "timezone": "Asia/Kolkata"},
    "haldwani": {"latitude": 29.2197, "longitude": 79.5120, "city": "Haldwani, Uttarakhand, India", "country": "India", "timezone": "Asia/Kolkata"},
    "delhi": {"latitude": 28.6139, "longitude": 77.2090, "city": "Delhi, India", "country": "India", "timezone": "Asia/Kolkata"},
}


def _simulate_current_weather(lat: float, lon: float, city: str) -> dict:
    # Deterministic-ish fallback to keep UI functional when weather API is unavailable.
    now = datetime.now()
    day_seed = int(now.strftime("%Y%m%d")) + int(abs(lat) * 1000) + int(abs(lon) * 1000)
    rnd = random.Random(day_seed)
    base_temp = 18 + ((lat - 28) * 0.45)
    temp = round(base_temp + rnd.uniform(-3, 4), 1)
    hum = round(58 + rnd.uniform(-12, 18), 1)
    conditions = [
        ("Clear Sky", "☀️"),
        ("Mainly Clear", "🌤️"),
        ("Partly Cloudy", "⛅"),
        ("Cloudy", "☁️"),
    ]
    cond, icon = conditions[now.hour % len(conditions)]
    return {
        "temperature": temp,
        "humidity": max(20, min(95, hum)),
        "feels_like": round(temp + rnd.uniform(-2, 2), 1),
        "precipitation": round(max(0, rnd.uniform(0, 2.5)), 1),
        "wind_kmh": round(4 + rnd.uniform(0, 16), 1),
        "uv_index": round(max(0, min(10, 2 + rnd.uniform(0, 6))), 1),
        "condition": cond,
        "icon": icon,
        "source": "Simulated (offline)",
        "fetched_at": now.isoformat(),
        "city": city,
    }


@bp.route("/current")
@rate_limit("weather")
def current():
    """GET /api/weather/current?lat=&lon=&city= — live conditions."""
    try:
        lat = float(request.args.get("lat", DEFAULT_LAT))
        lon = float(request.args.get("lon", DEFAULT_LON))
    except (TypeError, ValueError):
        lat, lon = DEFAULT_LAT, DEFAULT_LON
    city = request.args.get("city", DEFAULT_CITY)
    data = get_live_weather(lat, lon)
    if not data:
        data = _simulate_current_weather(lat, lon, city)
    data["city"] = city
    return jsonify(data)


@bp.route("/forecast", methods=["POST"])
@rate_limit("weather")
def forecast():
    """POST /api/weather/forecast — multi-day forecast."""
    d    = request.get_json() or {}
    lat  = float(d.get("lat",  DEFAULT_LAT))
    lon  = float(d.get("lon",  DEFAULT_LON))
    days = int(d.get("days", 7))
    city = d.get("city", DEFAULT_CITY)
    fc   = get_forecast(lat, lon, days)
    if fc:
        return jsonify({"city": city, "lat": lat, "lon": lon,
                        "forecast": fc, "source": "Open-Meteo Live"})
    # fallback
    import random, math
    from datetime import datetime, timedelta
    base = 20 + (lat - 29) * 0.5
    fallback = []
    for day in range(1, min(days + 1, 17)):
        fallback.append({
            "day": day,
            "date": (datetime.now() + timedelta(days=day)).strftime("%b %d"),
            "temp_max": round(base + 5 + random.uniform(-2, 2), 1),
            "temp_min": round(base - 5 + random.uniform(-2, 2), 1),
            "temperature": round(base + random.uniform(-3, 3), 1),
            "humidity": round(60 + random.uniform(-10, 15), 1),
            "rainfall_probability": round(random.uniform(0.05, 0.6), 2),
            "precipitation_mm": round(random.uniform(0, 7), 1),
            "wind_kmh": round(random.uniform(5, 25), 1),
            "uv_index": round(random.uniform(3, 8), 1),
            "condition": random.choice(["Sunny", "Partly Cloudy", "Cloudy", "Light Rain"]),
            "icon": random.choice(["☀️", "⛅", "🌤️", "🌧️"]),
            "source": "simulated",
        })
    return jsonify({"city": city, "lat": lat, "lon": lon,
                    "forecast": fallback, "source": "Simulated (offline)"})


@bp.route("/geocode")
@rate_limit("weather")
def geocode():
    """GET /api/weather/geocode?city= — city name to coordinates."""
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({"error": "Provide ?city=Name"}), 400

    lower = city.lower()
    if lower in CITY_FALLBACKS:
        return jsonify(CITY_FALLBACKS[lower] | {"source": "fallback-map"})

    result = geocode_city(city)
    if not result:
        # Graceful fallback to keep UX intact even when upstream geocoder fails.
        return jsonify({
            "latitude": DEFAULT_LAT,
            "longitude": DEFAULT_LON,
            "city": f"{city} (approx)",
            "country": "",
            "timezone": "Asia/Kolkata",
            "source": "fallback-default",
            "note": "City lookup unavailable, showing default coordinates",
        })
    return jsonify(result)

@bp.route("/geocode_reverse")
def geocode_reverse():
    """
    GET /api/weather/geocode_reverse?lat=&lon=
    Accurate reverse geocoding using BigDataCloud API (free, no key needed).
    Returns city, state, country for given GPS coordinates.
    """
    try:
        lat = float(request.args.get("lat", DEFAULT_LAT))
        lon = float(request.args.get("lon", DEFAULT_LON))
    except ValueError:
        return jsonify({"error": "Invalid lat/lon"}), 400

    import urllib.request as ur
    import json as js

    # ── Method 1: BigDataCloud Reverse Geocoding (free, accurate, no key) ────
    try:
        url = (
            f"https://api.bigdatacloud.net/data/reverse-geocode-client"
            f"?latitude={lat}&longitude={lon}&localityLanguage=en"
        )
        req = ur.Request(url, headers={"User-Agent": "AgriTech/3.0"})
        with ur.urlopen(req, timeout=6) as r:
            data = js.loads(r.read().decode())

        city    = data.get("city") or data.get("locality") or data.get("principalSubdivision", "")
        state   = data.get("principalSubdivision", "")
        country = data.get("countryName", "")

        # Build display name: "City, State, Country"
        parts = [p for p in [city, state, country] if p and p != city or p == city]
        # Deduplicate and clean
        seen, clean = set(), []
        for p in [city, state, country]:
            if p and p not in seen:
                seen.add(p)
                clean.append(p)
        display = ", ".join(clean) if clean else f"{lat:.4f}°N, {lon:.4f}°E"

        return jsonify({
            "city":      display,
            "city_short": city or display.split(",")[0],
            "state":     state,
            "country":   country,
            "latitude":  round(lat, 6),
            "longitude": round(lon, 6),
            "source":    "BigDataCloud",
        })

    except Exception as e1:
        pass  # Fall through to next method

    # ── Method 2: Nominatim OpenStreetMap (free, accurate backup) ────────────
    try:
        url = (
            f"https://nominatim.openstreetmap.org/reverse"
            f"?lat={lat}&lon={lon}&format=json&addressdetails=1"
        )
        req = ur.Request(url, headers={
            "User-Agent": "AgriTech/3.0 (educational project)",
            "Accept-Language": "en",
        })
        with ur.urlopen(req, timeout=6) as r:
            data = js.loads(r.read().decode())

        addr    = data.get("address", {})
        city    = (addr.get("city") or addr.get("town") or
                   addr.get("village") or addr.get("county") or "")
        state   = addr.get("state", "")
        country = addr.get("country", "")

        parts = [p for p in [city, state, country] if p]
        seen, clean = set(), []
        for p in parts:
            if p not in seen:
                seen.add(p)
                clean.append(p)
        display = ", ".join(clean) if clean else f"{lat:.4f}°N, {lon:.4f}°E"

        return jsonify({
            "city":       display,
            "city_short": city or display.split(",")[0],
            "state":      state,
            "country":    country,
            "latitude":   round(lat, 6),
            "longitude":  round(lon, 6),
            "source":     "OpenStreetMap",
        })

    except Exception as e2:
        pass  # Fall through to coordinate fallback

    # ── Final fallback: return raw coordinates ────────────────────────────────
    return jsonify({
        "city":       f"{lat:.4f}°N, {lon:.4f}°E",
        "city_short": f"{lat:.2f}°N",
        "state":      "",
        "country":    "",
        "latitude":   round(lat, 6),
        "longitude":  round(lon, 6),
        "source":     "coordinates",
    })
