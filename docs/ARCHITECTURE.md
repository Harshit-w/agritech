# AgriTech v3 — Architecture Guide

## System Overview

```
Browser (Chrome/Edge)
        │  HTTP/JSON  (REST)
        │  Polls sensors every 5s, alerts every 10s, weather every 5min
        ▼
┌──────────────────────────────────────────────────────────────┐
│                     Flask Application                        │
│  app.py — factory pattern, blueprints, global headers        │
│  wsgi.py — Gunicorn entry point for production               │
│  config.py — all settings, env-var overrides                 │
├──────────┬──────────────┬──────────────┬─────────────────────┤
│ api/     │              │              │                      │
│ sensors  │  api/weather │ api/irrigat. │  api/predict         │
│ .py      │  .py         │ .py          │  .py                 │
├──────────┴──────────────┴──────────────┴─────────────────────┤
│                    services/  (business logic)               │
│  sensors.py — readings + alert generation                    │
│  weather.py — Open-Meteo API + 5-min cache                   │
│  irrigation.py — zone state (in-memory / DB)                 │
├─────────────────────────────────────────────────────────────┤
│               ml_service/  (ML model wrappers)              │
│  model_manager.py — singleton, thread-safe, hot-reload      │
│  crop.py · disease.py · soil.py · intent.py                 │
│  validators.py — Pydantic request validation                 │
├─────────────────────────────────────────────────────────────┤
│                    models/  (binary files)                  │
│  crop_model.pkl · disease_model.h5 · soil_analysis.pkl      │
│  intent_model.pkl · vectorizer.pkl · le_crop.pkl            │
└─────────────────────────────────────────────────────────────┘
        │
        ▼ HTTP (urllib, no extra dependencies)
Open-Meteo API  (free, no API key)
  api.open-meteo.com/v1/forecast
  geocoding-api.open-meteo.com/v1/search
```

---

## Directory Structure

```
agritech_final/
├── app.py                    ← Flask app factory
├── wsgi.py                   ← Gunicorn entry point
├── config.py                 ← Centralised settings
├── requirements.txt          ← Flask only (3 packages)
├── requirements-ml.txt       ← Optional ML packages
├── Dockerfile                ← Python 3.11-slim container
├── docker-compose.yml        ← App + Redis orchestration
├── .env.example              ← Environment variable template
├── .gitignore
├── .dockerignore
│
├── api/                      ← Flask Blueprints (thin controllers)
│   ├── __init__.py
│   ├── routes.py             ← Blueprint registration
│   ├── sensors.py            ← /api/sensors, /api/alerts
│   ├── weather.py            ← /api/weather/*
│   ├── irrigation.py         ← /api/irrigation/*
│   ├── predict.py            ← /api/predict/*
│   └── system.py             ← /api/health, /api/status
│
├── services/                 ← Business logic
│   ├── __init__.py
│   ├── weather.py            ← Open-Meteo integration, caching
│   ├── sensors.py            ← Sensor data, alert generation
│   └── irrigation.py        ← Zone state management
│
├── ml_service/               ← ML layer
│   ├── __init__.py
│   ├── model_manager.py      ← Thread-safe singleton loader
│   ├── validators.py         ← Pydantic input validation
│   ├── crop.py               ← Crop prediction (RF + rule fallback)
│   ├── disease.py            ← Disease detection (CNN + random fallback)
│   ├── soil.py               ← Soil scoring (regression + rule fallback)
│   └── intent.py             ← NLP intent (SVM + keyword fallback)
│
├── templates/
│   └── index.html            ← HTML app shell (8-tab SPA)
│
├── static/
│   ├── css/style.css         ← Complete stylesheet (light, earth tones)
│   └── js/main.js            ← All frontend JavaScript (no frameworks)
│
├── models/                   ← Drop .pkl / .h5 files here
├── logs/                     ← app.log written here
├── uploads/                  ← Leaf images stored here
│
├── tests/
│   └── test_all.py           ← 40+ unit and integration tests
│
└── docs/
    ├── API_DOCS.md
    ├── ARCHITECTURE.md       ← This file
    ├── MODELS_GUIDE.md
    ├── DEPLOYMENT_GUIDE.md
    └── CONTRIBUTING.md
```

---

