"""
ml_service/disease.py
Handles: Binary (None,1) sigmoid, Multi-class (None,N) softmax, Colour fallback.
"""

import hashlib, json, logging
from pathlib import Path

log = logging.getLogger(__name__)

ROOT       = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "disease_model.h5"
CLASS_PATH = ROOT / "models" / "disease_classes.json"

# ── Helper functions defined FIRST so they can be used anywhere below ──────────

def _auto_color(label: str) -> str:
    l = label.lower()
    if any(w in l for w in ("healthy", "normal", "good")): return "#16a34a"
    if "blight" in l or "blast"   in l:                    return "#991b1b"
    if "rust"   in l:                                      return "#dc2626"
    if "spot"   in l or "brown"   in l:                    return "#ea580c"
    if "mildew" in l or "powdery" in l:                    return "#d97706"
    if "wilt"   in l or "bacterial" in l:                  return "#7c3aed"
    if "mosaic" in l or "virus"   in l:                    return "#0891b2"
    if "curl"   in l or "yellow"  in l:                    return "#ca8a04"
    if "mite"   in l or "spider"  in l:                    return "#b45309"
    return "#6b7280"

def _is_healthy(label: str) -> bool:
    return any(w in label.lower() for w in ("healthy", "normal", "good", "no disease"))

def _hash_img(b64: str) -> int:
    import base64
    raw = base64.b64decode(b64 + "==")
    return int(hashlib.sha256(raw).hexdigest(), 16)

def _severity(disease: str, seed: int) -> str:
    if _is_healthy(disease): return "None"
    idx = seed % 3
    if idx == 0: idx = 1
    return SEVERITIES[idx]

# ── Default state ──────────────────────────────────────────────────────────────
DISEASES    = ["Healthy", "Powdery Mildew", "Leaf Spot", "Rust", "Blight", "Wilt"]
SEVERITIES  = ["Mild", "Moderate", "Severe"]
IMG_SIZE    = (224, 224)
MODEL_TYPE  = "none"
THRESHOLD   = 0.5
HEALTHY_IDX = []
COLORS      = {d: _auto_color(d) for d in DISEASES}

# ── Load class mapping from disease_classes.json ───────────────────────────────
def _load_mapping():
    global DISEASES, IMG_SIZE, MODEL_TYPE, THRESHOLD, HEALTHY_IDX, COLORS
    if not CLASS_PATH.exists():
        return
    try:
        m       = json.loads(CLASS_PATH.read_text())
        classes = list(m["classes"].values())
        if not classes:
            return
        DISEASES    = classes
        h, w        = m.get("input_size", [224, 224])
        IMG_SIZE    = (h, w)
        MODEL_TYPE  = m.get("model_type", "multiclass")
        THRESHOLD   = float(m.get("threshold", 0.5))
        HEALTHY_IDX = m.get("healthy_indices", [])
        COLORS      = {lbl: _auto_color(lbl) for lbl in DISEASES}
        log.info(f"✅ disease_classes.json loaded — {len(DISEASES)} classes, type={MODEL_TYPE}")
    except Exception as e:
        log.warning(f"Could not read disease_classes.json: {e}")

_load_mapping()

# ── Load TensorFlow model ──────────────────────────────────────────────────────
_model     = None
_n_output  = 0
_tf_loaded = False

def _try_load():
    global _model, _n_output, _tf_loaded, MODEL_TYPE, IMG_SIZE
    if not MODEL_PATH.exists():
        return
    try:
        import warnings
        warnings.filterwarnings("ignore")
        import tensorflow as tf
        _model     = tf.keras.models.load_model(str(MODEL_PATH))
        _n_output  = _model.output_shape[-1]
        h = _model.input_shape[1] if len(_model.input_shape) >= 3 else IMG_SIZE[0]
        w = _model.input_shape[2] if len(_model.input_shape) >= 3 else IMG_SIZE[1]
        IMG_SIZE   = (h, w)
        _tf_loaded = True
        if _n_output == 1 and MODEL_TYPE == "none":
            MODEL_TYPE = "binary"
        elif MODEL_TYPE == "none":
            MODEL_TYPE = "multiclass"
        log.info(f"✅ disease_model.h5 loaded — {_n_output} output(s), type={MODEL_TYPE}, {h}×{w}")
    except ImportError:
        log.warning("TensorFlow not installed. Run: pip install tensorflow")
    except Exception as e:
        log.warning(f"Could not load disease_model.h5: {e}")

_try_load()

# ── Image loading ──────────────────────────────────────────────────────────────
def _load_image(b64: str):
    import base64, io
    import numpy as np
    from PIL import Image
    raw = base64.b64decode(b64 + "==")
    img = Image.open(io.BytesIO(raw)).convert("RGB").resize(IMG_SIZE)
    arr = np.array(img, dtype=np.float32) / 255.0
    return __import__("numpy").expand_dims(arr, 0)

