import json
from flask import Flask, jsonify, request

app = Flask("vercel_predict_disease")


@app.route("/", methods=["POST"])
def _predict_disease():
    try:
        body = request.get_json() or {}
    except Exception:
        body = {}

    crop = body.get("crop", "Tomato")
    image_b64 = body.get("image")

    try:
        from ml_service import disease as disease_mod
        r = disease_mod.predict_disease(crop, image_b64)
        return jsonify(r)
    except Exception as e:
        return jsonify({"error": "model_unavailable", "detail": str(e), "message": "Disease detection may require heavy ML dependencies or model files — consider container host."}), 503

