"""
services/database.py
Optional lightweight persistence layer using Python's built-in sqlite3.
Stores sensor readings, alerts, and irrigation logs.
Swap DATABASE_URL in .env to use PostgreSQL in production.

Usage:
    from services.database import db
    db.init()
    db.save_reading(sensor_dict)
    rows = db.get_readings(limit=100)
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

log = logging.getLogger(__name__)

DB_PATH = Path("agritech.db")


class Database:
    """Minimal SQLite wrapper. Thread-safe via connection-per-call pattern."""

    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self._initialized = False

    # ── Connection ────────────────────────────────────────────────────────────
    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Init ──────────────────────────────────────────────────────────────────
    def init(self):
        """Create tables if they don't exist."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    temperature REAL,
                    humidity    REAL,
                    soil_moisture REAL,
                    ph_level    REAL,
                    light_intensity INTEGER,
                    nitrogen    INTEGER,
                    phosphorus  INTEGER,
                    potassium   INTEGER,
                    source      TEXT,
                    created_at  TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    type       TEXT NOT NULL,
                    title      TEXT NOT NULL,
                    message    TEXT,
                    acknowledged INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS irrigation_log (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    zone_id   TEXT NOT NULL,
                    zone_name TEXT,
                    action    TEXT,
                    duration  INTEGER,
                    schedule  TEXT,
                    timestamp TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS predictions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_type  TEXT NOT NULL,
                    input_data  TEXT,
                    result      TEXT,
                    confidence  REAL,
                    timestamp   TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_readings_ts  ON sensor_readings(timestamp);
                CREATE INDEX IF NOT EXISTS idx_alerts_ts    ON alerts(created_at);
                CREATE INDEX IF NOT EXISTS idx_preds_type   ON predictions(model_type);
            """)
        self._initialized = True
        log.info(f"Database initialized at {self.path}")

    # ── Sensor readings ───────────────────────────────────────────────────────
    def save_reading(self, reading: dict) -> int:
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO sensor_readings
                  (timestamp, temperature, humidity, soil_moisture, ph_level,
                   light_intensity, nitrogen, phosphorus, potassium, source)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                reading.get("timestamp", datetime.now().isoformat()),
                reading.get("temperature"),
                reading.get("humidity"),
                reading.get("soil_moisture"),
                reading.get("ph_level"),
                reading.get("light_intensity"),
                reading.get("nitrogen"),
                reading.get("phosphorus"),
                reading.get("potassium"),
                reading.get("source", "unknown"),
            ))
            return cur.lastrowid

    def get_readings(self, hours: int = 24, limit: int = 500) -> list:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM sensor_readings
                WHERE timestamp >= datetime('now', ?)
                ORDER BY timestamp DESC
                LIMIT ?
            """, (f"-{hours} hours", limit)).fetchall()
            return [dict(row) for row in rows]

    # ── Alerts ────────────────────────────────────────────────────────────────
    def save_alert(self, alert: dict) -> int:
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO alerts (type, title, message)
                VALUES (?, ?, ?)
            """, (alert.get("type"), alert.get("title"), alert.get("msg")))
            return cur.lastrowid

    def get_alerts(self, limit: int = 50) -> list:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]

    def acknowledge_alert(self, alert_id: int) -> bool:
        with self._conn() as conn:
            conn.execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (alert_id,))
            return True

    # ── Irrigation log ────────────────────────────────────────────────────────
    def log_irrigation(self, zone_id: str, zone_name: str, action: str,
                       duration: int = None, schedule: str = None) -> int:
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO irrigation_log (zone_id, zone_name, action, duration, schedule)
                VALUES (?, ?, ?, ?, ?)
            """, (zone_id, zone_name, action, duration, schedule))
            return cur.lastrowid

    def get_irrigation_log(self, zone_id: str = None, limit: int = 100) -> list:
        with self._conn() as conn:
            if zone_id:
                rows = conn.execute(
                    "SELECT * FROM irrigation_log WHERE zone_id=? ORDER BY timestamp DESC LIMIT ?",
                    (zone_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM irrigation_log ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(row) for row in rows]

    # ── ML predictions ────────────────────────────────────────────────────────
    def save_prediction(self, model_type: str, input_data: dict,
                        result: dict, confidence: float = None) -> int:
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO predictions (model_type, input_data, result, confidence)
                VALUES (?, ?, ?, ?)
            """, (model_type, json.dumps(input_data), json.dumps(result), confidence))
            return cur.lastrowid

    def get_predictions(self, model_type: str = None, limit: int = 100) -> list:
        with self._conn() as conn:
            if model_type:
                rows = conn.execute(
                    "SELECT * FROM predictions WHERE model_type=? ORDER BY timestamp DESC LIMIT ?",
                    (model_type, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM predictions ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["input_data"] = json.loads(d["input_data"]) if d["input_data"] else {}
                d["result"]     = json.loads(d["result"])     if d["result"]     else {}
                result.append(d)
            return result

    # ── Stats ─────────────────────────────────────────────────────────────────
    def stats(self) -> dict:
        with self._conn() as conn:
            return {
                "total_readings":   conn.execute("SELECT COUNT(*) FROM sensor_readings").fetchone()[0],
                "total_alerts":     conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
                "total_predictions":conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0],
                "irrigation_events":conn.execute("SELECT COUNT(*) FROM irrigation_log").fetchone()[0],
            }


# Singleton instance
db = Database()
