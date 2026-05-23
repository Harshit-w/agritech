"""services/sensors.py — Sensor readings with real weather API + simulated/real soil sensors.
Support for hardware connection via Bluetooth/USB. If hardware connected, use real data; else simulate.
"""

import math
import random
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from services.weather import get_live_weather, DEFAULT_CITY, DEFAULT_LAT, DEFAULT_LON

log = logging.getLogger(__name__)

# ── Hardware Connection Status ─────────────────────────────────────────────────
HARDWARE_STATUS_FILE = Path(__file__).parent.parent / ".hardware_status"

def _default_hardware_status() -> dict:
    return {"connected": False, "device": None, "connection_type": None}


def _normalize_hardware_status(status: dict | None) -> dict:
    """Ensure status dict always has the expected keys."""
    s = status or {}
    return {
        "connected": bool(s.get("connected", False)),
        "device": s.get("device"),
        "connection_type": s.get("connection_type"),
    }


def _get_hardware_status() -> dict:
    """Load and validate hardware connection status from file."""
    status = _default_hardware_status()
    try:
        if HARDWARE_STATUS_FILE.exists():
            status = _normalize_hardware_status(json.loads(HARDWARE_STATUS_FILE.read_text()))
    except Exception as e:
        log.warning(f"Could not load hardware status: {e}")

    # Prevent stale "connected" status when device is actually unavailable.
    if status["connected"] and _read_hardware_sensors(status) is None:
        log.warning("Stale hardware connection detected. Marking status as disconnected.")
        return _set_hardware_status(False)

    return status

def _set_hardware_status(connected: bool, device: str = None, connection_type: str = None):
    """Save hardware connection status."""
    status = {"connected": connected, "device": device, "connection_type": connection_type}
    try:
        HARDWARE_STATUS_FILE.write_text(json.dumps(status))
    except Exception as e:
        log.warning(f"Could not save hardware status: {e}")
    return status

def _read_hardware_sensors(hw_status: dict = None) -> dict:
    """
    Read from connected hardware (Bluetooth/USB).
    Stub implementation - would connect to actual hardware here.
    Returns None if hardware not connected or read failed.
    """
    hw_status = _normalize_hardware_status(hw_status) if hw_status is not None else _get_hardware_status()
    if not hw_status["connected"]:
        return None
    
    try:
        # TODO: Implement actual hardware communication
        # For now, return None (hardware not actually connected)
        log.info(f"Hardware connected: {hw_status['device']} via {hw_status['connection_type']}")
        # Placeholder for real hardware reads
        return None
    except Exception as e:
        log.error(f"Hardware read failed: {e}")
        return None


def _probe_hardware(device_name: str, connection_type: str) -> bool:
    """
    Probe for real hardware availability.
    Replace this stub with actual USB/Bluetooth discovery logic.
    """
    log.info(f"Probing hardware: {device_name} via {connection_type}")
    return False


def get_sensor_readings(lat: float = None, lon: float = None) -> dict:
    """
    Get sensor data. Priority:
    1. Temperature & Humidity: ALWAYS from Open-Meteo API (real-time, accurate)
    2. If hardware connected → read real soil data from hardware
    3. Otherwise → use simulated soil data (realistic ranges)
    """
    from services.weather import DEFAULT_LAT, DEFAULT_LON
    use_lat = lat if lat is not None else DEFAULT_LAT
    use_lon = lon if lon is not None else DEFAULT_LON
    w  = get_live_weather(use_lat, use_lon)
    ts = datetime.now()

    # ✅ Temperature and Humidity: ALWAYS from real Open-Meteo API (NO artificial noise)
    if w:
        temperature = round(w["temperature"], 1)  # Real API value, no noise
        humidity    = round(min(100, max(0, w["humidity"])), 1)  # Real API value, no noise
        weather_source = "Open-Meteo API (live)"
    else:
        # Fallback: Use realistic calculated values if API fails (rare)
        # But log this as it should not happen often
        log.warning(f"Weather API failed for {use_lat},{use_lon} - using fallback calculated values")
        h           = ts.hour + ts.minute / 60
        temperature = round(18 + 10 * math.sin((h - 6) * math.pi / 12), 1)
        humidity    = round(65 + 12 * math.cos((h - 14) * math.pi / 12), 1)
        weather_source = "Calculated (API unavailable)"

    # Soil sensors: try hardware first, fall back to simulated
    hw_status = _get_hardware_status()
    hw_data = _read_hardware_sensors() if hw_status["connected"] else None
    soil_source = "hardware" if hw_data else "simulated"

    if hw_data:
        # Use real hardware data
        soil_moisture = hw_data.get("soil_moisture")
        ph_level = hw_data.get("ph_level")
        light_intensity = hw_data.get("light_intensity")
        nitrogen = hw_data.get("nitrogen")
        phosphorus = hw_data.get("phosphorus")
        potassium = hw_data.get("potassium")
    else:
        # Use simulated data (realistic ranges)
        soil_moisture = round(random.uniform(38, 70), 1)
        ph_level = round(random.uniform(5.9, 7.4), 2)
        light_intensity = int(random.uniform(9000, 80000))
        nitrogen = int(random.uniform(42, 112))
        phosphorus = int(random.uniform(14, 56))
        potassium = int(random.uniform(92, 238))

    return {
        "timestamp":       ts.isoformat(),
        "temperature":     temperature,
        "humidity":        humidity,
        "soil_moisture":   soil_moisture,
        "ph_level":        ph_level,
        "light_intensity": light_intensity,
        "nitrogen":        nitrogen,
        "phosphorus":      phosphorus,
        "potassium":       potassium,
        "status":          "online",
        "source":          soil_source,
        "hardware_connected": hw_status["connected"],
        "hardware_device": hw_status["device"],
        "hardware_connection": hw_status["connection_type"],
        "weather_source":  weather_source,
        "location":        DEFAULT_CITY if (lat is None and lon is None) else f"{use_lat:.4f}°N, {use_lon:.4f}°E",
    }



