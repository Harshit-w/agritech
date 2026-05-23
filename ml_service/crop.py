"""ml_service/crop.py — Crop recommendation (Groq LLM + rule-based fallback)."""

import os
import json
import random
import logging
from pathlib import Path
import requests

log = logging.getLogger(__name__)

CROP_DATA = {
    "Rice":      {"temp": [20, 35], "ph": [5.5, 7.0], "moist": [60, 90], "icon": "🌾", "season": "Kharif"},
    "Wheat":     {"temp": [15, 28], "ph": [6.0, 7.5], "moist": [40, 65], "icon": "🌿", "season": "Rabi"},
    "Maize":     {"temp": [18, 32], "ph": [5.8, 7.0], "moist": [50, 75], "icon": "🌽", "season": "Kharif"},
    "Tomato":    {"temp": [20, 30], "ph": [6.0, 6.8], "moist": [55, 75], "icon": "🍅", "season": "All"},
    "Potato":    {"temp": [15, 25], "ph": [5.0, 6.5], "moist": [60, 80], "icon": "🥔", "season": "Rabi"},
    "Cotton":    {"temp": [25, 38], "ph": [6.0, 8.0], "moist": [30, 60], "icon": "🌸", "season": "Kharif"},
    "Sugarcane": {"temp": [24, 38], "ph": [6.0, 7.5], "moist": [65, 85], "icon": "🎋", "season": "Annual"},
}

# Try to load real model
_model = None
_le    = None

def _try_load():
    global _model, _le
    try:
        import joblib
        model_path = Path("models/crop_model.pkl")
        le_path    = Path("models/le_crop.pkl")
        if model_path.exists() and le_path.exists():
            _model = joblib.load(model_path)
            _le    = joblib.load(le_path)
            log.info("✅ Loaded crop_model.pkl")
    except Exception as e:
        log.debug(f"No crop model file: {e}")

_try_load()


# ── Groq LLM settings ───────────────────────────────────────────────────────
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")


def _query_groq_for_crops(features: dict) -> dict | None:
    """Ask Groq LLM for a smart crop recommendation. Returns dict matching
    the existing return schema or None on failure.
    """
    if not GROQ_KEY:
        return None

    system = (
        "You are AgriBot, an expert agricultural assistant. Given the input field "
        "parameters (temperature, humidity, soil moisture, pH, N, P, K) and the "
        "regional context (India), return the best crop recommendation and top 5 "
        "matches formatted as JSON. Output MUST be valid JSON only with keys: \n"
        "crop (string), icon (emoji), confidence (number 0-100), model (string), top5 (array).\n"
        "Each top5 item should contain: name (string), icon (emoji), score (number 0-100), temp (string like '15-28°C'), ph (string like '6.0-7.5').\n"
        "Be concise and prefer common Indian crops. Use emojis from this mapping: Rice: 🌾, Wheat: 🌿, Maize: 🌽, Tomato: 🍅, Potato: 🥔, Cotton: 🌸, Sugarcane: 🎋, default: 🌱."
    )

    user = (
        f"Input parameters: temperature={features.get('temperature')}, humidity={features.get('humidity')}, "
        f"soil_moisture={features.get('soil_moisture')}, ph_level={features.get('ph_level')}, "
        f"nitrogen={features.get('nitrogen')}, phosphorus={features.get('phosphorus')}, potassium={features.get('potassium')}\n"
        "Return JSON as described, do not include explanation text."
    )

    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.2,
        "max_tokens": 300,
        "stream": False,
    }

    try:
        resp = requests.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        j = resp.json()

        # Groq may return content in several places depending on API version
        content = None
        try:
            content = j.get("choices", [])[0].get("message", {}).get("content")
        except Exception:
            content = None
        if not content:
            # Try older style
            try:
                content = j.get("choices", [])[0].get("text")
            except Exception:
                content = None

        if not content:
            log.debug("Groq response had no content: %s", j)
            return None

        # Ensure we have JSON — strip surrounding backticks or markdown
        text = content.strip()
        # If wrapped in ```json ... ``` remove fences
        if text.startswith("```") and "json" in text[:10].lower():
            parts = text.split("\n")
            # remove first line and last fence
            text = "\n".join(parts[1:-1]) if len(parts) > 2 else text

        # Some LLMs reply with trailing explanation after JSON — try to find first JSON object
        try:
            # Find first { and last }
            first = text.find("{")
            last = text.rfind("}")
            if first != -1 and last != -1:
                text = text[first : last + 1]
            parsed = json.loads(text)
            # Validate minimal structure
            if isinstance(parsed, dict) and "crop" in parsed and "top5" in parsed:
                return parsed
            return None
        except Exception as e:
            log.warning(f"Failed to parse Groq crop JSON: {e} -- content: {text[:200]}")
            return None

    except Exception as e:
        log.warning(f"Groq crop request failed: {e}")
        return None


