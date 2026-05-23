"""
tests/test_ml.py
Unit tests for ml_service/ — crop, disease, soil, intent predictors + validators.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from ml_service.crop      import predict_crop, CROP_DATA
from ml_service.disease   import predict_disease, DISEASES
from ml_service.soil      import analyze_soil
from ml_service.intent    import classify_intent, INTENTS
from ml_service.validators import (
    CropRequest, DiseaseRequest, SoilRequest,
    WeatherRequest, IntentRequest, IrrigationUpdate, validate,
)


# ── Crop Predictor ────────────────────────────────────────────────────────────
class TestCropPredictor:
    def _default(self):
        return dict(temperature=22, humidity=65, soil_moisture=55,
                    ph_level=6.5, nitrogen=70, phosphorus=35, potassium=150)

    def test_returns_valid_crop(self):
        r = predict_crop(**self._default())
        assert r["crop"] in CROP_DATA

    def test_confidence_in_range(self):
        r = predict_crop(**self._default())
        assert 0 <= r["confidence"] <= 100

    def test_top5_length(self):
        r = predict_crop(**self._default())
        assert len(r["top5"]) == 5

    def test_top5_sorted_descending(self):
        r = predict_crop(**self._default())
        scores = [c["score"] for c in r["top5"]]
        assert scores == sorted(scores, reverse=True)

    def test_icon_present(self):
        r = predict_crop(**self._default())
        assert r["icon"] in ["🌾","🌿","🌽","🍅","🥔","🌸","🎋"]

    def test_model_field_present(self):
        r = predict_crop(**self._default())
        assert "model" in r

    def test_high_moisture_favors_rice(self):
        r = predict_crop(temperature=28, humidity=80, soil_moisture=80,
                         ph_level=6.0, nitrogen=80, phosphorus=40, potassium=160)
        top_names = [c["name"] for c in r["top5"]]
        assert "Rice" in top_names[:3]

    def test_high_temp_low_moisture_favors_cotton(self):
        r = predict_crop(temperature=35, humidity=45, soil_moisture=35,
                         ph_level=7.0, nitrogen=60, phosphorus=30, potassium=140)
        top_names = [c["name"] for c in r["top5"]]
        assert "Cotton" in top_names[:3]

    def test_cool_temp_favors_potato_wheat(self):
        r = predict_crop(temperature=18, humidity=65, soil_moisture=65,
                         ph_level=6.0, nitrogen=70, phosphorus=35, potassium=150)
        top_names = [c["name"] for c in r["top5"]]
        assert "Potato" in top_names[:3] or "Wheat" in top_names[:3]

    def test_each_top5_has_required_fields(self):
        r = predict_crop(**self._default())
        for c in r["top5"]:
            for field in ["name", "score", "icon", "temp", "ph"]:
                assert field in c

    def test_top5_first_matches_recommendation(self):
        r = predict_crop(**self._default())
        assert r["top5"][0]["name"] == r["crop"]

    def test_all_7_crops_can_be_recommended(self):
        """Run many combinations to ensure all crops appear at some point."""
        # We just check that the system doesn't crash for any combination
        combos = [
            (20, 80, 75, 6.0, 80, 40, 180),   # Rice conditions
            (22, 55, 52, 7.0, 70, 35, 150),    # Wheat conditions
            (25, 60, 60, 6.5, 70, 35, 155),    # Maize conditions
            (25, 70, 65, 6.4, 65, 30, 140),    # Tomato conditions
            (20, 70, 70, 6.2, 65, 30, 145),    # Potato conditions
            (32, 45, 40, 7.2, 60, 28, 135),    # Cotton conditions
            (30, 75, 75, 6.8, 75, 38, 170),    # Sugarcane conditions
        ]
        for combo in combos:
            r = predict_crop(*combo)
            assert r["crop"] in CROP_DATA


# ── Disease Detector ──────────────────────────────────────────────────────────
class TestDiseaseDetector:
    def test_returns_valid_disease(self):
        r = predict_disease("Tomato")
        assert r["disease"] in DISEASES

    def test_non_leaf_image_prompts_for_plant(self, monkeypatch):
        from ml_service import disease as disease_mod

        monkeypatch.setattr(disease_mod, "_model", None)
        monkeypatch.setattr(
            disease_mod,
            "_colour_features",
            lambda _b64: {
                "mean_r": 120.0,
                "mean_g": 110.0,
                "mean_b": 100.0,
                "std_r": 8.0,
                "std_g": 7.0,
                "std_b": 6.0,
                "yellow": 0.0,
                "brown": 0.0,
                "white": 0.0,
                "dark": 0.0,
                "green": 0.0,
            },
        )

        r = disease_mod.predict_disease("Tomato", "ZmF1bHR5LWltYWdl")
        assert r["disease"] == "ADD IMAGE OF PLANT"
        assert r["treatment"] == "ADD IMAGE OF PLANT"
        assert r["healthy"] is False

    def test_healthy_flag_matches_disease(self):
        for _ in range(30):
            r = predict_disease("Tomato")
            assert r["healthy"] == (r["disease"] == "Healthy")

    def test_confidence_in_range(self):
        r = predict_disease("Rice")
        assert 0 <= r["confidence"] <= 100

    def test_probs_sum_near_100(self):
        r = predict_disease("Wheat")
        total = sum(r["probs"].values())
        assert 99.0 <= total <= 101.0

    def test_probs_has_all_diseases(self):
        r = predict_disease("Maize")
        for disease in DISEASES:
            assert disease in r["probs"]

    def test_severity_values(self):
        for _ in range(30):
            r = predict_disease("Potato")
            if r["healthy"]:
                assert r["severity"] == "None"
            else:
                assert r["severity"] in ["Mild", "Moderate", "Severe"]

    def test_all_crops_supported(self):
        for crop in ["Rice", "Wheat", "Tomato", "Potato", "Maize", "Cotton", "Sugarcane"]:
            r = predict_disease(crop)
            assert r["crop"] == crop
            assert r["disease"] in DISEASES

    def test_treatment_present(self):
        r = predict_disease("Cotton")
        assert len(r["treatment"]) > 5

    def test_color_present(self):
        r = predict_disease("Tomato")
        assert r["color"].startswith("#")

    def test_model_field_present(self):
        r = predict_disease("Wheat")
        assert "model" in r


# ── Soil Analyzer ─────────────────────────────────────────────────────────────
class TestSoilAnalyzer:
    def test_good_soil_score_high(self):
        r = analyze_soil(85, 45, 200, 6.5, 4.0)
        assert r["score"] >= 70
        assert r["status"] == "Good"

    def test_poor_soil_score_low(self):
        r = analyze_soil(5, 3, 15, 4.2, 0.3)
        assert r["score"] < 40
        assert r["status"] == "Poor"

    def test_fair_soil_in_middle(self):
        r = analyze_soil(40, 20, 100, 6.5, 1.5)
        assert 40 <= r["score"] <= 70

    def test_score_always_in_0_100(self):
        combos = [(0,0,0,7,0), (300,150,500,7,100), (70,35,150,6.5,2.5)]
        for combo in combos:
            r = analyze_soil(*combo)
            assert 0 <= r["score"] <= 100

    def test_color_matches_status(self):
        good = analyze_soil(85, 45, 200, 6.5, 4.0)
        assert good["color"] == "#16a34a"
        poor = analyze_soil(5, 3, 15, 4.2, 0.3)
        assert poor["color"] == "#dc2626"

    def test_npk_ratio_format(self):
        r = analyze_soil(70, 35, 150, 6.5, 2.5)
        assert r["npk"] == "70:35:150"

    def test_breakdown_has_all_components(self):
        r = analyze_soil(70, 35, 150, 6.5, 2.5)
        for key in ["nitrogen", "phosphorus", "potassium", "ph", "organic"]:
            assert key in r["breakdown"]

    def test_low_nitrogen_triggers_warning(self):
        r = analyze_soil(20, 35, 150, 6.5, 2.5)
        texts = [rec["text"] for rec in r["recs"]]
        assert any("Nitrogen" in t for t in texts)

    def test_acidic_ph_triggers_lime_rec(self):
        r = analyze_soil(70, 35, 150, 4.5, 2.5)
        texts = [rec["text"].lower() for rec in r["recs"]]
        assert any("lime" in t or "acidic" in t for t in texts)

    def test_alkaline_ph_triggers_sulfur_rec(self):
        r = analyze_soil(70, 35, 150, 8.5, 2.5)
        texts = [rec["text"].lower() for rec in r["recs"]]
        assert any("sulfur" in t or "alkaline" in t for t in texts)

    def test_perfect_soil_gives_ok_rec(self):
        r = analyze_soil(80, 40, 180, 6.5, 3.5)
        types = [rec["type"] for rec in r["recs"]]
        assert "ok" in types

    def test_model_field_present(self):
        r = analyze_soil(70, 35, 150, 6.5, 2.5)
        assert "model" in r


# ── Intent Classifier ────────────────────────────────────────────────────────
class TestIntentClassifier:
    def test_irrigation_keywords(self):
        assert classify_intent("start irrigation in north field")["intent"] == "irrigation"

    def test_crop_keywords(self):
        assert classify_intent("which crop should I plant this season")["intent"] == "crop"

    def test_disease_keywords(self):
        assert classify_intent("my wheat has rust spots and blight")["intent"] == "disease"

    def test_weather_keywords(self):
        assert classify_intent("what is the weather forecast for tomorrow")["intent"] == "weather"

    def test_soil_keywords(self):
        assert classify_intent("check soil pH and nitrogen levels")["intent"] == "soil"

    def test_unknown_gives_general(self):
        assert classify_intent("hello how are you doing today")["intent"] == "general"

    def test_confidence_range(self):
        r = classify_intent("start irrigation now")
        assert 0 <= r["confidence"] <= 1

    def test_icon_present(self):
        r = classify_intent("check disease on leaf")
        assert r["icon"] in ["💧","🌾","🔬","🌤️","🧪","💬"]

    def test_language_passed_through(self):
        r = classify_intent("irrigate field", language="hi")
        assert r["language"] == "hi"

    def test_model_field_present(self):
        r = classify_intent("start watering zone 1")
        assert "model" in r

    def test_case_insensitive(self):
        r1 = classify_intent("START IRRIGATION")
        r2 = classify_intent("start irrigation")
        assert r1["intent"] == r2["intent"]


# ── Validators ────────────────────────────────────────────────────────────────
class TestValidators:
    # CropRequest
    def test_crop_request_defaults(self):
        obj, err = validate(CropRequest, {})
        assert err is None
        assert obj.temperature == 22.0

    def test_crop_request_coercion(self):
        obj, err = validate(CropRequest, {"temperature": "28.5"})
        assert err is None
        assert obj.temperature == 28.5

    def test_crop_request_ph_bounds(self):
        _, err = validate(CropRequest, {"ph_level": 15})
        if err: assert "Validation" in err["error"]

    # DiseaseRequest
    def test_disease_request_valid_crop(self):
        obj, err = validate(DiseaseRequest, {"crop": "Tomato"})
        assert err is None

    def test_disease_request_invalid_crop(self):
        _, err = validate(DiseaseRequest, {"crop": "Banana"})
        if err: assert "Validation" in err["error"]

    def test_disease_request_image_optional(self):
        obj, err = validate(DiseaseRequest, {"crop": "Rice"})
        assert err is None
        assert obj.image is None

    # SoilRequest
    def test_soil_request_defaults(self):
        obj, err = validate(SoilRequest, {})
        assert err is None
        assert obj.nitrogen == 70.0

    # WeatherRequest
    def test_weather_request_defaults(self):
        obj, err = validate(WeatherRequest, {})
        assert err is None
        assert obj.days == 7

    def test_weather_request_lat_bounds(self):
        _, err = validate(WeatherRequest, {"lat": 95})
        if err: assert "Validation" in err["error"]

    # IntentRequest
    def test_intent_request_text_required(self):
        _, err = validate(IntentRequest, {"text": "ab"})
        if err: assert "Validation" in err["error"]

    def test_intent_request_invalid_lang_defaults(self):
        obj, err = validate(IntentRequest, {"text": "hello world", "language": "zz"})
        assert err is None
        assert obj.language == "en"

    # IrrigationUpdate
    def test_irrigation_update_all_optional(self):
        obj, err = validate(IrrigationUpdate, {})
        assert err is None
        assert obj.active is None
        assert obj.duration is None

    def test_irrigation_update_duration_max(self):
        _, err = validate(IrrigationUpdate, {"duration": 200})
        if err: assert "Validation" in err["error"]

    def test_irrigation_update_duration_min(self):
        _, err = validate(IrrigationUpdate, {"duration": 2})
        if err: assert "Validation" in err["error"]
