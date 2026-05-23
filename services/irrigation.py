"""services/irrigation.py — Irrigation zone state management (in-memory)."""

import logging
from datetime import datetime

from services.sensors import get_sensor_readings
from services.weather import DEFAULT_LAT, DEFAULT_LON, get_forecast

log = logging.getLogger(__name__)

# In-memory state — replace with DB persistence for production
_ZONES: dict = {
    "north": {"id": "north", "name": "North Field",   "icon": "🌾", "active": True,  "duration": 30, "schedule": "06:00", "liters": 245},
    "south": {"id": "south", "name": "South Field",   "icon": "🌿", "active": False, "duration": 20, "schedule": "07:30", "liters": 180},
    "east":  {"id": "east",  "name": "East Orchard",  "icon": "🍎", "active": True,  "duration": 45, "schedule": "05:30", "liters": 320},
    "west":  {"id": "west",  "name": "West Garden",   "icon": "🌻", "active": False, "duration": 15, "schedule": "08:00", "liters": 95},
}


def get_zones() -> dict:
    """Return all irrigation zone configurations as a deep copy to avoid caller-side mutation."""
    import copy
    return copy.deepcopy(_ZONES)


def update_zone(zone_id: str, data: dict) -> dict | None:
    """
    Update a zone's settings. Returns updated zone or None if not found.
    Accepted fields: active (bool), duration (int 5-120), schedule (str HH:MM)
    """
    if zone_id not in _ZONES:
        return None

    zone = _ZONES[zone_id]

    if "active" in data:
        zone["active"] = bool(data["active"])
        log.info(f"Zone '{zone_id}' toggled → {'ON' if zone['active'] else 'OFF'}")

    if "duration" in data:
        zone["duration"] = max(5, min(120, int(data["duration"])))
        log.info(f"Zone '{zone_id}' duration → {zone['duration']} min")

    if "schedule" in data:
        zone["schedule"] = str(data["schedule"])
        log.info(f"Zone '{zone_id}' schedule → {zone['schedule']}")

    return dict(zone)


def _zone_factor(zone_id: str) -> float:
    return {
        "north": 1.00,
        "south": 0.95,
        "east": 1.10,
        "west": 0.90,
    }.get(zone_id, 1.0)


def recommend_irrigation_plan(zone_id: str | None = None, lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON) -> dict:
    """Build a forecast-aware irrigation plan from current conditions."""
    zones = get_zones()
    if zone_id and zone_id not in zones:
        return {"error": f"Zone '{zone_id}' not found"}

    sensors = get_sensor_readings(lat, lon)
    forecast = get_forecast(lat, lon, days=1) or []
    next_day = forecast[0] if forecast else {}

    rain_prob = float(next_day.get("rainfall_probability", 0.0))
    rain_mm = float(next_day.get("precipitation_mm", 0.0))

    results = []
    targets = [zones[zone_id]] if zone_id else [zones[k] for k in zones]

    for zone in targets:
        base = int(zone.get("duration", 20))
        duration = float(base)
        reasons = []

        moisture = float(sensors.get("soil_moisture", 50))
        temperature = float(sensors.get("temperature", 25))
        humidity = float(sensors.get("humidity", 60))

        if moisture < 30:
            duration += 20
            reasons.append("soil moisture critically low")
        elif moisture < 45:
            duration += 10
            reasons.append("soil moisture below ideal")
        elif moisture > 80:
            duration -= 20
            reasons.append("soil moisture already high")
        elif moisture > 65:
            duration -= 10
            reasons.append("soil moisture above target")

        if temperature > 34:
            duration += 10
            reasons.append("high evapotranspiration risk")
        elif temperature > 28:
            duration += 5
            reasons.append("warm weather conditions")
        elif temperature < 15:
            duration -= 5
            reasons.append("cool weather lowers demand")

        if humidity > 85:
            duration -= 5
            reasons.append("high humidity reduces water loss")

        if rain_prob >= 0.6 or rain_mm >= 4.0:
            duration = 0
            reasons.append("rain expected soon")

        duration = max(0, min(120, int(round(duration * _zone_factor(zone["id"])))) )
        action = "skip" if duration == 0 else "run"

        results.append({
            "zone_id": zone["id"],
            "zone_name": zone["name"],
            "recommended_action": action,
            "recommended_duration_min": duration,
            "reasons": reasons or ["conditions near baseline"],
        })

    return {
        "generated_at": datetime.now().isoformat(),
        "location": {"lat": lat, "lon": lon},
        "drivers": {
            "soil_moisture": sensors.get("soil_moisture"),
            "temperature": sensors.get("temperature"),
            "humidity": sensors.get("humidity"),
            "rain_probability": rain_prob,
            "forecast_rain_mm": rain_mm,
        },
        "plan": results,
    }
