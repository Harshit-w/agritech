import json
from flask import Flask, jsonify

app = Flask("vercel_health")


@app.route("/", methods=["GET"])
def _health():
    body = {"status": "ok", "service": "AgriTech (serverless)", "timestamp": None}
    try:
        import time
        body["timestamp"] = time.time()
    except Exception:
        body["timestamp"] = None
    return jsonify(body)

