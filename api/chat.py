"""
api/chat.py
AI Farming Assistant — Hybrid Dual-Model API
- Groq Llama 3.3 for text chat (fast, cost-effective)
- Google Gemini for image analysis (multimodal capabilities)
"""

import os
import json
import time
import threading
import logging
import requests
import base64
import audioop
import wave
from pathlib import Path
from io import BytesIO
from flask import Blueprint, jsonify, request, Response, stream_with_context
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)
bp  = Blueprint("chat", __name__)

# ── Groq Config (Text Chat) ────────────────────────────────────────────────────
GROQ_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# ── Gemini Config (Image Analysis) ─────────────────────────────────────────────
GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

try:
    import google.generativeai as genai
    from PIL import Image
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    log.warning("google-generativeai or PIL not installed. Image analysis disabled.")

# ── Vosk config (voice command transcription) ─────────────────────────────────
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15")
VOSK_SAMPLE_RATE = 16000
_vosk_model = None
_vosk_lock = threading.Lock()

try:
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    KaldiRecognizer = None
    Model = None
    log.warning("vosk not installed. Voice command transcription disabled.")


def _get_vosk_model() -> tuple[object | None, str | None]:
    """Lazily load Vosk model once per process."""
    global _vosk_model
    if not VOSK_AVAILABLE:
        return None, "Vosk package is not installed"

    with _vosk_lock:
        if _vosk_model is not None:
            return _vosk_model, None

        model_path = Path(VOSK_MODEL_PATH)
        if not model_path.exists():
            return None, f"Vosk model not found at {model_path}"

        try:
            _vosk_model = Model(str(model_path))
            log.info(f"Loaded Vosk model from {model_path}")
            return _vosk_model, None
        except Exception as e:
            log.error(f"Vosk model load failed: {e}")
            return None, str(e)


# ── Request throttle — Groq is generous, 1 request per 1 second is safe ────────
_last_request_time = 0.0
_request_lock      = threading.Lock()
MIN_REQUEST_GAP    = 1.0   # seconds between requests

def _wait_for_slot():
    """Block until it's safe to make a request without hitting rate limit."""
    global _last_request_time
    with _request_lock:
        now     = time.time()
        elapsed = now - _last_request_time
        if elapsed < MIN_REQUEST_GAP:
            wait = MIN_REQUEST_GAP - elapsed
            time.sleep(wait)
        _last_request_time = time.time()

