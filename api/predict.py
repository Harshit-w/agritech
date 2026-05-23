"""api/predict.py — All ML prediction endpoints."""

from flask import Blueprint, jsonify, request
from ml_service.crop       import predict_crop
from ml_service.disease    import predict_disease
from ml_service.soil       import analyze_soil
from ml_service.intent     import classify_intent
from api.rate_limit        import rate_limit

bp = Blueprint("predict", __name__)


@bp.route("/crop", methods=["POST"])
@rate_limit("predict")
def crop():
    """POST /api/predict/crop — crop recommendation."""
    d = request.get_json() or {}
    result = predict_crop(
        temperature   = float(d.get("temperature",   22)),
        humidity      = float(d.get("humidity",      65)),
        soil_moisture = float(d.get("soil_moisture", 55)),
        ph_level      = float(d.get("ph_level",     6.5)),
        nitrogen      = float(d.get("nitrogen",      70)),
        phosphorus    = float(d.get("phosphorus",    35)),
        potassium     = float(d.get("potassium",    150)),
    )
    return jsonify(result)


@bp.route("/disease", methods=["POST"])
@rate_limit("predict")
def disease():
    """POST /api/predict/disease — leaf disease detection."""
    d    = request.get_json() or {}
    crop = d.get("crop", "Tomato")
    img  = d.get("image")          # base64 string (optional)
    try:
        return jsonify(predict_disease(crop, img))
    except Exception as e:
        return jsonify({
            "error": f"Disease prediction failed: {e}",
            "disease": "Unknown",
            "healthy": False,
            "confidence": 0,
            "crop": crop,
            "color": "#6b7280",
            "severity": "Unknown",
            "treatment": "Model inference failed. Verify ML dependencies and model files.",
            "probs": {},
            "model": "Prediction error",
        }), 500


@bp.route("/soil", methods=["POST"])
@rate_limit("predict")
def soil():
    """POST /api/predict/soil — soil health analysis."""
    d = request.get_json() or {}
    result = analyze_soil(
        nitrogen      = float(d.get("nitrogen",       70)),
        phosphorus    = float(d.get("phosphorus",     35)),
        potassium     = float(d.get("potassium",     150)),
        ph_level      = float(d.get("ph_level",      6.5)),
        organic_matter= float(d.get("organic_matter", 2.5)),
    )
    return jsonify(result)


@bp.route("/intent", methods=["POST"])
@rate_limit("predict")
def intent():
    """POST /api/predict/intent — NLP intent classification."""
    d    = request.get_json() or {}
    text = d.get("text", "")
    if len(text) < 3:
        return jsonify({"error": "Text too short (min 3 chars)"}), 400
    lang = d.get("language", "en")
    return jsonify(classify_intent(text, lang))
