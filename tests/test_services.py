"""
tests/test_services.py
Unit tests for services/ layer — weather, sensors, irrigation.
These test business logic independently of the Flask layer.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import math
from unittest.mock import patch
from services.sensors    import get_sensor_readings, get_sensor_history, generate_alerts
from services.irrigation import get_zones, update_zone
from services.weather    import geocode_city, get_live_weather, DEFAULT_LAT, DEFAULT_LON


# ── Sensor Service ─────────────────────────────────────────────────────────────
class TestSensorService:
    def test_returns_all_required_fields(self):
        s = get_sensor_readings()
        required = [
            "timestamp", "temperature", "humidity", "soil_moisture",
            "ph_level", "light_intensity", "nitrogen", "phosphorus",
            "potassium", "status", "source", "location",
        ]
        for field in required:
            assert field in s, f"Missing: {field}"

    def test_temperature_is_numeric(self):
        s = get_sensor_readings()
        assert isinstance(s["temperature"], (int, float))
        assert -20 <= s["temperature"] <= 60

    def test_humidity_in_range(self):
        s = get_sensor_readings()
        assert 0 <= s["humidity"] <= 100

    def test_soil_moisture_in_range(self):
        s = get_sensor_readings()
        assert 0 <= s["soil_moisture"] <= 100

    def test_ph_in_range(self):
        s = get_sensor_readings()
        assert 0 <= s["ph_level"] <= 14

    def test_nitrogen_positive(self):
        s = get_sensor_readings()
        assert s["nitrogen"] > 0

    def test_status_online(self):
        s = get_sensor_readings()
        assert s["status"] == "online"

    def test_source_is_string(self):
        s = get_sensor_readings()
        assert s["source"] in ("live", "simulated")

    def test_location_set(self):
        s = get_sensor_readings()
        assert "Bageshwar" in s["location"]

    def test_history_returns_list(self):
        h = get_sensor_history(6)
        assert isinstance(h, list)
        assert len(h) > 0

    def test_history_24h_length(self):
        h = get_sensor_history(24)
        # 24 hours * 4 readings per hour = 96 data points
        assert len(h) == 96

    def test_history_6h_length(self):
        h = get_sensor_history(6)
        assert len(h) == 24

    def test_history_chronological_order(self):
        h = get_sensor_history(2)
        timestamps = [r["timestamp"] for r in h]
        assert timestamps == sorted(timestamps)

    def test_history_has_required_fields(self):
        h = get_sensor_history(1)
        for r in h:
            for field in ["timestamp", "temperature", "soil_moisture", "humidity", "ph_level"]:
                assert field in r

    def test_history_temperature_in_range(self):
        h = get_sensor_history(6)
        for r in h:
            assert -20 <= r["temperature"] <= 60

    def test_multiple_calls_vary(self):
        # Sensor readings should not be identical (they have randomness)
        readings = [get_sensor_readings()["soil_moisture"] for _ in range(5)]
        assert len(set(readings)) > 1


# ── Alert Service ─────────────────────────────────────────────────────────────
class TestAlertService:
    def _normal_sensors(self):
        return {
            "temperature": 25.0, "humidity": 65.0,
            "soil_moisture": 55.0, "ph_level": 6.5,
        }

    def _critical_sensors(self):
        return {
            "temperature": 42.0, "humidity": 90.0,
            "soil_moisture": 15.0, "ph_level": 4.5,
        }

    def test_normal_gives_ok_alert(self):
        with patch("services.sensors.get_live_weather", return_value=None):
            alerts = generate_alerts(self._normal_sensors())
        assert len(alerts) == 1
        assert alerts[0]["type"] == "ok"

    def test_low_moisture_gives_danger(self):
        s = self._normal_sensors()
        s["soil_moisture"] = 20.0
        with patch("services.sensors.get_live_weather", return_value=None):
            alerts = generate_alerts(s)
        types = [a["type"] for a in alerts]
        assert "danger" in types

    def test_high_temp_gives_danger(self):
        s = self._normal_sensors()
        s["temperature"] = 42.0
        with patch("services.sensors.get_live_weather", return_value=None):
            alerts = generate_alerts(s)
        types = [a["type"] for a in alerts]
        assert "danger" in types

    def test_bad_ph_gives_warn(self):
        s = self._normal_sensors()
        s["ph_level"] = 4.5
        with patch("services.sensors.get_live_weather", return_value=None):
            alerts = generate_alerts(s)
        types = [a["type"] for a in alerts]
        assert "warn" in types

    def test_high_humidity_gives_warn(self):
        s = self._normal_sensors()
        s["humidity"] = 92.0
        with patch("services.sensors.get_live_weather", return_value=None):
            alerts = generate_alerts(s)
        types = [a["type"] for a in alerts]
        assert "warn" in types

    def test_all_critical_gives_multiple_alerts(self):
        with patch("services.sensors.get_live_weather", return_value=None):
            alerts = generate_alerts(self._critical_sensors())
        assert len(alerts) >= 3

    def test_each_alert_has_required_fields(self):
        with patch("services.sensors.get_live_weather", return_value=None):
            alerts = generate_alerts(self._normal_sensors())
        for a in alerts:
            assert "type"  in a
            assert "icon"  in a
            assert "title" in a
            assert "msg"   in a

    def test_live_weather_rain_gives_info_alert(self):
        mock_weather = {
            "precipitation": 8.0, "wind_kmh": 10.0, "uv_index": 3.0,
            "condition": "Heavy Rain", "icon": "🌧️",
        }
        with patch("services.sensors.get_live_weather", return_value=mock_weather):
            alerts = generate_alerts(self._normal_sensors())
        types = [a["type"] for a in alerts]
        assert "info" in types

    def test_live_weather_high_wind_gives_warn(self):
        mock_weather = {
            "precipitation": 0.0, "wind_kmh": 55.0, "uv_index": 3.0,
            "condition": "Windy", "icon": "💨",
        }
        with patch("services.sensors.get_live_weather", return_value=mock_weather):
            alerts = generate_alerts(self._normal_sensors())
        types = [a["type"] for a in alerts]
        assert "warn" in types


# ── Irrigation Service ────────────────────────────────────────────────────────
class TestIrrigationService:
    def test_returns_four_zones(self):
        zones = get_zones()
        assert len(zones) == 4

    def test_zone_ids(self):
        zones = get_zones()
        assert set(zones.keys()) == {"north", "south", "east", "west"}

    def test_each_zone_has_required_fields(self):
        zones = get_zones()
        for zone_id, zone in zones.items():
            for field in ["id", "name", "icon", "active", "duration", "schedule", "liters"]:
                assert field in zone, f"Zone '{zone_id}' missing field: {field}"

    def test_update_active(self):
        result = update_zone("north", {"active": False})
        assert result is not None
        assert result["active"] is False
        # Restore
        update_zone("north", {"active": True})

    def test_update_duration(self):
        result = update_zone("south", {"duration": 60})
        assert result["duration"] == 60

    def test_duration_clamped_max(self):
        result = update_zone("east", {"duration": 999})
        assert result["duration"] == 120

    def test_duration_clamped_min(self):
        result = update_zone("west", {"duration": 1})
        assert result["duration"] == 5

    def test_update_schedule(self):
        result = update_zone("north", {"schedule": "08:30"})
        assert result["schedule"] == "08:30"

    def test_partial_update(self):
        # Only update duration, active should not change
        before = get_zones()["south"]["active"]
        update_zone("south", {"duration": 25})
        after = get_zones()["south"]
        assert after["active"] == before
        assert after["duration"] == 25

    def test_invalid_zone_returns_none(self):
        result = update_zone("nonexistent_zone", {"active": True})
        assert result is None

    def test_update_returns_updated_zone(self):
        result = update_zone("east", {"duration": 50, "active": True})
        assert result["duration"] == 50
        assert result["active"] is True

    def test_get_zones_returns_copy(self):
        """Modifying returned dict should not affect internal state."""
        zones1 = get_zones()
        zones1["north"]["name"] = "MODIFIED"
        zones2 = get_zones()
        assert zones2["north"]["name"] != "MODIFIED"


# ── Weather Service (offline) ─────────────────────────────────────────────────
class TestWeatherService:
    def test_live_weather_returns_none_when_offline(self):
        """In test environment (no internet), should return None gracefully."""
        result = get_live_weather(DEFAULT_LAT, DEFAULT_LON)
        # Either None (no internet) or a valid dict (with internet)
        assert result is None or isinstance(result, dict)

    def test_live_weather_valid_structure_when_available(self):
        result = get_live_weather(DEFAULT_LAT, DEFAULT_LON)
        if result is None:
            pytest.skip("No internet connection — skipping live weather test")
        required = ["temperature", "humidity", "feels_like", "precipitation",
                    "wind_kmh", "uv_index", "condition", "icon", "source"]
        for field in required:
            assert field in result

    def test_geocode_returns_none_when_offline(self):
        result = geocode_city("Dehradun")
        assert result is None or isinstance(result, dict)

    def test_geocode_valid_structure_when_available(self):
        result = geocode_city("Dehradun")
        if result is None:
            pytest.skip("No internet — skipping geocode test")
        assert "latitude"  in result
        assert "longitude" in result
        assert "city"      in result
        assert -90 <= result["latitude"] <= 90
        assert -180 <= result["longitude"] <= 180
