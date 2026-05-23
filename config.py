"""
config.py — Centralised configuration with environment-variable overrides.
Copy .env.example to .env and edit before production deployment.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME:    str  = os.getenv("APP_NAME",    "AgriTech")
    APP_VERSION: str  = os.getenv("APP_VERSION", "3.0.0")
    SECRET_KEY:  str  = os.getenv("SECRET_KEY",  "change-me-in-production-agritech-v3")
    DEBUG:       bool = os.getenv("FLASK_DEBUG", "0") == "1"

    # ── Server ───────────────────────────────────────────────────────────────
    HOST:    str = os.getenv("HOST", "0.0.0.0")
    PORT:    int = int(os.getenv("PORT", "5000"))
    WORKERS: int = int(os.getenv("GUNICORN_WORKERS", "4"))

    # ── Default farm location ─────────────────────────────────────────────────
    DEFAULT_LAT:  float = float(os.getenv("DEFAULT_LAT",  "30.2139"))
    DEFAULT_LON:  float = float(os.getenv("DEFAULT_LON",  "78.1740"))
    DEFAULT_CITY: str   = os.getenv("DEFAULT_CITY", "Bageshwar, Uttarakhand, India")

    # ── Weather cache ─────────────────────────────────────────────────────────
    WEATHER_CACHE_TTL: int = int(os.getenv("WEATHER_CACHE_TTL", "300"))   # seconds

    # ── Sensor thresholds ─────────────────────────────────────────────────────
    TEMP_WARN_HIGH:     float = float(os.getenv("TEMP_WARN_HIGH",     "38.0"))
    TEMP_WARN_LOW:      float = float(os.getenv("TEMP_WARN_LOW",      "10.0"))
    MOISTURE_WARN_LOW:  float = float(os.getenv("MOISTURE_WARN_LOW",  "30.0"))
    MOISTURE_WARN_HIGH: float = float(os.getenv("MOISTURE_WARN_HIGH", "80.0"))
    HUMIDITY_WARN_HIGH: float = float(os.getenv("HUMIDITY_WARN_HIGH", "85.0"))
    PH_WARN_LOW:        float = float(os.getenv("PH_WARN_LOW",        "5.8"))
    PH_WARN_HIGH:       float = float(os.getenv("PH_WARN_HIGH",       "7.5"))

    # ── Paths ─────────────────────────────────────────────────────────────────
    MODELS_DIR:  Path = BASE_DIR / "models"
    LOGS_DIR:    Path = BASE_DIR / "logs"
    UPLOADS_DIR: Path = BASE_DIR / "uploads"

    # ── Upload limits ─────────────────────────────────────────────────────────
    MAX_CONTENT_LENGTH: int = 50 * 1024 * 1024   # 50 MB

    # ── Database (optional) ───────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///agritech.db")

    # ── Redis (optional) ──────────────────────────────────────────────────────
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ── Auth / RBAC (optional) ────────────────────────────────────────────────
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "0") == "1"
    AUTH_TOKEN_TTL_HOURS: int = int(os.getenv("AUTH_TOKEN_TTL_HOURS", "12"))
    AUTH_USERS_JSON: str = os.getenv(
        "AUTH_USERS_JSON",
        '{"admin":{"password":"admin123","role":"admin"},'
        '"agri":{"password":"agri123","role":"agronomist"},'
        '"viewer":{"password":"view123","role":"viewer"}}',
    )

    def __init__(self):
        # Ensure required directories exist
        for d in (self.MODELS_DIR, self.LOGS_DIR, self.UPLOADS_DIR):
            d.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DEBUG   = True
