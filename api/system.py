"""api/system.py — Health check and status endpoints."""

from datetime import datetime
import time
from flask import Blueprint, current_app, jsonify

bp = Blueprint("system", __name__)

_start_time = datetime.now()


@bp.route("/health")
def health():
    """GET /api/health — liveness probe for Docker / load balancers."""
    return jsonify({
        "status":    "healthy",
        "app":       "AgriTech v3",
        "timestamp": datetime.now().isoformat(),
    })


@bp.route("/status")
def status():
    """GET /api/status — operational summary."""
    uptime = str(datetime.now() - _start_time).split(".")[0]
    return jsonify({
        "status":          "operational",
        "version":         "3.0.0",
        "uptime":          uptime,
        "sensors_online":  8,
        "irrigation_zones": 4,
        "ml_models":       5,
        "weather_source":  "Open-Meteo (free, no key)",
        "timestamp":       datetime.now().isoformat(),
    })


@bp.route("/metrics")
def metrics():
    """GET /api/metrics — basic request/error/latency metrics."""
    m = current_app.extensions.get("metrics", {})
    started_at = float(m.get("started_at", time.time()))
    uptime_s = max(1.0, time.time() - started_at)

    path_summary = {}
    for path, stats in m.get("paths", {}).items():
        count = max(1, int(stats.get("count", 0)))
        total_ms = float(stats.get("total_ms", 0.0))
        path_summary[path] = {
            "count": count,
            "avg_ms": round(total_ms / count, 2),
            "max_ms": round(float(stats.get("max_ms", 0.0)), 2),
        }

    total = int(m.get("total_requests", 0))
    return jsonify({
        "uptime_seconds": round(uptime_s, 1),
        "total_requests": total,
        "requests_per_sec": round(total / uptime_s, 3),
        "errors_4xx": int(m.get("errors_4xx", 0)),
        "errors_5xx": int(m.get("errors_5xx", 0)),
        "status_counts": m.get("status_counts", {}),
        "paths": path_summary,
        "timestamp": datetime.now().isoformat(),
    })


@bp.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404


@bp.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500
