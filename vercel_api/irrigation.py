import json
from flask import Flask, jsonify, request

app = Flask("vercel_irrigation")


@app.route("/", methods=["GET"])
def _get_zones():
    try:
        from services.irrigation import get_zones
        zones = get_zones()
        return jsonify(zones)
    except Exception as e:
        return jsonify({"error": "irrigation_unavailable", "detail": str(e)}), 503


@app.route("/update", methods=["POST"])
def _update_zone():
    try:
        from services.irrigation import update_zone
    except Exception as e:
        return jsonify({"error": "irrigation_unavailable", "detail": str(e)}), 503

    payload = request.get_json() or {}
    zone_id = payload.get("zone_id")
    data = payload.get("data", {})
    if not zone_id:
        return jsonify({"error": "missing_zone_id"}), 400
    res = update_zone(zone_id, data)
    if res is None:
        return jsonify({"error": "zone_not_found"}), 404
    return jsonify(res)

