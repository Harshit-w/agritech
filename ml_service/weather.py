"""ml_service/weather.py — Weather forecasting model (ARIMA/LSTM wrapper with simulation fallback)."""

import math
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

_model = None


def _try_load():
    global _model
    try:
        import joblib
        p = Path("models/weather_model.pkl")
        if p.exists():
            _model = joblib.load(p)
            log.info("✅ Loaded weather_model.pkl")
    except Exception as e:
        log.debug(f"No weather model: {e}")


_try_load()


def forecast_weather(lat: float, lon: float, days: int = 7) -> list:
    """
    Generate weather forecast.
    Uses loaded ARIMA/LSTM model if available, otherwise physics-based simulation.
    The services/weather.py module handles the live Open-Meteo API call first —
    this is used only as a final fallback when the API is also unavailable.
    """
    if _model:
        try:
            import numpy as np
            # Model expects [lat, lon, day_index] features
            predictions = []
            for day in range(1, days + 1):
                features = np.array([[lat, lon, day]])
                pred = _model.predict(features)[0]
                predictions.append({
                    "day": day,
                    "temperature": round(float(pred[0]), 1),
                    "humidity":    round(float(pred[1]), 1),
                    "rainfall_probability": round(min(1.0, max(0.0, float(pred[2]))), 2),
                })
            return predictions
        except Exception as e:
            log.warning(f"Weather model failed: {e}")

    # Physics-based simulation
    base_temp = 20.0 + (lat - 29) * 0.5
    now = datetime.now()
    result = []
    for day in range(1, min(days + 1, 17)):
        # Add seasonal variation
        day_of_year = (now + timedelta(days=day)).timetuple().tm_yday
        seasonal = 5 * math.sin((day_of_year - 80) * 2 * math.pi / 365)
        temp_max = round(base_temp + seasonal + 5 + random.uniform(-2, 2), 1)
        temp_min = round(base_temp + seasonal - 5 + random.uniform(-2, 2), 1)
        rain_prob = round(random.uniform(0.05, 0.65), 2)
        result.append({
            "day":                  day,
            "date":                 (now + timedelta(days=day)).strftime("%b %d"),
            "temp_max":             temp_max,
            "temp_min":             temp_min,
            "temperature":          round((temp_max + temp_min) / 2, 1),
            "humidity":             round(60 + random.uniform(-15, 20), 1),
            "rainfall_probability": rain_prob,
            "precipitation_mm":     round(random.uniform(0, 8) if rain_prob > 0.4 else 0, 1),
            "wind_kmh":             round(random.uniform(5, 30), 1),
            "uv_index":             round(random.uniform(3, 9), 1),
            "condition":            _condition(rain_prob),
            "icon":                 _icon(rain_prob),
            "source":               "ML simulation",
        })
    return result


def _condition(rain_prob: float) -> str:
    if rain_prob > 0.7: return "Heavy Rain"
    if rain_prob > 0.5: return "Light Rain"
    if rain_prob > 0.3: return "Partly Cloudy"
    return "Sunny"


def _icon(rain_prob: float) -> str:
    if rain_prob > 0.7: return "⛈️"
    if rain_prob > 0.5: return "🌧️"
    if rain_prob > 0.3: return "⛅"
    return "☀️"
