"""ml_service/soil.py — Soil health scoring and fertilizer recommendations."""

import logging
from pathlib import Path

log = logging.getLogger(__name__)

_model = None

def _try_load():
    global _model
    try:
        import joblib
        p = Path("models/soil_analysis.pkl")
        if p.exists():
            _model = joblib.load(p)
            log.info("✅ Loaded soil_analysis.pkl")
    except Exception as e:
        log.debug(f"No soil model: {e}")

_try_load()


def analyze_soil(nitrogen, phosphorus, potassium, ph_level, organic_matter) -> dict:
    """Compute soil health score + fertilizer recommendations."""

    if _model:
        try:
            import numpy as np
            features  = np.array([[nitrogen, phosphorus, potassium, ph_level, organic_matter]])
            score     = float(_model.predict(features)[0])
            score     = round(min(100, max(0, score)), 1)
            model_name = "Regression (trained)"
        except Exception as e:
            log.warning(f"Soil model failed: {e}")
            score, model_name = _rule_score(nitrogen, phosphorus, potassium, ph_level, organic_matter)
    else:
        score, model_name = _rule_score(nitrogen, phosphorus, potassium, ph_level, organic_matter)

    recs = _recommendations(nitrogen, phosphorus, potassium, ph_level, organic_matter)

    return {
        "score":   score,
        "status":  "Good" if score >= 70 else "Fair" if score >= 40 else "Poor",
        "color":   "#16a34a" if score >= 70 else "#d97706" if score >= 40 else "#dc2626",
        "npk":     f"{nitrogen}:{phosphorus}:{potassium}",
        "recs":    recs,
        "breakdown": {
            "nitrogen":   round(min(30, nitrogen / 4)     if nitrogen   <= 120 else max(0, 30 - (nitrogen - 120) / 5),    1),
            "phosphorus": round(min(20, phosphorus / 3)   if phosphorus <= 60  else max(0, 20 - (phosphorus - 60) / 3),   1),
            "potassium":  round(min(20, potassium / 12.5) if potassium  <= 250 else max(0, 20 - (potassium - 250) / 10),  1),
            "ph":         round(20 if 6.0 <= ph_level <= 7.0 else max(0, 20 - abs(ph_level - 6.5) * 8), 1),
            "organic":    round(min(10, organic_matter * 2), 1),
        },
        "model": model_name,
    }


def _rule_score(n, p, k, ph, om):
    ns  = min(30, n / 4)     if n  <= 120 else max(0, 30 - (n - 120) / 5)
    ps  = min(20, p / 3)     if p  <=  60 else max(0, 20 - (p - 60) / 3)
    ks  = min(20, k / 12.5)  if k  <= 250 else max(0, 20 - (k - 250) / 10)
    phs = 20 if 6.0 <= ph <= 7.0 else max(0, 20 - abs(ph - 6.5) * 8)
    os  = min(10, om * 2)
    return round(ns + ps + ks + phs + os, 1), "Rule-based (no model file)"


def _recommendations(n, p, k, ph, om) -> list:
    recs = []
    if n < 50:    recs.append({"type": "warn",    "text": "Low Nitrogen — apply urea or ammonium nitrate fertilizer."})
    elif n > 100: recs.append({"type": "caution", "text": "Excess Nitrogen — reduce N-rich fertilizers to avoid runoff."})
    if p < 20:    recs.append({"type": "warn",    "text": "Low Phosphorus — apply superphosphate or bone meal."})
    if k < 100:   recs.append({"type": "warn",    "text": "Low Potassium — apply potassium chloride or wood ash."})
    if ph < 6.0:  recs.append({"type": "action",  "text": f"Acidic Soil (pH {ph}) — apply agricultural lime to raise pH."})
    elif ph > 7.5:recs.append({"type": "action",  "text": f"Alkaline Soil (pH {ph}) — apply elemental sulfur to lower pH."})
    if om < 2.0:  recs.append({"type": "info",    "text": "Low Organic Matter — add compost or green manure."})
    if not recs:  recs.append({"type": "ok",      "text": "Excellent soil health — maintain current practices."})
    return recs