def predict_crop(temperature, humidity, soil_moisture, ph_level,
                 nitrogen, phosphorus, potassium) -> dict:
    """Predict best crop. Uses real RandomForest if available, else rule-based."""
    features = {
        "temperature": temperature,
        "humidity": humidity,
        "soil_moisture": soil_moisture,
        "ph_level": ph_level,
        "nitrogen": nitrogen,
        "phosphorus": phosphorus,
        "potassium": potassium,
    }

    # Try LLM first (Groq) — returns normalized JSON matching our schema
    try:
        llm_resp = _query_groq_for_crops(features)
        if llm_resp:
            # Normalize response to expected keys and types
            crop = llm_resp.get("crop")
            icon = llm_resp.get("icon") or CROP_DATA.get(crop, {}).get("icon", "🌱")
            confidence = float(llm_resp.get("confidence") or 0) if llm_resp.get("confidence") is not None else 0.0
            top5_raw = llm_resp.get("top5") or []
            top5 = []
            for t in top5_raw[:5]:
                name = t.get("name")
                score = float(t.get("score") or 0)
                icon_t = t.get("icon") or CROP_DATA.get(name, {}).get("icon", "🌱")
                temp = t.get("temp") or f"{CROP_DATA.get(name,{}).get('temp',['-','-'])[0]}-{CROP_DATA.get(name,{}).get('temp',['-','-'])[1]}°C"
                ph = t.get("ph") or f"{CROP_DATA.get(name,{}).get('ph',['-','-'])[0]}-{CROP_DATA.get(name,{}).get('ph',['-','-'])[1]}"
                top5.append({"name": name, "score": round(score, 1), "icon": icon_t, "temp": temp, "ph": ph})

            return {
                "crop": crop,
                "icon": icon,
                "confidence": round(confidence, 1),
                "top5": top5,
                "model": "Groq LLM",
            }
    except Exception as e:
        log.warning(f"LLM crop recommendation failed: {e}")

    if _model and _le:
        try:
            import numpy as np
            features = np.array([[temperature, humidity, soil_moisture,
                                   ph_level, nitrogen, phosphorus, potassium]])
            idx    = _model.predict(features)[0]
            probs  = _model.predict_proba(features)[0]
            crop   = _le.inverse_transform([idx])[0]
            conf   = round(probs[idx] * 100, 1)
            top5   = sorted(zip(_le.classes_, probs * 100), key=lambda x: -x[1])[:5]
            return {
                "crop": crop,
                "icon": CROP_DATA.get(crop, {}).get("icon", "🌱"),
                "confidence": conf,
                "top5": [{"name": c, "score": round(s, 1),
                          "icon": CROP_DATA.get(c, {}).get("icon", "🌱"),
                          "temp": f"{CROP_DATA.get(c,{}).get('temp',['-','-'])[0]}-{CROP_DATA.get(c,{}).get('temp',['-','-'])[1]}°C",
                          "ph":   f"{CROP_DATA.get(c,{}).get('ph',['-','-'])[0]}-{CROP_DATA.get(c,{}).get('ph',['-','-'])[1]}"}
                         for c, s in top5],
                "model": "RandomForest (trained)",
            }
        except Exception as e:
            log.warning(f"Model inference failed, using rule-based: {e}")

    # Rule-based scoring
    scores = {}
    for crop, d in CROP_DATA.items():
        s = 0
        t1, t2 = d["temp"]; s += 30 if t1 <= temperature <= t2 else max(0, 30 - abs(temperature - (t1+t2)/2) * 2)
        p1, p2 = d["ph"];   s += 25 if p1 <= ph_level <= p2   else max(0, 25 - abs(ph_level - (p1+p2)/2) * 10)
        m1, m2 = d["moist"];s += 25 if m1 <= soil_moisture <= m2 else max(0, 25 - abs(soil_moisture - (m1+m2)/2))
        s += min(20, (nitrogen + phosphorus * 0.5 + potassium * 0.1) / 10)
        scores[crop] = min(100, max(0, s + random.uniform(-2, 2)))

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top, sc = ranked[0]
    return {
        "crop":       top,
        "icon":       CROP_DATA[top]["icon"],
        "confidence": round(sc, 1),
        "top5": [
            {"name": c, "score": round(s, 1), "icon": CROP_DATA[c]["icon"],
             "temp": f"{CROP_DATA[c]['temp'][0]}-{CROP_DATA[c]['temp'][1]}°C",
             "ph":   f"{CROP_DATA[c]['ph'][0]}-{CROP_DATA[c]['ph'][1]}"}
            for c, s in ranked[:5]
        ],
        "model": "Rule-based (no model file)",
    }
