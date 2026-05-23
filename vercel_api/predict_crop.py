import json
from flask import Flask, jsonify, request

app = Flask("vercel_predict_crop")


@app.route("/", methods=["POST"])
def _predict_crop():
    try:
        body = request.get_json() or {}
    except Exception:
        body = {}
    try:
        from ml_service.crop import predict_crop
        r = predict_crop(**body)
        return jsonify(r)
    except Exception as e:
        return jsonify({"error": "crop_unavailable", "detail": str(e)}), 503

