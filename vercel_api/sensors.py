import json
from flask import Flask, jsonify

app = Flask("vercel_sensors")


def _safe_call_get_sensor_readings():
    try:
        from services.sensors import get_sensor_readings
        return get_sensor_readings()
    except Exception as e:
        return {"error": "sensor_unavailable", "detail": str(e)}


@app.route("/", methods=["GET"])
def _sensors():
    data = _safe_call_get_sensor_readings()
    if "error" in data:
        return jsonify(data), 503
    return jsonify(data)

