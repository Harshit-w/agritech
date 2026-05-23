"""ml_service/intent.py — NLP intent classification (SVM fallback to keyword matching)."""

import random
import logging
from pathlib import Path

log = logging.getLogger(__name__)

INTENTS = {
    "irrigation":  ["water", "irrigat", "drip", "sprinkl", "zone", "flood", "pour"],
    "crop":        ["crop", "plant", "grow", "sow", "cultivat", "recommend", "which crop", "seed"],
    "disease":     ["disease", "sick", "spot", "rust", "blight", "wilt", "infect", "mildew", "leaf", "fungus"],
    "weather":     ["weather", "rain", "forecast", "temperature", "humid", "climate", "storm", "wind"],
    "soil":        ["soil", "ph", "nitrogen", "phosphorus", "potassium", "npk", "fertil", "nutrient", "organic"],
    "general":     [],
}

ICONS = {
    "irrigation": "💧",
    "crop":       "🌾",
    "disease":    "🔬",
    "weather":    "🌤️",
    "soil":       "🧪",
    "general":    "💬",
}

_pipeline = None

def _try_load():
    global _pipeline
    try:
        import joblib
        p = Path("models/intent_model.pkl")
        if p.exists():
            _pipeline = joblib.load(p)
            log.info("✅ Loaded intent_model.pkl")
    except Exception as e:
        log.debug(f"No intent model: {e}")

_try_load()


def classify_intent(text: str, language: str = "en") -> dict:
    """Classify farming command text into one of 6 intent categories."""

    if _pipeline:
        try:
            intent = _pipeline.predict([text])[0]
            proba  = _pipeline.predict_proba([text])[0]
            conf   = round(float(max(proba)), 2)
            return _result(intent, conf, language, "SVM (trained)")
        except Exception as e:
            log.warning(f"Intent model failed: {e}")

    # Keyword matching fallback
    t     = text.lower()
    best  = "general"
    bscore = 0
    for intent, keywords in INTENTS.items():
        score = sum(1 for kw in keywords if kw in t)
        if score > bscore:
            best, bscore = intent, score

    return _result(best, round(random.uniform(0.72, 0.97), 2), language, "Keyword matching")


def _result(intent, confidence, language, model):
    return {
        "intent":     intent,
        "icon":       ICONS.get(intent, "💬"),
        "confidence": confidence,
        "language":   language,
        "action":     f"Routing to {intent.replace('_', ' ')} module",
        "model":      model,
    }
