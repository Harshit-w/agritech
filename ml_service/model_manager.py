"""
ml_service/model_manager.py
Thread-safe singleton that loads, caches, and hot-reloads all ML model files.
Falls back gracefully when files are absent.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

MODELS_DIR = Path("models")

MODEL_FILES = {
    "crop":       ("crop_model.pkl",    "sklearn"),
    "le_crop":    ("le_crop.pkl",       "sklearn"),
    "le_soil":    ("le_soil.pkl",       "sklearn"),
    "soil":       ("soil_analysis.pkl", "sklearn"),
    "intent":     ("intent_model.pkl",  "sklearn"),
    "vectorizer": ("vectorizer.pkl",    "sklearn"),
    "weather":    ("weather_model.pkl", "sklearn"),
    "disease":    ("disease_model.h5",  "keras"),
}


class ModelManager:
    _inst = None
    _lock = threading.Lock()

    def __init__(self):
        self._models = {}
        self._errors = {}
        self._times  = {}
        self._rlock  = threading.RLock()
        self._initialized = False

    @classmethod
    def instance(cls):
        if cls._inst is None:
            with cls._lock:
                if cls._inst is None:
                    cls._inst = cls()
                    cls._inst._load_all()
        return cls._inst

    def _load_all(self):
        log.info("ModelManager: scanning models/ directory...")
        for name, (filename, kind) in MODEL_FILES.items():
            self._load_one(name, filename, kind)
        self._initialized = True
        loaded = len(self._models)
        mocked = len(MODEL_FILES) - loaded - len(self._errors)
        log.info(f"ModelManager ready — {loaded} loaded, {len(self._errors)} failed, {mocked} mocked")

    def _load_one(self, name, filename, kind):
        path = MODELS_DIR / filename
        if not path.exists():
            log.info(f"  ⚠️  {name}: file not found ({filename}) — will use mock")
            return False
        try:
            t0 = time.perf_counter()
            if kind == "sklearn":
                import joblib
                model = joblib.load(path)
            elif kind == "keras":
                import tensorflow as tf
                model = tf.keras.models.load_model(str(path))
            else:
                raise ValueError(f"Unknown kind: {kind}")
            elapsed = round(time.perf_counter() - t0, 3)
            with self._rlock:
                self._models[name] = model
                self._times[name]  = elapsed
                self._errors.pop(name, None)
            log.info(f"  ✓ loaded {name} from {filename} ({elapsed}s)")
            return True
        except Exception as e:
            log.warning(f"  ✗ failed to load {name}: {e}")
            with self._rlock:
                self._errors[name] = str(e)
            return False

    def get(self, name):
        """Get model by name. Returns None if not loaded."""
        with self._rlock:
            return self._models.get(name)

    def has(self, name):
        """Check if model is loaded."""
        with self._rlock:
            return name in self._models

    def get_or_none(self, name):
        """Safely get model, returns None if missing."""
        with self._rlock:
            return self._models.get(name)

    def get_status(self, name):
        """Get status of a model: 'loaded', 'failed', or 'missing'."""
        with self._rlock:
            if name in self._models:
                return "loaded"
            elif name in self._errors:
                return "failed"
            else:
                return "missing"

    def reload(self, name=None):
        targets = [name] if name else list(MODEL_FILES.keys())
        results = {}
        for n in targets:
            info = MODEL_FILES.get(n)
            if info:
                results[n] = self._load_one(n, info[0], info[1])
        return results

    def status(self):
        with self._rlock:
            return {
                "initialized":  self._initialized,
                "loaded_count": len(self._models),
                "loaded": {k: {"file": MODEL_FILES[k][0], "load_time_s": self._times.get(k)} for k in self._models},
                "failed": {k: v for k, v in self._errors.items()},
                "missing": [k for k in MODEL_FILES if k not in self._models and k not in self._errors],
                "summary": f"{len(self._models)}/{len(MODEL_FILES)} models loaded, {len(self._errors)} failed, {len(MODEL_FILES) - len(self._models) - len(self._errors)} missing"
            }

    def __repr__(self):
        return f"<ModelManager loaded={len(self._models)} initialized={self._initialized}>"
