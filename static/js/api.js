"use strict";
/**
 * static/js/api.js
 * Centralized API client for AgriTech v3.
 * All fetch calls go through this module for consistent error handling.
 */

const AgriAPI = (() => {
  // ── Base fetch ─────────────────────────────────────────────────────────────
  async function request(path, options = {}) {
    try {
      const response = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
      if (!response.ok) {
        console.warn(
          `[API] ${options.method || "GET"} ${path} → ${response.status}`,
        );
      }
      return await response.json();
    } catch (err) {
      console.error(`[API] Network error on ${path}:`, err.message);
      return null;
    }
  }

  const get = (path) => request(path);
  const post = (path, body) =>
    request(path, { method: "POST", body: JSON.stringify(body) });

  // ── Sensor endpoints ───────────────────────────────────────────────────────
  const sensors = {
    current: () => get("/api/sensors"),
    history: (hours = 24) => get(`/api/sensors/history?hours=${hours}`),
    alerts: () => get("/api/alerts"),
  };

  // ── Weather endpoints ──────────────────────────────────────────────────────
  const weather = {
    current: (lat, lon, city) =>
      get(
        `/api/weather/current?lat=${lat}&lon=${lon}&city=${encodeURIComponent(city)}`,
      ),
    forecast: (lat, lon, days, city) =>
      post("/api/weather/forecast", { lat, lon, days, city }),
    geocode: (city) =>
      get(`/api/weather/geocode?city=${encodeURIComponent(city)}`),
  };

  // ── Prediction endpoints ───────────────────────────────────────────────────
  const predict = {
    crop: (params) => post("/api/predict/crop", params),
    disease: (crop, image) =>
      post("/api/predict/disease", { crop, image: image || null }),
    soil: (params) => post("/api/predict/soil", params),
    intent: (text, language = "en") =>
      post("/api/predict/intent", { text, language }),
  };

  // ── System endpoints ───────────────────────────────────────────────────────
  const system = {
    health: () => get("/api/health"),
    status: () => get("/api/status"),
  };

  // ── Public API ─────────────────────────────────────────────────────────────
  return { sensors, weather, predict, system, get, post };
})();

// Make available globally
window.AgriAPI = AgriAPI;
