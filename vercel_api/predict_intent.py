import json
from flask import Flask, jsonify, request

app = Flask("vercel_predict_intent")


@app.route("/", methods=["POST"])
def _predict_intent():
    try:
        body = request.get_json() or {}
    except Exception:
        body = {}
    try:
        from ml_service.intent import classify_intent
        text = body.get('text', '')
        lang = body.get('language', 'en')
        r = classify_intent(text, language=lang)
        return jsonify(r)
    except Exception as e:
        return jsonify({"error": "intent_unavailable", "detail": str(e)}), 503