# ── Retry with backoff ─────────────────────────────────────────────────────────
def _call_with_retry(make_request_fn, max_retries=3):
    """
    Call Groq API with automatic retry on rate limit or timeout.
    Waits progressively longer on retries.
    """
    for attempt in range(max_retries):
        try:
            _wait_for_slot()
            return make_request_fn(), None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = 2 + (attempt * 2)  # 2s, 4s, 6s
                    log.warning(f"Groq 429 on attempt {attempt+1}, waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
                return None, {"code": 429, "message": str(e)}
            return None, {"code": e.response.status_code, "message": e.response.text[:300]}
        except requests.exceptions.Timeout:
            return None, {"code": 504, "message": "Request timeout"}
        except requests.exceptions.RequestException as e:
            return None, {"code": 0, "message": str(e)}
        except Exception as e:
            return None, {"code": -1, "message": str(e)}
    return None, {"code": 429, "message": "Max retries exceeded"}

SYSTEM_PROMPT = """You are AgriBot, an expert AI farming assistant for Indian farmers.

You have deep knowledge of:
- Crop diseases, symptoms, and treatments (fungicides, pesticides, bio-agents)
- Soil health, NPK fertilizers, dosage, and timing
- Irrigation scheduling and water management
- Weather impact on crops and farming decisions
- Pest management and integrated pest control (IPM)
- Crop varieties suited to different Indian regions and climates
- Organic and sustainable farming practices
- Government schemes and subsidies for Indian farmers

Location context: Dehradun, Uttarakhand, India (hill farming, moderate climate, diverse crops)

When analysing a leaf image:
1. Identify the crop type if visible
2. Describe symptoms clearly (colour, pattern, location on leaf)
3. Give the most likely disease with confidence level
4. Provide specific treatment recommendations with product names
5. Suggest preventive measures

Response style:
- Be practical, specific, and concise
- Use bullet points for lists
- Include product names and dosages when recommending treatments
- Always add safety precautions for chemicals
- If unsure, say so clearly and recommend consulting a local agronomist or KVK"""


def _build_messages(messages: list) -> list:
    """Convert message format to OpenAI-compatible format."""
    result = []
    for m in messages:
        role = "user" if m["role"] == "user" else "assistant"
        content = m.get("content", "")
        
        # If content is a list (image + text), join or handle specially
        if isinstance(content, list):
            text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
            content = " ".join(text_parts) if text_parts else str(content)
        
        result.append({"role": role, "content": str(content)})
    return result


def _get_location_context(city: str = None, latitude: float = None, longitude: float = None) -> str:
    """Generate location-specific context for AgriBot."""
    
    # Map of famous agricultural cities to their characteristics
    location_traits = {
        "almora": "Almora, Uttarakhand (high-altitude hill station, cool climate 1600m+, traditional farming, apples, walnuts, cereals)",
        "bageshwar": "Bageshwar, Uttarakhand (hill farming, cool climate, altitude ~1000m, cereals, pulses, seasonal crops)",
        "dehradun": "Dehradun, Uttarakhand (moderate hill climate, diverse crops, floriculture, vegetables, cereals)",
        "nainital": "Nainital, Uttarakhand (high-altitude hill station, cool climate, dairy farming, fruit crops)",
        "ranikhet": "Ranikhet, Uttarakhand (hill farming, cool climate, apples, stone fruits, cereals)",
        "pithoragarh": "Pithoragarh, Uttarakhand (mountain farming, cold winters, vegetables, pulses)",
        "rudraprayag": "Rudraprayag, Uttarakhand (hill farming, moderate climate, seasonal crops)",
        "pauri": "Pauri, Uttarakhand (hill farming, cereals, pulses, spices)",
        "kanpur": "Kanpur, Uttar Pradesh (plains, wheat-rice belt, sugarcane, intensive farming)",
        "lucknow": "Lucknow, Uttar Pradesh (plains, diverse crops, wheat, rice, pulses)",
        "delhi": "Delhi/NCR (plains, market-driven farming, vegetables, dairy)",
        "chandigarh": "Chandigarh, Punjab (plains, wheat-rice rotation, Punjab's agricultural hub)",
        "amritsar": "Amritsar, Punjab (wheat belt, rice in monsoon, traditional farming)",
        "jaipur": "Jaipur, Rajasthan (arid/semi-arid, mustard, pulses, millets, horticulture)",
        "jodhpur": "Jodhpur, Rajasthan (desert farming, mustard, chickpea, pearl millet)",
        "agra": "Agra, Uttar Pradesh (plains, wheat-rice, vegetables, floriculture)",
        "indore": "Indore, Madhya Pradesh (central India, soybean, wheat, pulses)",
        "bhopal": "Bhopal, Madhya Pradesh (central India, wheat, chickpea, soybean)",
        "nagpur": "Nagpur, Maharashtra (Vidarbha region, cotton, soybean, oranges)",
        "pune": "Pune, Maharashtra (sugar belt, sugarcane, jowar, pulses)",
        "bangalore": "Bangalore, Karnataka (coffee belt, arecanut, coconut, horticulture)",
        "mysore": "Mysore, Karnataka (coffee, spices, coconut, horticulture)",
        "kochi": "Kochi, Kerala (spice hub, coconut, pepper, cardamom, areca)",
        "thrissur": "Thrissur, Kerala (spice crops, coconut, spices, horticulture)",
        "madurai": "Madurai, Tamil Nadu (south india, rice, cotton, sugarcane)",
        "coimbatore": "Coimbatore, Tamil Nadu (textile city, cotton, coconut, spices)",
        "hyderabad": "Hyderabad, Telangana (rice belt, cotton, jowar, tobacco)",
        "vijayawada": "Vijayawada, Andhra Pradesh (rice plains, sugarcane, coconut)",
        "patna": "Patna, Bihar (rice belt, wheat, maize, vegetables)",
        "guwahati": "Guwahati, Assam (tea gardens, rice, jute, diverse crops)",
        "srinagar": "Srinagar, Kashmir (high altitude, apples, walnuts, saffron, cold crops)",
        "manali": "Manali, Himachal Pradesh (hill farming, apples, stone fruits, vegetables)",
        "shimla": "Shimla, Himachal Pradesh (hill station, apples, walnuts, potatoes)",
    }
    
    # Try to match city name
    context = None
    if city:
        city_lower = city.lower().strip()
        for key, val in location_traits.items():
            if key in city_lower:
                context = val
                break
    
    # Fallback to generic context if no match
    if not context:
        context = f"{city or 'Unknown location'}, India (regional farming context)"
    
    prompt = f"""You are AgriBot, an expert AI farming assistant for Indian farmers.

You have deep knowledge of:
- Crop diseases, symptoms, and treatments (fungicides, pesticides, bio-agents)
- Soil health, NPK fertilizers, dosage, and timing
- Irrigation scheduling and water management
- Weather impact on crops and farming decisions
- Pest management and integrated pest control (IPM)
- Crop varieties suited to different Indian regions and climates
- Organic and sustainable farming practices
- Government schemes and subsidies for Indian farmers

**Current Location Context: {context}**
Provide recommendations specific to this region's climate, soil, water availability, and traditional crops.

When analysing a leaf image:
1. Identify the crop type if visible
2. Describe symptoms clearly (colour, pattern, location on leaf)
3. Give the most likely disease with confidence level
4. Provide specific treatment recommendations with product names
5. Suggest preventive measures

Response style:
- Be practical, specific, and concise
- Use bullet points for lists
- Include product names and dosages when recommending treatments
- Always add safety precautions for chemicals
- If unsure, say so clearly and recommend consulting a local agronomist or KVK
- Consider local climate, soil type, and typical crops of this region"""
    
    return prompt
@bp.route("/chat/stream", methods=["POST"])
def chat_stream():
    if not GROQ_KEY:
        return jsonify({"error": "set up Groq"}), 500

    data     = request.get_json() or {}
    messages = data.get("messages", [])
    location = data.get("location", {})
    
    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    # Get location-specific system prompt
    city = location.get("city") if location else None
    lat = location.get("latitude") if location else None
    lon = location.get("longitude") if location else None
    system_prompt = _get_location_context(city, lat, lon)

    # Keep last 6 messages — enough context without wasting tokens
    messages = messages[-6:]

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model":       GROQ_MODEL,
        "messages":    [{"role": "system", "content": system_prompt}] + _build_messages(messages),
        "max_tokens":  800,
        "temperature": 0.7,
        "stream":      True,
    }

    def generate():
        try:
            _wait_for_slot()
            
            resp = requests.post(
                f"{GROQ_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                stream=True,
                timeout=60,
            )
            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                if line_str.startswith("data:"):
                    json_str = line_str[5:].strip()
                    if json_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(json_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield f"data: {json.dumps({'text': content})}\n\n"
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                msg = "⏳ Groq API rate limit reached. Please wait a moment and try again."
            elif e.response.status_code == 401:
                msg = "❌ Invalid Groq API key. Check your GROQ_API_KEY in .env"
            else:
                msg = f"❌ API error ({e.response.status_code}). Please try again."
            log.warning(f"Groq stream {e.response.status_code}: {e.response.text[:200]}")
            yield f"data: {json.dumps({'error': msg})}\n\n"

        except Exception as e:
            log.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': '❌ Connection error. Check internet and try again.'})}\n\n"

        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype = "text/event-stream",
        headers  = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Image analysis (Gemini) ───────────────────────────────────────────────────
@bp.route("/chat/analyse-image", methods=["POST"])
def analyse_image():
    """
    Image analysis endpoint using Google Gemini (vision model).
    Uses Gemini for image analysis since Groq doesn't support images.
    """
    if not GEMINI_AVAILABLE:
        return jsonify({"error": "Gemini library not installed. Run: pip install google-generativeai pillow"}), 500
    
    if not GEMINI_KEY:
        return jsonify({"error": "GEMINI_API_KEY not set in .env"}), 500

    data      = request.get_json() or {}
    image_b64 = data.get("image")
    crop      = data.get("crop", "unknown crop")

    if not image_b64:
        return jsonify({"error": "No image provided"}), 400

    try:
        # Configure Gemini
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)

        # Decode base64 image to PIL Image
        image_data = base64.b64decode(image_b64)
        image = Image.open(BytesIO(image_data))

        # Create analysis prompt
        analysis_prompt = (
            f"You are an expert agricultural plant disease diagnostic AI.\n"
            f"Crop type: {crop}\n\n"
            f"Analyse this leaf image for plant disease. Provide:\n"
            f"1. **Disease identified** (or 'Healthy')\n"
            f"2. **Confidence** (High/Medium/Low)\n"
            f"3. **Symptoms observed** - describe what you see\n"
            f"4. **Treatment** - specific products + dosage\n"
            f"5. **Prevention tips** for the future\n\n"
            f"Include both chemical and organic options.\n"
            f"Always add safety precautions for chemicals."
        )

        # Send to Gemini - pass PIL Image directly
        response = model.generate_content([analysis_prompt, image])

        reply = response.text if response.text else "Could not analyse image. Please try again."
        
        return jsonify({
            "reply": reply,
            "type": "image_analysis",
            "crop": crop
        })

    except Exception as e:
        log.error(f"Gemini image analysis error: {e}")
        error_msg = str(e)
        
        if "API" in error_msg or "key" in error_msg.lower():
            return jsonify({"error": "Invalid Gemini API key. Check .env"}), 401
        elif "quota" in error_msg.lower() or "429" in error_msg:
            return jsonify({"error": "Gemini API quota exceeded. Please try again later."}), 429
        else:
            return jsonify({"error": f"Image analysis failed. Check logs."}), 500


