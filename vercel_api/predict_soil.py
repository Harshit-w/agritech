import json
from flask import Flask, jsonify, request

app = Flask("vercel_predict_soil")


@app.route("/", methods=["POST"])
def _predict_soil():
    try:
        body = request.get_json() or {}
    except Exception:
        body = {}
    try:
        from ml_service.soil import analyze_soil
        params = [body.get('nitrogen', 70), body.get('phosphorus', 35), body.get('potassium', 150), body.get('ph_level', 6.5), body.get('organic_matter', 2.5)]
        r = analyze_soil(*params)
        return jsonify(r)
    except Exception as e:
        return jsonify({"error": "soil_unavailable", "detail": str(e)}), 503

