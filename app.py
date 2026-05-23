"""
AgriTech v3 — AI-Powered Smart Farming Platform
app.py — Main Flask application entry point
"""

import logging
import threading
import time
from pathlib import Path
from flask import Flask, g, make_response, send_from_directory, request
from config import Config
from api.routes import register_routes

BASE_DIR = Path(__file__).resolve().parent

# ── logging ───────────────────────────────────────────────────────────────────
(BASE_DIR / "logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(BASE_DIR / "logs" / "app.log"), encoding="utf-8"),
    ],
)
log = logging.getLogger("agritech")

# ── app factory ───────────────────────────────────────────────────────────────
def create_app(config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    cfg = config or Config()
    app.config.from_object(cfg)
    app.extensions["metrics"] = {
        "started_at": time.time(),
        "total_requests": 0,
        "errors_4xx": 0,
        "errors_5xx": 0,
        "status_counts": {},
        "paths": {},
        "lock": threading.Lock(),
    }

    @app.before_request
    def log_request():
        """Log all incoming requests"""
        g._request_started = time.perf_counter()
        log.info(f">>> {request.method} {request.path} (from {request.remote_addr})")

    @app.after_request
    def set_headers(r):
        elapsed_ms = round((time.perf_counter() - getattr(g, "_request_started", time.perf_counter())) * 1000, 2)
        metrics = app.extensions.get("metrics", {})
        lock = metrics.get("lock")
        if lock:
            with lock:
                metrics["total_requests"] = metrics.get("total_requests", 0) + 1
                code_key = str(r.status_code)
                status_counts = metrics.setdefault("status_counts", {})
                status_counts[code_key] = status_counts.get(code_key, 0) + 1

                if 400 <= r.status_code < 500:
                    metrics["errors_4xx"] = metrics.get("errors_4xx", 0) + 1
                if r.status_code >= 500:
                    metrics["errors_5xx"] = metrics.get("errors_5xx", 0) + 1

                p = request.path
                pstats = metrics.setdefault("paths", {}).setdefault(
                    p,
                    {"count": 0, "total_ms": 0.0, "max_ms": 0.0},
                )
                pstats["count"] += 1
                pstats["total_ms"] = round(pstats["total_ms"] + elapsed_ms, 2)
                pstats["max_ms"] = max(pstats["max_ms"], elapsed_ms)

        r.headers["Access-Control-Allow-Origin"]  = "*"
        r.headers["Access-Control-Allow-Headers"] = "Content-Type"
        r.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        r.headers["X-Response-Time-ms"] = str(elapsed_ms)
        return r

    @app.route("/")
    def index():
        return make_response(send_from_directory("templates", "index.html"))

    register_routes(app)
    return app


app = create_app()

if __name__ == "__main__":
    from services.weather import warm_weather_cache
    from services.sensors import _set_hardware_status
    from config import Config
    cfg = Config()
    
    # Clear hardware status on startup (reset to disconnected)
    _set_hardware_status(False)
    
    log.info("🌱  AgriTech v3 starting…")
    log.info(f"📍  {cfg.DEFAULT_CITY}  ({cfg.DEFAULT_LAT:.4f}°N  {cfg.DEFAULT_LON:.4f}°E)")
    warm_weather_cache()
    app.run(host="0.0.0.0", port=5000, debug=False)
