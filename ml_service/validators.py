"""ml_service/validators.py — Request validators for all API endpoints."""

try:
    from pydantic import BaseModel, Field, field_validator
    HAS_PYDANTIC = True
except ImportError:
    class BaseModel:
        def __init__(self, **kw):
            for k, v in kw.items(): setattr(self, k, v)
    def Field(default=None, **kw): return default
    def field_validator(*a, **kw):
        def d(fn): return fn
        return d
    HAS_PYDANTIC = False

from typing import Optional

VALID_CROPS = {"Rice", "Wheat", "Tomato", "Potato", "Maize", "Cotton", "Sugarcane"}
VALID_LANGS = {"en", "hi", "es", "fr", "de", "pt"}


class CropRequest(BaseModel):
    temperature:   float = Field(default=22.0,  ge=-10, le=60)
    humidity:      float = Field(default=65.0,  ge=0,   le=100)
    soil_moisture: float = Field(default=55.0,  ge=0,   le=100)
    ph_level:      float = Field(default=6.5,   ge=0,   le=14)
    nitrogen:      float = Field(default=70.0,  ge=0,   le=300)
    phosphorus:    float = Field(default=35.0,  ge=0,   le=150)
    potassium:     float = Field(default=150.0, ge=0,   le=500)


class DiseaseRequest(BaseModel):
    crop:  str           = Field(default="Tomato")
    image: Optional[str] = Field(default=None)

    @field_validator("crop")
    @classmethod
    def crop_valid(cls, v):
        if v not in VALID_CROPS:
            raise ValueError(f"crop must be one of: {', '.join(sorted(VALID_CROPS))}")
        return v


class SoilRequest(BaseModel):
    nitrogen:       float = Field(default=70.0,  ge=0, le=300)
    phosphorus:     float = Field(default=35.0,  ge=0, le=150)
    potassium:      float = Field(default=150.0, ge=0, le=500)
    ph_level:       float = Field(default=6.5,   ge=0, le=14)
    organic_matter: float = Field(default=2.5,   ge=0, le=100)


class WeatherRequest(BaseModel):
    lat:  float = Field(default=30.2139,  ge=-90,  le=90)
    lon:  float = Field(default=78.1740,  ge=-180, le=180)
    days: int   = Field(default=7,         ge=1,    le=16)
    city: str   = Field(default="Dehradun, Uttarakhand, India")


class IntentRequest(BaseModel):
    text:     str = Field(..., min_length=3, max_length=500)
    language: str = Field(default="en")

    @field_validator("language")
    @classmethod
    def lang_valid(cls, v):
        return v if v in VALID_LANGS else "en"


class IrrigationUpdate(BaseModel):
    active:   Optional[bool] = None
    duration: Optional[int]  = Field(default=None, ge=5, le=120)
    schedule: Optional[str]  = None


def validate(model_class, data: dict):
    # Pre-coerce common numeric string values and normalize language
    d = dict(data or {})
    # Normalize language early so model validators receive a sane value
    if "language" in d and isinstance(d["language"], str):
        if d["language"] not in VALID_LANGS:
            d["language"] = "en"

    # Coerce numeric strings to numbers for common fields
    for k, v in list(d.items()):
        if isinstance(v, str):
            # try int first, then float
            try:
                if v.isdigit():
                    d[k] = int(v)
                else:
                    d[k] = float(v)
            except Exception:
                # leave as-is if not numeric
                pass

    try:
        obj = model_class(**d)
        return obj, None
    except Exception as e:
        return None, {"error": "Validation failed", "detail": str(e)}
