"""api/irrigation.py — Irrigation zone management endpoints."""

from flask import Blueprint, jsonify, request
from services.auth import require_roles
from services.irrigation import get_zones, recommend_irrigation_plan, update_zone

bp = Blueprint("irrigation", __name__)


@bp.route("")
@bp.route("/")
def zones():
    """GET /api/irrigation — all zone configurations."""
    return jsonify(get_zones())


@bp.route("/recommend", methods=["GET"])
def recommend():
    """GET /api/irrigation/recommend — forecast-aware irrigation plan."""
    zone_id = request.args.get("zone_id")
    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon")

    try:
        lat = float(lat_raw) if lat_raw is not None else None
        lon = float(lon_raw) if lon_raw is not None else None
    except ValueError:
        return jsonify({"error": "lat/lon must be valid numbers"}), 400

    kwargs = {}
    if lat is not None and lon is not None:
        kwargs["lat"] = lat
        kwargs["lon"] = lon

    result = recommend_irrigation_plan(zone_id=zone_id, **kwargs)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


@bp.route("/<zone_id>", methods=["POST"])
@require_roles("agronomist", "admin")
def update(zone_id: str):
    """POST /api/irrigation/<zone_id> — update zone settings."""
    data = request.get_json() or {}
    result = update_zone(zone_id, data)
    if result is None:
        return jsonify({"error": f"Zone '{zone_id}' not found"}), 404
    return jsonify(result)