# ── Binary inference ───────────────────────────────────────────────────────────
def _predict_binary(arr, b64: str):
    import warnings; warnings.filterwarnings("ignore")
    prob     = float(_model.predict(arr, verbose=0)[0][0])
    seed     = _hash_img(b64) % 3
    class0   = DISEASES[0] if len(DISEASES) > 0 else "Healthy"
    class1   = DISEASES[1] if len(DISEASES) > 1 else "Diseased"
    if prob >= THRESHOLD:
        disease = class1
        conf    = round(prob * 100, 1)
    else:
        disease = class0
        conf    = round((1 - prob) * 100, 1)
    probs    = {class0: round((1-prob)*100, 1), class1: round(prob*100, 1)}
    severity = _severity(disease, seed)
    note     = f"Binary CNN (sigmoid={round(prob,3)}, threshold={THRESHOLD})"
    return disease, conf, probs, severity, note

# ── Multi-class inference ──────────────────────────────────────────────────────
def _predict_multiclass(arr, b64: str):
    import warnings; warnings.filterwarnings("ignore")
    pout   = _model.predict(arr, verbose=0)[0]
    n      = len(pout)
    labels = DISEASES[:n] if n <= len(DISEASES) else DISEASES + [f"Class_{i}" for i in range(len(DISEASES), n)]
    idx    = int(pout.argmax())
    disease= labels[idx]
    conf   = round(float(pout[idx]) * 100, 1)
    probs  = {labels[i]: round(float(p)*100, 1) for i, p in enumerate(pout)}
    seed   = _hash_img(b64) % 3
    sev    = _severity(disease, seed)
    note   = f"CNN model ({n} classes)"
    return disease, conf, probs, sev, note

# ── Colour-feature fallback ────────────────────────────────────────────────────
def _colour_features(b64: str):
    import base64, io
    try:
        import numpy as np
        from PIL import Image
        raw = base64.b64decode(b64 + "==")
        img = Image.open(io.BytesIO(raw)).convert("RGB").resize((64, 64))
        arr = np.array(img, dtype=np.float32)
        r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
        t = 64 * 64
        return {
            "mean_r": float(r.mean()), "mean_g": float(g.mean()), "mean_b": float(b.mean()),
            "std_r":  float(r.std()),  "std_g":  float(g.std()),  "std_b":  float(b.std()),
            "yellow": float(((r>150)&(g>140)&(b<100)).sum()/t),
            "brown":  float(((r>140)&(g<110)&(b< 80)).sum()/t),
            "white":  float(((r>200)&(g>200)&(b>200)).sum()/t),
            "dark":   float(((r< 60)&(g< 80)&(b< 60)).sum()/t),
            "green":  float(((g>r)  &(g>b)  &(g>100)).sum()/t),
        }
    except Exception as e:
        log.debug(f"Feature extraction: {e}")
        return None

def _classify_colour(feat: dict, seed: int):
    scores = {
        "Healthy":        min(95, feat["green"]*60 + max(0,.3-feat["yellow"])*30 + max(0,.1-feat["brown"])*20),
        "Powdery Mildew": min(90, feat["white"]*180 + feat["green"]*20),
        "Leaf Spot":      min(88, feat["brown"]*140 + feat["green"]*15 + feat["std_r"]*0.3),
        "Rust":           min(88, feat["brown"]*120 + max(0, feat["mean_r"]-feat["mean_g"]-feat["mean_b"]*.5)*.4),
        "Blight":         min(85, feat["dark"]*150  + feat["brown"]*80),
        "Wilt":           min(82, max(0, 40-(abs(feat["mean_r"]-feat["mean_g"])+abs(feat["mean_g"]-feat["mean_b"])))*1.2),
    }
    total   = sum(scores.values()) or 1
    norm    = {d: round(v/total*100, 1) for d, v in scores.items()}
    disease = max(norm, key=norm.get)
    conf    = norm[disease]
    sev_idx = seed % 3
    if conf > 75 and sev_idx == 0: sev_idx = 1
    sev = "None" if _is_healthy(disease) else SEVERITIES[sev_idx]
    return disease, conf, norm, sev

def _looks_like_leaf(feat: dict) -> bool:
    if not feat:
        return False
    plant_pixels = feat["green"] + feat["yellow"] + feat["brown"]
    return plant_pixels >= 0.08 or feat["green"] >= 0.03 or feat["white"] >= 0.08

def _add_image_of_plant(crop: str) -> dict:
    return {
        "disease":    "ADD IMAGE OF PLANT",
        "healthy":    False,
        "confidence": 0,
        "crop":       crop,
        "color":      "#6b7280",
        "severity":   "Unknown",
        "treatment":  "ADD IMAGE OF PLANT",
        "probs":      {d: 0 for d in DISEASES},
        "model":      "Image validation",
    }