@bp.route("/chat/transcribe", methods=["POST"])
def transcribe_audio():
    """Transcribe WAV audio with Vosk for Assistant voice commands."""
    data = request.get_json() or {}
    audio_b64 = data.get("audio", "")

    if not audio_b64:
        return jsonify({"error": "No audio provided"}), 400

    model, err = _get_vosk_model()
    if err:
        return jsonify({
            "error": "voice_unavailable",
            "message": (
                "Vosk voice transcription unavailable. Install vosk and download "
                f"a model to {VOSK_MODEL_PATH}. Detail: {err}"
            ),
        }), 503

    try:
        # Accept plain base64 and data URL formats.
        if "," in audio_b64:
            audio_b64 = audio_b64.split(",", 1)[1]
        raw_audio = base64.b64decode(audio_b64)

        with wave.open(BytesIO(raw_audio), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            pcm = wf.readframes(wf.getnframes())

        if sampwidth != 2:
            pcm = audioop.lin2lin(pcm, sampwidth, 2)

        if n_channels > 1:
            pcm = audioop.tomono(pcm, 2, 0.5, 0.5)

        if framerate != VOSK_SAMPLE_RATE:
            pcm, _ = audioop.ratecv(pcm, 2, 1, framerate, VOSK_SAMPLE_RATE, None)

        rec = KaldiRecognizer(model, VOSK_SAMPLE_RATE)
        words = []
        chunk = 4000

        for i in range(0, len(pcm), chunk):
            piece = pcm[i : i + chunk]
            if rec.AcceptWaveform(piece):
                r = json.loads(rec.Result())
                t = (r.get("text") or "").strip()
                if t:
                    words.append(t)

        final_result = json.loads(rec.FinalResult())
        final_text = (final_result.get("text") or "").strip()
        if final_text:
            words.append(final_text)

        text = " ".join(words).strip()
        if not text:
            return jsonify({"text": "", "message": "No speech recognized"})

        return jsonify({"text": text})

    except wave.Error:
        return jsonify({"error": "Invalid WAV audio payload"}), 400
    except Exception as e:
        log.error(f"Vosk transcription failed: {e}")
        return jsonify({"error": "Transcription failed"}), 500


# ── Non-streaming fallback ─────────────────────────────────────────────────────
@bp.route("/chat", methods=["POST"])
def chat():
    if not GROQ_KEY:
        return jsonify({"error": "GROQ_API_KEY not set in .env"}), 500

    data     = request.get_json() or {}
    messages = data.get("messages", [])[-6:]
    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model":       GROQ_MODEL,
        "messages":    [{"role": "system", "content": SYSTEM_PROMPT}] + _build_messages(messages),
        "max_tokens":  800,
        "temperature": 0.7,
    }

    def do_request():
        _wait_for_slot()
        resp = requests.post(
            f"{GROQ_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    result, err = _call_with_retry(do_request)

    if err:
        if err["code"] == 429:
            return jsonify({"error": "rate_limit",
                            "message": "Rate limit reached. Please wait a moment."}), 429
        elif err["code"] == 401:
            return jsonify({"error": "auth_error",
                            "message": "Invalid Groq API key."}), 401
        return jsonify({"error": "api_error",
                        "message": f"API error ({err['code']}). Please try again."}), 502

    try:
        reply = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        return jsonify({
            "reply":         reply or "No response. Please try again.",
            "input_tokens":  usage.get("prompt_tokens",     0),
            "output_tokens": usage.get("completion_tokens", 0),
        })
    except (KeyError, IndexError, TypeError) as e:
        log.error(f"Response parsing error: {e}")
        return jsonify({"error": "api_error",
                        "message": "Could not parse API response."}), 502