def get_sensor_history(hours: int = 24) -> list:
    """
    Generate realistic 15-minute interval historical data.
    Uses current real weather API data as baseline for temperature/humidity trends.
    """
    now  = datetime.now()
    w    = get_live_weather()  # Get current real weather
    base_temp = w["temperature"] if w else 25.0
    base_humidity = w["humidity"] if w else 60.0
    
    data = []
    for i in range(hours * 4):
        ts = now - timedelta(minutes=15 * i)
        h  = ts.hour + ts.minute / 60
        
        # Temperature: base on real current temp with realistic daily cycle
        temp_cycle = 5 * math.sin((h - 6) * math.pi / 12)
        temperature = round(base_temp - (i * 0.01) + temp_cycle, 1)  # Slight trend over time
        
        # Humidity: inverse relationship with temperature
        humidity_cycle = -8 * math.sin((h - 6) * math.pi / 12)
        humidity = round(min(100, max(20, base_humidity + humidity_cycle + (i * 0.005))), 1)
        
        # Soil data: realistic simulated values (no hardware history available)
        data.append({
            "timestamp":     ts.isoformat(),
            "temperature":   temperature,
            "humidity":      humidity,
            "soil_moisture": round(54 + 12 * math.cos(i * 0.15), 1),
            "ph_level":      round(6.5 + 0.3 * math.sin(i * 0.05), 2),
        })
    return list(reversed(data))


def generate_alerts(sensors: dict) -> list:
    """Generate threshold-based alerts, supplemented by live weather conditions."""
    alerts = []
    w      = get_live_weather()

    # Soil / sensor alerts
    if sensors["soil_moisture"] < 30:
        alerts.append({"type": "danger", "icon": "🔴",
            "title": "Critical: Low Soil Moisture",
            "msg": f"Soil moisture at {sensors['soil_moisture']}% — irrigate immediately."})

    if sensors["temperature"] > 38:
        alerts.append({"type": "danger", "icon": "🔴",
            "title": "Heat Stress Alert",
            "msg": f"Temperature {sensors['temperature']}°C — shade crops urgently."})

    if sensors["ph_level"] < 5.8 or sensors["ph_level"] > 7.5:
        alerts.append({"type": "warn", "icon": "⚠️",
            "title": "pH Out of Range",
            "msg": f"Soil pH at {sensors['ph_level']} — amendment needed."})

    if sensors["humidity"] > 85:
        alerts.append({"type": "warn", "icon": "⚠️",
            "title": "High Humidity",
            "msg": f"Humidity at {sensors['humidity']}% — elevated disease risk."})

    # Live weather alerts
    if w:
        if w.get("precipitation", 0) > 5:
            alerts.append({"type": "info", "icon": "🌧️",
                "title": "Rain Detected (Live)",
                "msg": f"{w['precipitation']}mm precipitation — delay irrigation and field operations."})

        if w.get("wind_kmh", 0) > 40:
            alerts.append({"type": "warn", "icon": "💨",
                "title": "High Wind Alert",
                "msg": f"Wind at {w['wind_kmh']} km/h — protect tall crops, avoid spraying."})

        if w.get("uv_index", 0) >= 8:
            alerts.append({"type": "warn", "icon": "☀️",
                "title": "High UV Index",
                "msg": f"UV Index {w['uv_index']} — protect workers, avoid fieldwork 11am–3pm."})

    # Hardware connection status
    hw_status = _get_hardware_status()
    if hw_status["connected"]:
        alerts.append({"type": "ok", "icon": "🔌",
            "title": f"Hardware Connected: {hw_status['device']}",
            "msg": f"Using real data via {hw_status['connection_type']}"})

    if not alerts:
        cond = f" · {w['icon']} {w['condition']}" if w else ""
        alerts.append({"type": "ok", "icon": "✅",
            "title": "All Systems Normal",
            "msg": f"All readings within optimal ranges{cond}"})

    return alerts


def connect_hardware(device_name: str, connection_type: str = "bluetooth") -> dict:
    """
    Connect to hardware sensor only if a real device is detected.
    This avoids false "connected" state in UI when no sensor is present.
    """
    try:
        log.info(f"Scanning for hardware: {device_name} via {connection_type}...")

        detection_success = _probe_hardware(device_name, connection_type)

        if detection_success:
            status = _set_hardware_status(True, device_name, connection_type)
            log.info(f"✅ Hardware detected: {device_name} via {connection_type}")
            return {"success": True, "status": status, "message": f"Connected to {device_name}"}
        else:
            _set_hardware_status(False)
            log.info(f"❌ No hardware detected on {connection_type}")
            return {"success": False, "error": f"No sensors detected on {connection_type}. Please check connection."}
    except Exception as e:
        log.error(f"Hardware connection scan failed: {e}")
        return {"success": False, "error": f"Scan error: {str(e)}"}


def disconnect_hardware() -> dict:
    """Disconnect from hardware sensor."""
    try:
        status = _set_hardware_status(False)
        log.info("Hardware disconnected - reverting to simulated data")
        return {"success": True, "status": status}
    except Exception as e:
        log.error(f"Hardware disconnection failed: {e}")
        return {"success": False, "error": str(e)}


def get_hardware_status() -> dict:
    """Get current hardware connection status."""
    return _get_hardware_status()