# ── Public predict ─────────────────────────────────────────────────────────────
def predict_disease(crop: str, image_base64: str = None) -> dict:
    # CNN model
    if _model and image_base64:
        try:
            feat = _colour_features(image_base64)
            if feat and not _looks_like_leaf(feat):
                return _add_image_of_plant(crop)
            arr = _load_image(image_base64)
            if MODEL_TYPE == "binary" or _n_output == 1:
                disease, conf, probs, sev, note = _predict_binary(arr, image_base64)
            else:
                disease, conf, probs, sev, note = _predict_multiclass(arr, image_base64)
            return _build(disease, conf, probs, sev, crop, note)
        except Exception as e:
            log.warning(f"CNN inference failed: {e}")

    # Colour fallback
    if image_base64:
        seed = _hash_img(image_base64)
        feat = _colour_features(image_base64)
        if feat:
            if not _looks_like_leaf(feat):
                return _add_image_of_plant(crop)
            disease, conf, probs, sev = _classify_colour(feat, seed)
            return _build(disease, conf, probs, sev, crop,
                          "Colour analysis · add disease_model.h5 for CNN accuracy")
        return {
            "disease":"ADD IMAGE OF PLANT","healthy":False,"confidence":0,"crop":crop,
            "color":"#6b7280","severity":"Unknown",
            "treatment":"ADD IMAGE OF PLANT",
            "probs":{d: 0 for d in DISEASES},
            "model":"Image read error",
        }

    # No image — return a sensible default drawn from known classes
    import random
    probs = {d: round(100 / len(DISEASES), 1) for d in DISEASES}
    disease = DISEASES[0] if DISEASES else "Healthy"
    severity = "None" if _is_healthy(disease) else random.choice(SEVERITIES)
    return {
        "disease": disease,
        "healthy": _is_healthy(disease),
        "confidence": round(probs.get(disease, 0), 1),
        "crop": crop,
        "color": COLORS.get(disease, _auto_color(disease)),
        "severity": severity,
        "treatment": "Please upload a leaf image to detect disease.",
        "probs": probs,
        "model": "No image provided",
    }

# ── Build result dict ──────────────────────────────────────────────────────────
def _build(disease, conf, probs, severity, crop, model_name):
    TREATMENTS = {
        "Healthy":           "No treatment needed. Continue monitoring weekly.",
        "Powdery Mildew":    "Apply sulfur-based fungicide (Kumulus DF) or neem oil.",
        "Leaf Spot":         "Apply Mancozeb (Dithane M-45) or Chlorothalonil. Remove infected leaves.",
        "Rust":              "Apply Propiconazole (Tilt 250E) or Tebuconazole. Repeat every 7-14 days.",
        "Blight":            "Apply Metalaxyl+Mancozeb (Ridomil Gold MZ). Remove infected plants immediately.",
        "Wilt":              "Drench with Carbendazim. Remove infected roots. Use Trichoderma bio-fungicide.",
        "Bacterial_spot":    "Apply copper-based bactericide. Remove infected leaves. Avoid overhead watering.",
        "Early_blight":      "Apply Chlorothalonil or Mancozeb. Remove lower infected leaves.",
        "Late_blight":       "Apply Metalaxyl+Mancozeb immediately. Remove infected plants.",
        "Leaf_Mold":         "Improve ventilation. Apply fungicide with chlorothalonil.",
        "Septoria_leaf_spot":"Apply Mancozeb or Chlorothalonil at first sign. Remove infected leaves.",
        "Spider_mites":      "Apply miticide (abamectin). Increase humidity. Remove heavily infested leaves.",
        "Target_Spot":       "Apply azoxystrobin or chlorothalonil fungicide.",
        "YellowLeaf_Curl":   "Control whitefly vectors. Remove infected plants. Use resistant varieties.",
        "mosaic_virus":      "Remove infected plants. Control aphid vectors. No chemical cure.",
    }
    # Find treatment — try exact match first, then partial match
    treatment = TREATMENTS.get(disease)
    if not treatment:
        disease_lower = disease.lower()
        for key, val in TREATMENTS.items():
            if key.lower().replace("_", " ") in disease_lower or disease_lower in key.lower():
                treatment = val
                break
    if not treatment:
        treatment = "Healthy crop — no treatment needed." if _is_healthy(disease) else \
                    f"{disease} detected. Consult a local agronomist for specific treatment."
    return {
        "disease":    disease,
        "healthy":    _is_healthy(disease),
        "confidence": round(conf, 1),
        "crop":       crop,
        "color":      COLORS.get(disease, _auto_color(disease)),
        "severity":   severity,
        "treatment":  treatment,
        "probs":      probs,
        "model":      model_name,
    }

def model_info() -> dict:
    return {
        "loaded":    _tf_loaded,
        "type":      MODEL_TYPE,
        "n_output":  _n_output,
        "classes":   DISEASES,
        "img_size":  list(IMG_SIZE),
        "threshold": THRESHOLD if MODEL_TYPE == "binary" else None,
    }
