"""api/sensors.py — Sensor readings and alert endpoints."""

from flask import Blueprint, jsonify, request
from services.sensors import (
    get_sensor_readings, get_sensor_history, generate_alerts,
    connect_hardware, disconnect_hardware, get_hardware_status
)
from api.rate_limit import rate_limit
from services.auth import require_roles

bp = Blueprint("sensors", __name__)


@bp.route("/sensors")
@rate_limit("sensors")
def sensors():
    """GET /api/sensors — current 8-sensor readings.
    Optional: ?lat=&lon= to get live weather from specific coordinates.
    """
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    if lat and lon:
        try:
            return jsonify(get_sensor_readings(float(lat), float(lon)))
        except ValueError:
            pass
    return jsonify(get_sensor_readings())


@bp.route("/sensors/history")
@rate_limit("sensors")
def sensors_history():
    """GET /api/sensors/history?hours=24 — time-series data."""
    hours = max(1, min(int(request.args.get("hours", 24)), 168))
    return jsonify({"hours": hours, "data": get_sensor_history(hours)})


@bp.route("/alerts")
@rate_limit("sensors")
def alerts():
    """GET /api/alerts — threshold-based farm alerts."""
    s = get_sensor_readings()
    alert_list = generate_alerts(s)
    return jsonify({"alerts": alert_list, "count": len(alert_list)})


# ── Hardware Connection Endpoints ─────────────────────────────────────────────
@bp.route("/hardware/status", methods=["GET"])
@rate_limit("sensors")
def hardware_status():
    """GET /api/hardware/status — Check hardware connection status."""
    status = get_hardware_status()
    return jsonify({
        "connected": status["connected"],
        "device": status["device"],
        "connection_type": status["connection_type"],
        "message": f"Connected to {status['device']} via {status['connection_type']}" 
                   if status["connected"] 
                   else "No hardware connected. Currently using simulated data."
    })


@bp.route("/hardware/connect", methods=["POST"])
@rate_limit("sensors")
@require_roles("agronomist", "admin")
def hardware_connect():
    """POST /api/hardware/connect — Connect to hardware sensor.
    Body: {"device": "device_name", "connection_type": "bluetooth|usb"}
    """
    data = request.get_json() or {}
    device = data.get("device", "").strip()
    conn_type = data.get("connection_type", "bluetooth").lower()

    if not device:
        return jsonify({"error": "device name required"}), 400
    if conn_type not in ["bluetooth", "usb"]:
        return jsonify({"error": "connection_type must be 'bluetooth' or 'usb'"}), 400

    result = connect_hardware(device, conn_type)
    if result["success"]:
        return jsonify({
            "success": True,
            "message": f"Connected to {device} via {conn_type}",
            "status": result["status"]
        })
    else:
        return jsonify({
            "success": False,
            "error": result.get("error", "Connection failed")
        }), 500


@bp.route("/hardware/disconnect", methods=["POST"])
@rate_limit("sensors")
@require_roles("agronomist", "admin")
def hardware_disconnect():
    """POST /api/hardware/disconnect — Disconnect from hardware sensor."""
    result = disconnect_hardware()
    if result["success"]:
        return jsonify({
            "success": True,
            "message": "Hardware disconnected. Reverting to simulated data.",
            "status": result["status"]
        })
    else:
        return jsonify({
            "success": False,
            "error": result.get("error", "Disconnection failed")
        }), 500
