"""tests/test_all.py — Full test suite for AgriTech v3."""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


# ── SYSTEM ────────────────────────────────────────────────────────────────────
class TestSystem:
    def test_index(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert b"AgriTech" in r.data

    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.get_json()["status"] == "healthy"

    def test_status(self, client):
        r = client.get("/api/status")
        d = r.get_json()
        assert r.status_code == 200
        assert d["sensors_online"] == 8
        assert d["irrigation_zones"] == 4

    def test_404(self, client):
        r = client.get("/api/nonexistent")
        assert r.status_code == 404

    def test_no_cache_header(self, client):
        r = client.get("/")
        assert "no-store" in r.headers.get("Cache-Control", "")

    def test_cors_header(self, client):
        r = client.get("/api/health")
        assert r.headers.get("Access-Control-Allow-Origin") == "*"


# ── SENSORS ───────────────────────────────────────────────────────────────────
class TestSensors:
    def test_sensors_200(self, client):
        r = client.get("/api/sensors")
        assert r.status_code == 200

    def test_sensors_all_fields(self, client):
        d = client.get("/api/sensors").get_json()
        for f in ["temperature", "humidity", "soil_moisture", "ph_level",
                  "light_intensity", "nitrogen", "phosphorus", "potassium", "status", "source"]:
            assert f in d, f"Missing field: {f}"

    def test_sensors_value_ranges(self, client):
        d = client.get("/api/sensors").get_json()
        assert -10 <= d["temperature"] <= 60
        assert 0   <= d["humidity"]    <= 100
        assert 0   <= d["soil_moisture"] <= 100
        assert 0   <= d["ph_level"]    <= 14

    def test_history_default(self, client):
        d = client.get("/api/sensors/history").get_json()
        assert "data" in d
        assert len(d["data"]) > 0
        assert d["hours"] == 24

    def test_history_custom_hours(self, client):
        d = client.get("/api/sensors/history?hours=6").get_json()
        assert d["hours"] == 6

    def test_history_clamp(self, client):
        d = client.get("/api/sensors/history?hours=9999").get_json()
        assert d["hours"] == 168

    def test_alerts_structure(self, client):
        d = client.get("/api/alerts").get_json()
        assert "alerts" in d
        assert "count"  in d
        assert d["count"] == len(d["alerts"])
        for a in d["alerts"]:
            assert "type"  in a
            assert "title" in a
            assert "msg"   in a

    def test_alerts_valid_types(self, client):
        d = client.get("/api/alerts").get_json()
        valid = {"ok", "warn", "danger", "info"}
        for a in d["alerts"]:
            assert a["type"] in valid


# ── WEATHER ───────────────────────────────────────────────────────────────────
class TestWeather:
    def test_forecast_returns_days(self, client):
        r = client.post("/api/weather/forecast",
            data=json.dumps({"lat": 29.5, "lon": 79.5, "days": 7, "city": "Bageshwar"}),
            content_type="application/json")
        assert r.status_code == 200
        d = r.get_json()
        assert "forecast" in d
        assert len(d["forecast"]) == 7

    def test_forecast_day_structure(self, client):
        r = client.post("/api/weather/forecast",
            data=json.dumps({"lat": 29.5, "lon": 79.5, "days": 3}),
            content_type="application/json")
        fc = r.get_json()["forecast"]
        for day in fc:
            for f in ["date", "temp_max", "temp_min", "humidity", "rainfall_probability", "condition", "icon"]:
                assert f in day, f"Missing field in forecast day: {f}"

    def test_forecast_max_days(self, client):
        r = client.post("/api/weather/forecast",
            data=json.dumps({"lat": 0, "lon": 0, "days": 16}),
            content_type="application/json")
        assert r.status_code == 200

    def test_geocode_not_found(self, client):
        r = client.get("/api/weather/geocode?city=XYZNONEXISTENTCITY99999")
        assert r.status_code in (200, 404, 503)

    def test_geocode_no_city(self, client):
        r = client.get("/api/weather/geocode")
        assert r.status_code == 400


# ── ML PREDICTIONS ────────────────────────────────────────────────────────────
class TestCropPredict:
    PAYLOAD = {
        "temperature": 22, "humidity": 65, "soil_moisture": 55,
        "ph_level": 6.5, "nitrogen": 70, "phosphorus": 35, "potassium": 150,
    }

    def test_crop_200(self, client):
        r = client.post("/api/predict/crop", data=json.dumps(self.PAYLOAD), content_type="application/json")
        assert r.status_code == 200

    def test_crop_fields(self, client):
        d = client.post("/api/predict/crop", data=json.dumps(self.PAYLOAD), content_type="application/json").get_json()
        assert "crop" in d
        assert "confidence" in d
        assert "top5" in d
        assert len(d["top5"]) == 5

    def test_crop_valid_crop_name(self, client):
        d = client.post("/api/predict/crop", data=json.dumps(self.PAYLOAD), content_type="application/json").get_json()
        valid = {"Rice", "Wheat", "Maize", "Tomato", "Potato", "Cotton", "Sugarcane"}
        assert d["crop"] in valid

    def test_crop_confidence_range(self, client):
        d = client.post("/api/predict/crop", data=json.dumps(self.PAYLOAD), content_type="application/json").get_json()
        assert 0 <= d["confidence"] <= 100

    def test_crop_empty_body(self, client):
        r = client.post("/api/predict/crop", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200   # uses defaults


class TestDiseasePredict:
    def test_disease_200(self, client):
        r = client.post("/api/predict/disease", data=json.dumps({"crop": "Tomato"}), content_type="application/json")
        assert r.status_code == 200

    def test_disease_fields(self, client):
        d = client.post("/api/predict/disease", data=json.dumps({"crop": "Wheat"}), content_type="application/json").get_json()
        for f in ["disease", "healthy", "confidence", "probs", "severity", "treatment"]:
            assert f in d

    def test_disease_healthy_flag(self, client):
        for _ in range(20):
            d = client.post("/api/predict/disease", data=json.dumps({"crop": "Rice"}), content_type="application/json").get_json()
            assert d["healthy"] == (d["disease"] == "Healthy")

    def test_disease_all_crops(self, client):
        for crop in ["Rice", "Wheat", "Tomato", "Potato", "Maize", "Cotton", "Sugarcane"]:
            r = client.post("/api/predict/disease", data=json.dumps({"crop": crop}), content_type="application/json")
            assert r.status_code == 200


class TestSoilPredict:
    PAYLOAD = {"nitrogen": 70, "phosphorus": 35, "potassium": 150, "ph_level": 6.5, "organic_matter": 2.5}

    def test_soil_200(self, client):
        r = client.post("/api/predict/soil", data=json.dumps(self.PAYLOAD), content_type="application/json")
        assert r.status_code == 200

    def test_soil_score_range(self, client):
        d = client.post("/api/predict/soil", data=json.dumps(self.PAYLOAD), content_type="application/json").get_json()
        assert 0 <= d["score"] <= 100

    def test_soil_status_values(self, client):
        d = client.post("/api/predict/soil", data=json.dumps(self.PAYLOAD), content_type="application/json").get_json()
        assert d["status"] in ("Good", "Fair", "Poor")

    def test_soil_good_score(self, client):
        d = client.post("/api/predict/soil",
            data=json.dumps({"nitrogen": 90, "phosphorus": 45, "potassium": 200, "ph_level": 6.5, "organic_matter": 4.0}),
            content_type="application/json").get_json()
        assert d["status"] == "Good"

    def test_soil_poor_score(self, client):
        d = client.post("/api/predict/soil",
            data=json.dumps({"nitrogen": 5, "phosphorus": 3, "potassium": 15, "ph_level": 4.5, "organic_matter": 0.3}),
            content_type="application/json").get_json()
        assert d["status"] == "Poor"

    def test_soil_recs_present(self, client):
        d = client.post("/api/predict/soil", data=json.dumps(self.PAYLOAD), content_type="application/json").get_json()
        assert len(d["recs"]) >= 1


class TestIntentPredict:
    def test_intent_irrigation(self, client):
        d = client.post("/api/predict/intent",
            data=json.dumps({"text": "Start irrigation in the north field zone"}),
            content_type="application/json").get_json()
        assert d["intent"] == "irrigation"

    def test_intent_disease(self, client):
        d = client.post("/api/predict/intent",
            data=json.dumps({"text": "Check disease on my wheat leaves, there are spots"}),
            content_type="application/json").get_json()
        assert d["intent"] == "disease"

    def test_intent_weather(self, client):
        d = client.post("/api/predict/intent",
            data=json.dumps({"text": "What is the weather forecast for tomorrow?"}),
            content_type="application/json").get_json()
        assert d["intent"] == "weather"

    def test_intent_soil(self, client):
        d = client.post("/api/predict/intent",
            data=json.dumps({"text": "Check soil pH and nitrogen levels please"}),
            content_type="application/json").get_json()
        assert d["intent"] == "soil"

    def test_intent_short_text(self, client):
        r = client.post("/api/predict/intent",
            data=json.dumps({"text": "hi"}),
            content_type="application/json")
        assert r.status_code == 400

    def test_intent_confidence_range(self, client):
        d = client.post("/api/predict/intent",
            data=json.dumps({"text": "irrigate the field now"}),
            content_type="application/json").get_json()
        assert 0 <= d["confidence"] <= 1


# ── IRRIGATION ────────────────────────────────────────────────────────────────
class TestIrrigation:
    def test_zones_200(self, client):
        r = client.get("/api/irrigation")
        assert r.status_code == 200

    def test_zones_count(self, client):
        d = client.get("/api/irrigation").get_json()
        assert len(d) == 4

    def test_zone_update_active(self, client):
        r = client.post("/api/irrigation/north",
            data=json.dumps({"active": True, "duration": 45}),
            content_type="application/json")
        assert r.status_code == 200
        d = r.get_json()
        assert d["active"] is True
        assert d["duration"] == 45

    def test_zone_duration_clamp(self, client):
        r = client.post("/api/irrigation/south",
            data=json.dumps({"duration": 9999}),
            content_type="application/json")
        assert r.get_json()["duration"] == 120

    def test_zone_not_found(self, client):
        r = client.post("/api/irrigation/unknown_zone",
            data=json.dumps({"active": True}),
            content_type="application/json")
        assert r.status_code == 404
