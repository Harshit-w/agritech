# 🌱 AgriTech v3 — AI-Powered Smart Farming Platform

Real-time farm monitoring with live weather data, ML crop recommendations, disease detection, soil analysis, and irrigation control.

---

## Quick Start

```bash
# 1. Open a terminal in the agritech_final folder
# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python app.py

# 5. Open browser
# http://127.0.0.1:5000
```

---

## Project Structure

```
agritech_final/
├── app.py                    ← Flask app entry point
├── config.py                 ← All configuration settings
├── requirements.txt          ← Core dependencies (Flask only)
├── requirements-ml.txt       ← Optional ML packages
├── Dockerfile                ← Container definition
├── docker-compose.yml        ← Multi-service setup
├── .env.example              ← Copy to .env for production
│
├── api/                      ← API blueprints (one per feature)
│   ├── sensors.py            ← GET /api/sensors, /api/alerts
│   ├── weather.py            ← GET/POST /api/weather/*
│   ├── irrigation.py         ← GET/POST /api/irrigation/*
│   ├── predict.py            ← POST /api/predict/*
│   ├── system.py             ← GET /api/health, /api/status
│   └── routes.py             ← Registers all blueprints
│
├── services/                 ← Business logic layer
│   ├── weather.py            ← Open-Meteo API integration
│   ├── sensors.py            ← Sensor readings + alerts
│   └── irrigation.py        ← Zone state management
│
├── ml_service/               ← ML model wrappers
│   ├── crop.py               ← Crop recommendation
│   ├── disease.py            ← Disease detection
│   ├── soil.py               ← Soil health analysis
│   └── intent.py             ← NLP intent classification
│
├── templates/
│   └── index.html            ← Single-page app shell
│
├── static/
│   ├── css/style.css         ← Complete stylesheet
│   └── js/main.js            ← All frontend JavaScript
│
├── models/                   ← Put .pkl and .h5 files here
├── logs/                     ← App logs written here
├── uploads/                  ← Image uploads stored here
└── tests/
    └── test_all.py           ← Full test suite
```

---

## API Endpoints

| Method | Endpoint                         | Description               |
| ------ | -------------------------------- | ------------------------- |
| GET    | `/api/sensors`                   | Live sensor readings      |
| GET    | `/api/sensors/history?hours=24`  | Time-series history       |
| GET    | `/api/alerts`                    | Threshold-based alerts    |
| GET    | `/api/weather/current?lat=&lon=` | Live current weather      |
| POST   | `/api/weather/forecast`          | Multi-day forecast        |
| GET    | `/api/weather/geocode?city=`     | City name → coordinates   |
| GET    | `/api/irrigation`                | All zone configs          |
| POST   | `/api/irrigation/<zone_id>`      | Update zone settings      |
| POST   | `/api/predict/crop`              | Crop recommendation       |
| POST   | `/api/predict/disease`           | Disease detection         |
| POST   | `/api/predict/soil`              | Soil health analysis      |
| POST   | `/api/predict/intent`            | NLP intent classification |
| GET    | `/api/health`                    | Health check              |
| GET    | `/api/status`                    | System status             |

---

## Weather API

Powered by **Open-Meteo** — completely free, no API key required.

Default location: **Bageshwar, Uttarakhand, India** (29.5007°N, 79.5429°E)

Change location in the Weather tab by searching a city name or entering coordinates.

---

## Adding Real ML Models

Drop trained model files into the `models/` folder:

| File                | Model        | Used by                |
| ------------------- | ------------ | ---------------------- |
| `crop_model.pkl`    | RandomForest | `/api/predict/crop`    |
| `le_crop.pkl`       | LabelEncoder | `/api/predict/crop`    |
| `disease_model.h5`  | ResNet50 CNN | `/api/predict/disease` |
| `soil_analysis.pkl` | Regression   | `/api/predict/soil`    |
| `intent_model.pkl`  | SVM pipeline | `/api/predict/intent`  |

Without model files, all endpoints use intelligent rule-based fallbacks — the app is fully functional either way.

---

## Running Tests

```bash
pip install pytest
pytest tests/test_all.py -v
```

---

## Docker

```bash
docker-compose up -d
# Visit http://localhost:5000
```

---

## Deployment (Docker)

Build the production image locally:

```bash
docker build -t agritech:latest .
```

Run the container (binds to port 5000):

```bash
# development/local
docker run --rm -p 5000:5000 \
    -e FLASK_DEBUG=0 \
    -e DEFAULT_LAT=29.500667 \
    -e DEFAULT_LON=79.542889 \
    -e DEFAULT_CITY="Bageshwar, Uttarakhand, India" \
    agritech:latest
```

Use `docker-compose` for local multi-volume setup (volumes keep models, logs, uploads):

```bash
docker-compose up --build -d
```

Push the image to a registry (example: Docker Hub):

```bash
# Tag then push
docker tag agritech:latest youruser/agritech:latest
docker push youruser/agritech:latest
```

Notes:

- Copy `.env.example` to `.env` and set `SECRET_KEY` and any API keys before deploying.
- The Dockerfile exposes `5000` and uses `gunicorn` as the production server.
- The container exposes a healthcheck on `/api/health` used by orchestrators.

---

## Keyboard Shortcuts

| Key   | Action          |
| ----- | --------------- |
| `1–8` | Switch tabs     |
| `R`   | Refresh sensors |
| `E`   | Export CSV      |
| `?`   | Show help       |