## Request Lifecycle

### Sensor Poll (every 5 seconds)
```
Browser setInterval(5000)
  → GET /api/sensors
  → api/sensors.py :: sensors()
  → services/sensors.py :: get_sensor_readings()
      → services/weather.py :: get_live_weather()   # uses 5-min cache
          → Open-Meteo API  (if cache stale)
      → random values for soil/NPK sensors
  → JSON response { temperature, humidity, ... }
  → static/js/main.js :: pollSensors()
      → updateDash(data)        # stat cards, NPK bars
      → updateSensorGrid(data)  # sensor card grid
      → addToLog(data)          # analytics data log
```

### Crop Prediction
```
User clicks "Recommend Crop"
  → POST /api/predict/crop  { temperature, humidity, ... }
  → api/predict.py :: crop()
  → ml_service/crop.py :: predict_crop()
      → ModelManager.instance().get("crop")   # real model if loaded
          → model.predict(features)           # RandomForest inference
      → OR rule-based scoring                 # if no model file
  → JSON { crop, confidence, top5, model }
  → main.js :: doCrop()  → renders result card
```

### Weather Forecast (with city search)
```
User types city name → clicks Find
  → GET /api/weather/geocode?city=Dehradun
  → services/weather.py :: geocode_city()
  → geocoding-api.open-meteo.com
  → lat/lon filled into form

User clicks Get Forecast
  → POST /api/weather/forecast  { lat, lon, days }
  → api/weather.py :: forecast()
  → services/weather.py :: get_forecast()
  → api.open-meteo.com/v1/forecast  (daily data)
  → JSON { city, forecast: [...7 days...] }
  → main.js :: loadForecast()  → renders table + chart
```

---

## ML Model Architecture

### Crop Predictor (`crop_model.pkl`)
```
Input:  [temp, humidity, moisture, pH, N, P, K]  — 7 features
Model:  RandomForestClassifier (n_estimators=100)
Output: class label + predict_proba() for 7 crops
Fallback: weighted rule-based scoring per crop requirements
```

### Disease Detector (`disease_model.h5`)
```
Input:  224×224×3 RGB image  (normalized 0–1)
Model:  ResNet50 (ImageNet pretrained) + custom head
        GlobalAvgPool → Dense(128, relu) → Dropout(0.3) → Dense(6, softmax)
Output: probability for 6 disease classes
Fallback: weighted random (Healthy=45% weight)
```

### Soil Analyzer (`soil_analysis.pkl`)
```
Input:  [N, P, K, pH, organic_matter]  — 5 features
Model:  Ridge Regression (sklearn Pipeline with StandardScaler)
Output: health_score (0–100)  +  rule-based recommendations
Fallback: formula-based score (same as model logic)
```

### Intent Classifier (`intent_model.pkl`)
```
Input:  raw text string
Model:  sklearn Pipeline:
          TfidfVectorizer(ngram_range=(1,2), max_features=5000)
          → LinearSVC(C=1.0)
Output: intent class + decision_function score
Fallback: keyword matching across 6 intent dictionaries
```

---

## Data Flow: Real vs Simulated

| Sensor | Production | Current |
|--------|-----------|---------|
| Temperature | IoT hardware (DHT22) | Open-Meteo live API |
| Humidity | IoT hardware (DHT22) | Open-Meteo live API |
| Soil Moisture | IoT hardware (capacitive) | Simulated (sinusoidal) |
| pH Level | IoT hardware (analog sensor) | Simulated (random walk) |
| Light | IoT hardware (LDR/BH1750) | Simulated (random) |
| N, P, K | IoT hardware (NPK sensor) | Simulated (random) |

Weather API updates every **5 minutes** (TTL cache).  
Sensor poll every **5 seconds**.  
Alert poll every **10 seconds**.

---

## Scalability Path

| Concern | Current | Production Path |
|---------|---------|----------------|
| Weather caching | In-process dict | Redis |
| Irrigation state | In-memory | PostgreSQL |
| Sensor history | Generated on-request | InfluxDB / TimescaleDB |
| ML inference | In-process | Triton Inference Server |
| Image uploads | Local filesystem | S3 / Cloud Storage |
| Workers | 1 (dev) / 4 (Gunicorn) | ECS horizontal scaling |
