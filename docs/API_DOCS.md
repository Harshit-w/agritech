# AgriTech v3 — API Documentation

**Base URL:** `http://localhost:5000`  
**Format:** JSON (all requests and responses)  
**Auth:** None required (v3). JWT planned for v4.  
**Weather:** Powered by [Open-Meteo](https://open-meteo.com) — free, no API key needed.

---

## Quick Reference

| # | Method | Endpoint | Description |
|---|--------|----------|-------------|
| 1 | GET | `/api/sensors` | Current 8-sensor readings |
| 2 | GET | `/api/sensors/history` | Historical time-series data |
| 3 | GET | `/api/alerts` | Live threshold-based alerts |
| 4 | GET | `/api/weather/current` | Live current weather conditions |
| 5 | POST | `/api/weather/forecast` | Multi-day weather forecast |
| 6 | GET | `/api/weather/geocode` | City name → coordinates |
| 7 | GET | `/api/irrigation` | All zone configurations |
| 8 | POST | `/api/irrigation/<zone_id>` | Update zone settings |
| 9 | POST | `/api/predict/crop` | ML crop recommendation |
| 10 | POST | `/api/predict/disease` | CNN leaf disease detection |
| 11 | POST | `/api/predict/soil` | Soil health analysis |
| 12 | POST | `/api/predict/intent` | NLP intent classification |
| 13 | GET | `/api/health` | Application health check |
| 14 | GET | `/api/status` | System operational status |

---

## Sensor Endpoints

### GET `/api/sensors`
Current readings from all 8 sensors.

**Response 200**
```json
{
  "timestamp": "2024-03-22T11:30:00.123456",
  "temperature": 14.9,
  "humidity": 74.0,
  "soil_moisture": 52.3,
  "ph_level": 6.58,
  "light_intensity": 42000,
  "nitrogen": 78,
  "phosphorus": 42,
  "potassium": 185,
  "status": "online",
  "source": "live",
  "location": "Bageshwar, Uttarakhand, India"
}
```

**Field Notes**
| Field | Unit | Source | Normal Range |
|-------|------|--------|-------------|
| `temperature` | °C | Open-Meteo live | 10–38 |
| `humidity` | % | Open-Meteo live | 40–85 |
| `soil_moisture` | % | Simulated sensor | 30–80 |
| `ph_level` | — | Simulated sensor | 5.8–7.5 |
| `light_intensity` | lux | Simulated sensor | 1000–80000 |
| `nitrogen` | mg/kg | Simulated sensor | 30–120 |
| `phosphorus` | mg/kg | Simulated sensor | 10–60 |
| `potassium` | mg/kg | Simulated sensor | 80–250 |
| `source` | — | — | `"live"` or `"simulated"` |

---

### GET `/api/sensors/history?hours=24`
Time-series sensor data at 15-minute intervals.

**Query Parameters**
| Param | Type | Default | Range |
|-------|------|---------|-------|
| `hours` | integer | 24 | 1–168 |

**Response 200**
```json
{
  "hours": 24,
  "data": [
    {
      "timestamp": "2024-03-22T10:00:00",
      "temperature": 13.2,
      "soil_moisture": 54.1,
      "humidity": 72.5,
      "ph_level": 6.51
    }
  ]
}
```

---

### GET `/api/alerts`
Threshold-based farm alerts enriched with live weather data.

**Response 200**
```json
{
  "alerts": [
    {
      "type": "ok",
      "icon": "✅",
      "title": "All Systems Normal",
      "msg": "All readings within optimal ranges · ⛅ Partly Cloudy"
    }
  ],
  "count": 1
}
```

**Alert Types:** `ok` · `warn` · `danger` · `info`

---

## Weather Endpoints

### GET `/api/weather/current?lat=&lon=&city=`
Live current atmospheric conditions from Open-Meteo.

**Query Parameters**
| Param | Default |
|-------|---------|
| `lat` | 29.500667 |
| `lon` | 79.542889 |
| `city` | Bageshwar, Uttarakhand, India |

**Response 200**
```json
{
  "temperature": 14.9,
  "humidity": 74.0,
  "feels_like": 13.2,
  "precipitation": 0.0,
  "wind_kmh": 8.5,
  "uv_index": 3.2,
  "condition": "Partly Cloudy",
  "icon": "⛅",
  "source": "Open-Meteo Live",
  "city": "Bageshwar, Uttarakhand, India"
}
```

---

### POST `/api/weather/forecast`
Multi-day forecast (real data or simulation fallback).

**Request Body**
```json
{
  "lat": 29.500667,
  "lon": 79.542889,
  "days": 7,
  "city": "Bageshwar"
}
```

**Response 200**
```json
{
  "city": "Bageshwar, Uttarakhand, India",
  "lat": 29.500667,
  "lon": 79.542889,
  "source": "Open-Meteo Live",
  "forecast": [
    {
      "day": 1,
      "date": "Mar 23",
      "date_full": "2024-03-23",
      "temp_max": 19.4,
      "temp_min": 8.1,
      "temperature": 13.8,
      "humidity": 68.5,
      "rainfall_probability": 0.12,
      "precipitation_mm": 0.0,
      "wind_kmh": 12.3,
      "uv_index": 5.8,
      "condition": "Partly Cloudy",
      "icon": "⛅",
      "source": "Open-Meteo Live"
    }
  ]
}
```

---

### GET `/api/weather/geocode?city=`
Convert city name to coordinates using Open-Meteo Geocoding API.

**Query Parameters**
| Param | Required | Example |
|-------|----------|---------|
| `city` | Yes | `Dehradun` |

**Response 200**
```json
{
  "latitude": 30.316498,
  "longitude": 78.032379,
  "city": "Dehradun, Uttarakhand, India",
  "country": "India",
  "timezone": "Asia/Kolkata"
}
```

**Response 404** — city not found  
**Response 400** — no city provided

---

## Irrigation Endpoints

### GET `/api/irrigation`
All 4 irrigation zone configurations.

**Response 200**
```json
{
  "north": {"id":"north","name":"North Field","icon":"🌾","active":true, "duration":30,"schedule":"06:00","liters":245},
  "south": {"id":"south","name":"South Field","icon":"🌿","active":false,"duration":20,"schedule":"07:30","liters":180},
  "east":  {"id":"east", "name":"East Orchard","icon":"🍎","active":true, "duration":45,"schedule":"05:30","liters":320},
  "west":  {"id":"west", "name":"West Garden","icon":"🌻","active":false,"duration":15,"schedule":"08:00","liters":95}
}
```

---

### POST `/api/irrigation/<zone_id>`
Update zone settings. `zone_id` is one of: `north` · `south` · `east` · `west`

**Request Body** (all fields optional)
```json
{
  "active": true,
  "duration": 45,
  "schedule": "06:30"
}
```

**Field Constraints**
| Field | Type | Range |
|-------|------|-------|
| `active` | boolean | — |
| `duration` | integer | 5–120 minutes |
| `schedule` | string | HH:MM format |

**Response 200** — returns updated zone object  
**Response 404** — zone not found

---

## ML Prediction Endpoints

### POST `/api/predict/crop`
Recommend the best crop based on field conditions.

**Request Body**
```json
{
  "temperature": 22.0,
  "humidity": 65.0,
  "soil_moisture": 55.0,
  "ph_level": 6.5,
  "nitrogen": 70,
  "phosphorus": 35,
  "potassium": 150
}
```

**Response 200**
```json
{
  "crop": "Tomato",
  "icon": "🍅",
  "confidence": 87.4,
  "model": "Rule-based (no model file)",
  "top5": [
    {"name":"Tomato","score":87.4,"icon":"🍅","temp":"20-30°C","ph":"6.0-6.8"},
    {"name":"Maize", "score":74.1,"icon":"🌽","temp":"18-32°C","ph":"5.8-7.0"}
  ]
}
```

**Supported Crops:** Rice · Wheat · Maize · Tomato · Potato · Cotton · Sugarcane

---

### POST `/api/predict/disease`
Detect crop leaf disease from image or crop type.

**Request Body**
```json
{
  "crop": "Tomato",
  "image": "<base64-encoded-jpg-or-png>"
}
```

`image` is optional. Without it, a weighted random result is returned for demonstration.

**Response 200**
```json
{
  "disease": "Powdery Mildew",
  "healthy": false,
  "confidence": 91.4,
  "crop": "Tomato",
  "color": "#d97706",
  "severity": "Moderate",
  "treatment": "Apply appropriate fungicide for Powdery Mildew. Consult local agronomist.",
  "probs": {
    "Healthy": 3.2,
    "Powdery Mildew": 91.4,
    "Leaf Spot": 2.8,
    "Rust": 1.1,
    "Blight": 0.9,
    "Wilt": 0.6
  },
  "model": "Weighted random (no model file)"
}
```

**Disease Classes:** Healthy · Powdery Mildew · Leaf Spot · Rust · Blight · Wilt

---

### POST `/api/predict/soil`
Analyse soil health and generate fertilizer recommendations.

**Request Body**
```json
{
  "nitrogen": 70,
  "phosphorus": 35,
  "potassium": 150,
  "ph_level": 6.5,
  "organic_matter": 2.5
}
```

**Response 200**
```json
{
  "score": 76.5,
  "status": "Good",
  "color": "#16a34a",
  "npk": "70:35:150",
  "model": "Rule-based (no model file)",
  "recs": [
    {"type": "ok", "text": "Excellent soil health — maintain current practices."}
  ],
  "breakdown": {
    "nitrogen": 17.5,
    "phosphorus": 11.7,
    "potassium": 12.0,
    "ph": 20.0,
    "organic": 5.0
  }
}
```

**Status Values:** `Good` (≥70) · `Fair` (40–70) · `Poor` (<40)

---

### POST `/api/predict/intent`
Classify a natural-language farming command into one of 6 intents.

**Request Body**
```json
{
  "text": "Start irrigation in the north field for 30 minutes",
  "language": "en"
}
```

**Field Constraints**
| Field | Required | Constraint |
|-------|----------|-----------|
| `text` | Yes | 3–500 characters |
| `language` | No | `en` `hi` `es` `fr` `de` `pt` |

**Response 200**
```json
{
  "intent": "irrigation",
  "icon": "💧",
  "confidence": 0.94,
  "language": "en",
  "action": "Routing to irrigation module",
  "model": "Keyword matching"
}
```

**Intent Classes:** `irrigation` · `crop` · `disease` · `weather` · `soil` · `general`

---

## System Endpoints

### GET `/api/health`
Liveness probe — used by Docker health checks and load balancers.

**Response 200**
```json
{
  "status": "healthy",
  "app": "AgriTech v3",
  "timestamp": "2024-03-22T11:30:00.123456"
}
```

---

### GET `/api/status`
Full operational status report.

**Response 200**
```json
{
  "status": "operational",
  "version": "3.0.0",
  "uptime": "0:12:34",
  "sensors_online": 8,
  "irrigation_zones": 4,
  "ml_models": 5,
  "weather_source": "Open-Meteo (free, no key)",
  "timestamp": "2024-03-22T11:30:00"
}
```

---

## Error Responses

All errors follow a consistent shape:
```json
{ "error": "Human-readable description" }
```

| Code | Meaning |
|------|---------|
| 400 | Bad request — invalid or missing input |
| 404 | Endpoint or resource not found |
| 503 | External service (weather API) unavailable |

---

## Code Examples

### Python
```python
import requests

BASE = "http://localhost:5000"

# Live sensor readings
sensors = requests.get(f"{BASE}/api/sensors").json()
print(f"Temperature: {sensors['temperature']}°C  Source: {sensors['source']}")

# Crop recommendation
result = requests.post(f"{BASE}/api/predict/crop", json={
    "temperature": 22, "humidity": 65, "soil_moisture": 55,
    "ph_level": 6.5, "nitrogen": 70, "phosphorus": 35, "potassium": 150
}).json()
print(f"Recommended: {result['crop']} ({result['confidence']}%)")

# Weather forecast
fc = requests.post(f"{BASE}/api/weather/forecast", json={
    "lat": 29.5, "lon": 79.5, "days": 7, "city": "Bageshwar"
}).json()
for day in fc["forecast"][:3]:
    print(f"{day['date']}: {day['temp_max']}/{day['temp_min']}°C  {day['icon']} {day['condition']}")
```

### JavaScript (fetch)
```javascript
const BASE = 'http://localhost:5000';

// Sensors
const s = await fetch(`${BASE}/api/sensors`).then(r => r.json());
console.log(`Temp: ${s.temperature}°C  Source: ${s.source}`);

// Soil analysis
const soil = await fetch(`${BASE}/api/predict/soil`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ nitrogen: 70, phosphorus: 35, potassium: 150, ph_level: 6.5, organic_matter: 2.5 })
}).then(r => r.json());
console.log(`Soil health: ${soil.score} (${soil.status})`);
```

### cURL
```bash
# Health check
curl http://localhost:5000/api/health

# Live sensors
curl http://localhost:5000/api/sensors

# Geocode a city
curl "http://localhost:5000/api/weather/geocode?city=Dehradun"

# Crop recommendation
curl -X POST http://localhost:5000/api/predict/crop \
  -H "Content-Type: application/json" \
  -d '{"temperature":22,"humidity":65,"soil_moisture":55,"ph_level":6.5,"nitrogen":70,"phosphorus":35,"potassium":150}'

# Toggle irrigation zone
curl -X POST http://localhost:5000/api/irrigation/north \
  -H "Content-Type: application/json" \
  -d '{"active": true, "duration": 45}'
```
