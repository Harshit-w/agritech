"use strict";
/* ── AgriTech v3 — main.js ─────────────────────────────────────────────────── */

// ── STATE ─────────────────────────────────────────────────────────────────────
const S = {
  sensors: null,
  log: [],
  charts: {},
  zones: {},
  donut: null,
  sortCol: 0,
  sortAsc: false,
  session_id: generateSessionId(), // Unique per browser session for rate limiting
  // Default location — Bageshwar, Uttarakhand, India
  // Overwritten automatically when user grants GPS permission
  city: "Bageshwar, Uttarakhand, India",
  lat: 29.500667,
  lon: 79.542889,
};

// ── Generate unique session ID ──────────────────────────────────────────────
function generateSessionId() {
  let sid = localStorage.getItem("agritech_session_id");
  if (!sid) {
    sid = "sess_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
    localStorage.setItem("agritech_session_id", sid);
  }
  return sid;
}

// ── API HELPER ────────────────────────────────────────────────────────────────
function getApiOrigin() {
  // When opened via VS Code Live Server (e.g. :5500), backend still runs on Flask :5000.
  if (window.location.port === "5500") {
    const host = window.location.hostname || "127.0.0.1";
    return `${window.location.protocol}//${host}:5000`;
  }
  return window.location.origin;
}

function apiUrl(path) {
  if (/^https?:\/\//i.test(path)) return path;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiOrigin()}${normalizedPath}`;
}

async function api(path, opts = {}) {
  try {
    const url = apiUrl(path);
    const r = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    console.error("[API]", path, e.message);
    return null;
  }
}

// ── HELPERS ───────────────────────────────────────────────────────────────────
const el = (id) => document.getElementById(id);
const set = (id, v) => {
  const e = el(id);
  if (e) e.textContent = v;
};
const sw = (id, w) => {
  const e = el(id);
  if (e) e.style.width = w;
};
const htm = (id, v) => {
  const e = el(id);
  if (e) e.innerHTML = v;
};

const fmt1 = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(1) : v;
};

function syncWeatherPanelsFromSensors(s) {
  if (!s) return;
  set("tw-temp", `${fmt1(s.temperature)}°C`);
  set("wb-temp", `${fmt1(s.temperature)}°C`);
  set("wb-hum", `${fmt1(s.humidity)}%`);
}

function prettifyDiseaseLabel(name) {
  if (!name) return "";
  return String(name).replace(/_+/g, " ").replace(/\s+/g, " ").trim();
}

// ── CLOCK ─────────────────────────────────────────────────────────────────────
setInterval(() => {
  set("clock", new Date().toLocaleTimeString("en-IN", { hour12: false }));
}, 1000);
set("clock", new Date().toLocaleTimeString("en-IN", { hour12: false }));

// ── NAVIGATION ────────────────────────────────────────────────────────────────
const PAGE = {
  dashboard: ["Farm Dashboard", "Real-time monitoring and AI insights"],
  sensors: ["Live Sensors", "8 field sensors — updated every 60 seconds"],
  weather: ["Weather Forecast", "Real data from Open-Meteo API"],
  crop: ["Crop Advisor", "AI-powered crop recommendations"],
  disease: ["Disease Detection", "CNN leaf disease analysis"],
  soil: ["Soil Lab", "Nutrient profiling and health scoring"],
  maps: ["Farm Maps", "Live location and manual farm markers"],
  analytics: ["Farm Analytics", "Trends, health score and data log"],
};

function goTab(tab) {
  document
    .querySelectorAll(".nav-item")
    .forEach((n) => n.classList.toggle("active", n.dataset.tab === tab));
  document
    .querySelectorAll(".tab-pane")
    .forEach((p) => p.classList.toggle("active", p.id === "tab-" + tab));
  const [t, s] = PAGE[tab] || ["AgriTech", ""];
  set("page-title", t);
  set("page-sub", s);
  if (tab === "analytics") initTrendChart();
  if (tab === "maps") initFarmMap();
  if (tab === "aichat") initChat();
}

document
  .querySelectorAll(".nav-item")
  .forEach((n) => n.addEventListener("click", () => goTab(n.dataset.tab)));

// ── SENSOR POLLING ────────────────────────────────────────────────────────────
async function pollSensors() {
  // Pass current GPS coordinates so temp/humidity reflect actual location
  const d = await api(`/api/sensors?lat=${S.lat}&lon=${S.lon}`);
  if (!d) return;
  S.sensors = d;
  // Keep weather chip + weather banner in lockstep with sensor stream values.
  syncWeatherPanelsFromSensors(d);
  updateDash(d);
  updateSensorGrid(d);
  addToLog(d);
}

async function pollAlerts() {
  const d = await api("/api/alerts");
  if (!d) return;
  set("alert-badge", d.count);
  renderAlerts(d.alerts);
}

// ── FARM MAPS ────────────────────────────────────────────────────────────────
const FARM_STORAGE_KEY = "agritech_saved_farms";
const DEFAULT_FARM_CENTER = {
  lat: 29.500667,
  lon: 79.542889,
  city: "Bageshwar, Uttarakhand, India",
};

let farmMap = null;
let farmBaseLayer = null;
let farmSatelliteLayer = null;
let farmLayerControl = null;
let farmMarkersLayer = null;
let farmMarkers = loadFarmMarkers();

function loadFarmMarkers() {
  try {
    return JSON.parse(localStorage.getItem(FARM_STORAGE_KEY) || "[]");
  } catch (_) {
    return [];
  }
}

function saveFarmMarkers() {
  localStorage.setItem(FARM_STORAGE_KEY, JSON.stringify(farmMarkers));
}

function renderFarmList() {
  const list = el("farm-list");
  if (!list) return;
  if (!farmMarkers.length) {
    list.innerHTML =
      '<div class="farm-empty">No farms saved yet. Double-click on the map to add one.</div>';
    return;
  }
  list.innerHTML = farmMarkers
    .map(
      (farm, index) => `
        <div class="farm-item">
          <div>
            <div class="farm-name">${farm.name}</div>
            <div class="farm-coords">${farm.lat.toFixed(5)}, ${farm.lon.toFixed(5)}</div>
          </div>
          <div class="farm-actions">
            <button class="farm-jump" onclick="focusFarm(${index})">Focus</button>
            <button class="farm-delete" onclick="deleteFarm(${index})">Delete</button>
          </div>
        </div>`,
    )
    .join("");
}

function addFarmMarker(lat, lon, name) {
  const farm = {
    name: name || `Farm ${farmMarkers.length + 1}`,
    lat: +lat,
    lon: +lon,
    createdAt: new Date().toISOString(),
  };
  farmMarkers.push(farm);
  saveFarmMarkers();
  renderFarmList();
  refreshFarmMarkers();
}

function refreshFarmMarkers() {
  if (!farmMap || !farmMarkersLayer || typeof L === "undefined") return;
  farmMarkersLayer.clearLayers();
  farmMarkers.forEach((farm, index) => {
    const marker = L.marker([farm.lat, farm.lon]).addTo(farmMarkersLayer);
    marker.bindPopup(
      `<b>${farm.name}</b><br>${farm.lat.toFixed(5)}, ${farm.lon.toFixed(5)}`,
    );
    marker.on("click", () => {
      farmMap.setView([farm.lat, farm.lon], 16);
    });
  });
}

function focusFarm(index) {
  const farm = farmMarkers[index];
  if (!farm || !farmMap) return;
  farmMap.setView([farm.lat, farm.lon], 16);
}

function deleteFarm(index) {
  const farm = farmMarkers[index];
  if (!farm) return;
  if (!confirm(`Delete farm "${farm.name}"? This cannot be undone.`)) return;
  farmMarkers.splice(index, 1);
  saveFarmMarkers();
  renderFarmList();
  refreshFarmMarkers();
}

function clearFarmMarkers() {
  if (!confirm("Clear all saved farm markers?")) return;
  farmMarkers = [];
  saveFarmMarkers();
  renderFarmList();
  refreshFarmMarkers();
}

async function locateFarm() {
  if (!navigator.geolocation) {
    alert("Geolocation is not supported by this browser.");
    return;
  }
  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const lat = +pos.coords.latitude.toFixed(6);
      const lon = +pos.coords.longitude.toFixed(6);
      const nameInput = el("farm-name");
      const farmName =
        nameInput && nameInput.value.trim()
          ? nameInput.value.trim()
          : `My Farm ${farmMarkers.length + 1}`;
      addFarmMarker(lat, lon, farmName);
      if (farmMap) farmMap.setView([lat, lon], 16);
      const currentLabel = farmName || DEFAULT_FARM_CENTER.city;
      setAllLocationText(currentLabel, currentLabel.split(",")[0], lat, lon);
      await onLocationUpdate(lat, lon);
    },
    () => alert("Unable to access your location right now."),
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 },
  );
}

function initFarmMap() {
  const mapEl = el("farm-map");
  if (!mapEl || typeof L === "undefined") return;
  if (farmMap) {
    farmMap.invalidateSize();
    refreshFarmMarkers();
    renderFarmList();
    return;
  }

  farmMap = L.map("farm-map", {
    zoomControl: true,
    doubleClickZoom: false,
  }).setView([S.lat, S.lon], 13);

  farmBaseLayer = L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  );

  farmSatelliteLayer = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
      maxZoom: 19,
      attribution: "Tiles &copy; Esri",
    },
  );

  farmBaseLayer.addTo(farmMap);
  farmMarkersLayer = L.layerGroup().addTo(farmMap);

  farmLayerControl = L.control
    .layers(
      { Street: farmBaseLayer, Satellite: farmSatelliteLayer },
      { Farms: farmMarkersLayer },
      { collapsed: true },
    )
    .addTo(farmMap);

  farmMap.on("dblclick", (e) => {
    const farmNameInput = el("farm-name");
    const farmName =
      farmNameInput && farmNameInput.value.trim()
        ? farmNameInput.value.trim()
        : `Farm ${farmMarkers.length + 1}`;
    addFarmMarker(e.latlng.lat, e.latlng.lng, farmName);
  });

  refreshFarmMarkers();
  renderFarmList();
  setTimeout(() => farmMap.invalidateSize(), 200);
}

// ── DASHBOARD UPDATE ──────────────────────────────────────────────────────────
function updateDash(s) {
  set("d-temp", s.temperature);
  set("d-moist", s.soil_moisture);
  set("d-hum", s.humidity);
  set("d-ph", s.ph_level);
  set(
    "d-temp-src",
    s.weather_source && s.weather_source.includes("Open-Meteo")
      ? "🟢 Live · Open-Meteo"
      : "🟡 Simulated",
  );
  set("d-moist-src", "🟡 Field sensor · simulated");
  set(
    "d-hum-src",
    s.weather_source && s.weather_source.includes("Open-Meteo")
      ? "🟢 Live · Open-Meteo"
      : "🟡 Simulated",
  );
  set("d-ph-src", "🟡 Field sensor · simulated");
  sw("d-temp-bar", Math.min(100, (s.temperature / 50) * 100) + "%");
  sw("d-moist-bar", s.soil_moisture + "%");
  sw("d-hum-bar", s.humidity + "%");
  sw("d-ph-bar", ((s.ph_level - 3) / 9) * 100 + "%");

  set("d-n", s.nitrogen + " mg/kg");
  set("d-p", s.phosphorus + " mg/kg");
  set("d-k", s.potassium + " mg/kg");
  sw("d-n-bar", Math.min(100, (s.nitrogen / 150) * 100) + "%");
  sw("d-p-bar", Math.min(100, (s.phosphorus / 80) * 100) + "%");
  sw("d-k-bar", Math.min(100, (s.potassium / 300) * 100) + "%");
  // Sync fertilizer tab NPK display
  set("fert-n-val", s.nitrogen + " mg/kg");
  set("fert-p-val", s.phosphorus + " mg/kg");
  set("fert-k-val", s.potassium + " mg/kg");
  sw("fert-n-bar", Math.min(100, (s.nitrogen / 150) * 100) + "%");
  sw("fert-p-bar", Math.min(100, (s.phosphorus / 80) * 100) + "%");
  sw("fert-k-bar", Math.min(100, (s.potassium / 300) * 100) + "%");

  // Health score
  const score = Math.round(
    s.soil_moisture * 0.3 +
      s.humidity * 0.25 +
      Math.min(100, (1 - Math.abs(s.temperature - 28) / 20) * 100) * 0.25 +
      Math.min(100, (1 - Math.abs(s.ph_level - 6.5) / 3) * 100) * 0.2,
  );
  set("health-num", score);
  set("hs-moist", s.soil_moisture + "%");
  sw("hs-moist-b", s.soil_moisture + "%");
  set("hs-hum", s.humidity + "%");
  sw("hs-hum-b", s.humidity + "%");
  set("hs-temp", s.temperature + "°C");
  sw("hs-temp-b", Math.min(100, (s.temperature / 50) * 100) + "%");
  set("hs-ph", s.ph_level);
  sw("hs-ph-b", ((s.ph_level - 3) / 9) * 100 + "%");
  updateDonut(score);
}

// ── SENSOR GRID ───────────────────────────────────────────────────────────────
const SDEFS = [
  {
    k: "temperature",
    n: "Temperature",
    ic: "🌡️",
    u: "°C",
    w: [10, 38],
    d: [0, 45],
  },
  {
    k: "soil_moisture",
    n: "Soil Moisture",
    ic: "💧",
    u: "%",
    w: [30, 80],
    d: [20, 90],
  },
  { k: "humidity", n: "Humidity", ic: "🌫️", u: "%", w: [40, 85], d: [30, 95] },
  {
    k: "ph_level",
    n: "pH Level",
    ic: "⚗️",
    u: "",
    w: [5.8, 7.5],
    d: [5.0, 8.5],
  },
  {
    k: "light_intensity",
    n: "Light",
    ic: "☀️",
    u: "lux",
    w: [1000, 80000],
    d: [500, 100000],
  },
  {
    k: "nitrogen",
    n: "Nitrogen",
    ic: "🌿",
    u: "mg/kg",
    w: [30, 120],
    d: [10, 150],
  },
  {
    k: "phosphorus",
    n: "Phosphorus",
    ic: "🔵",
    u: "mg/kg",
    w: [10, 60],
    d: [5, 80],
  },
  {
    k: "potassium",
    n: "Potassium",
    ic: "🟣",
    u: "mg/kg",
    w: [80, 250],
    d: [50, 300],
  },
];

function sStatus(v, def) {
  if (v < def.d[0] || v > def.d[1]) return "critical";
  if (v < def.w[0] || v > def.w[1]) return "warning";
  return "normal";
}

function updateSensorGrid(s) {
  const g = el("sensor-grid");
  if (!g) return;
  g.innerHTML = SDEFS.map((def) => {
    const v = s[def.k],
      st = sStatus(v, def);
    const disp =
      typeof v === "number" && !Number.isInteger(v) ? v.toFixed(2) : v;
    return `<div class="sensor-card">
      <div class="s-icon">${def.ic}</div>
      <div class="s-name">${def.n}</div>
      <div class="s-val">${disp}<span class="s-unit"> ${def.u}</span></div>
      <span class="s-badge s-${st}">${st}</span>
    </div>`;
  }).join("");

  // Sensor bar chart
  if (!S.charts.sensor) {
    S.charts.sensor = new Chart(el("sensor-chart").getContext("2d"), {
      type: "bar",
      data: {
        labels: [],
        datasets: [
          {
            data: [],
            backgroundColor: [
              "rgba(45,106,79,.55)",
              "rgba(37,99,235,.55)",
              "rgba(8,145,178,.55)",
              "rgba(147,51,234,.55)",
            ],
            borderRadius: 6,
          },
        ],
      },
      options: {
        ...CO(),
        plugins: { legend: { display: false } },
        scales: { y: YA(), x: XA() },
      },
    });
  }
  S.charts.sensor.data.labels = SDEFS.slice(0, 4).map((d) => d.n);
  S.charts.sensor.data.datasets[0].data = SDEFS.slice(0, 4).map((d) => {
    const v = s[d.k];
    return Math.min(100, v > 1000 ? v / 1000 : v);
  });
  S.charts.sensor.update("none");
}

// ── ALERTS ────────────────────────────────────────────────────────────────────
function renderAlerts(alerts) {
  const map = {
    ok: "a-ok",
    warn: "a-warn",
    danger: "a-danger",
    info: "a-info",
  };
  htm(
    "dash-alerts",
    alerts
      .map(
        (a) => `
    <div class="alert-item ${map[a.type] || "a-info"}">
      <span style="font-size:17px">${a.icon}</span>
      <div><div class="alert-title">${a.title}</div>
      <div class="alert-msg">${a.msg}</div></div>
    </div>`,
      )
      .join(""),
  );
}

// ── CHART OPTIONS ─────────────────────────────────────────────────────────────
function CO() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300 },
    plugins: {
      legend: {
        labels: {
          color: "#888",
          font: { family: "Plus Jakarta Sans", size: 11 },
          boxWidth: 10,
        },
      },
    },
  };
}
function YA() {
  return {
    grid: { color: "rgba(0,0,0,0.05)" },
    ticks: { color: "#aaa", font: { family: "Plus Jakarta Sans", size: 10 } },
  };
}
function XA() {
  return {
    grid: { color: "rgba(0,0,0,0.03)" },
    ticks: {
      color: "#aaa",
      font: { family: "Plus Jakarta Sans", size: 10 },
      maxTicksLimit: 8,
    },
  };
}

async function initDashChart() {
  const d = await api("/api/sensors/history?hours=24");
  if (!d) return;
  const pts = d.data.slice(-48);
  const labels = pts.map((p) =>
    new Date(p.timestamp).toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }),
  );
  if (S.charts.dash) S.charts.dash.destroy();
  S.charts.dash = new Chart(el("dash-chart").getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Temp °C",
          data: pts.map((p) => p.temperature),
          borderColor: "#ef4444",
          backgroundColor: "rgba(239,68,68,.07)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
        },
        {
          label: "Moisture %",
          data: pts.map((p) => p.soil_moisture),
          borderColor: "#2563eb",
          backgroundColor: "rgba(37,99,235,.07)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
        },
      ],
    },
    options: { ...CO(), scales: { y: YA(), x: XA() } },
  });
}

function initTrendChart() {
  if (S.charts.trend) return;
  api("/api/sensors/history?hours=24").then((d) => {
    if (!d) return;
    const pts = d.data.slice(-48);
    const labels = pts.map((p) =>
      new Date(p.timestamp).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }),
    );
    S.charts.trend = new Chart(el("trend-chart").getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Temperature",
            data: pts.map((p) => p.temperature),
            borderColor: "#ef4444",
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.4,
            fill: false,
          },
          {
            label: "Moisture",
            data: pts.map((p) => p.soil_moisture),
            borderColor: "#2563eb",
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.4,
            fill: false,
          },
          {
            label: "Humidity",
            data: pts.map((p) => p.humidity),
            borderColor: "#0891b2",
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.4,
            fill: false,
          },
        ],
      },
      options: { ...CO(), scales: { y: YA(), x: XA() } },
    });
  });
}

function updateDonut(score) {
  const canvas = el("donut-chart");
  if (!canvas) return;
  const color = score >= 70 ? "#16a34a" : score >= 40 ? "#d97706" : "#dc2626";
  if (S.donut) S.donut.destroy();
  S.donut = new Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      datasets: [
        {
          data: [score, 100 - score],
          backgroundColor: [color, "#f3f4f6"],
          borderWidth: 0,
          circumference: 270,
          rotation: -135,
        },
      ],
    },
    options: {
      responsive: false,
      plugins: { legend: { display: false } },
      cutout: "76%",
    },
  });
}

// ── WEATHER ───────────────────────────────────────────────────────────────────
async function loadWeatherBanner() {
  // Always use current S.lat/S.lon so it reflects GPS-updated location
  const d = await api(
    `/api/weather/current?lat=${S.lat}&lon=${S.lon}&city=${encodeURIComponent(S.city)}`,
  );
  if (!d || d.error) return;
  el("wb").classList.add("show");
  set("wb-icon", d.icon);
  set("wb-temp", `${fmt1(d.temperature)}°C`);
  set("wb-cond", d.condition);
  set("wb-feel", `${fmt1(d.feels_like)}°C`);
  set("wb-hum", `${fmt1(d.humidity)}%`);
  set("wb-wind", d.wind_kmh + " km/h");
  set("wb-prec", d.precipitation + " mm");
  set("wb-uv", d.uv_index);
  set("tw-icon", d.icon);
  set("tw-temp", `${fmt1(d.temperature)}°C`);
  set("tw-cond", d.condition);
  // Keep all location pills in sync on every weather refresh
  const short = S.city.split(",")[0].trim();
  set("tw-city", short);
  set("topbar-city-pill", short);
  set("footer-city", short);
  set("wb-banner-loc", S.city);
}

async function searchCity() {
  const city = el("w-city").value.trim();
  if (!city) return;
  htm("city-res", "🔍 Searching...");
  const d = await api("/api/weather/geocode?city=" + encodeURIComponent(city));
  if (!d || d.error) {
    htm("city-res", "❌ Not found — try a different name.");
    return;
  }
  el("w-lat").value = d.latitude;
  el("w-lon").value = d.longitude;
  S.city = d.city;
  S.lat = d.latitude;
  S.lon = d.longitude;
  set("w-city-lbl", d.city);
  htm(
    "city-res",
    "✅ <b>" + d.city + "</b> — " + d.latitude + "°N, " + d.longitude + "°E",
  );
}

async function loadNow() {
  const lat = +el("w-lat").value,
    lon = +el("w-lon").value;
  const d = await api(
    "/api/weather/current?lat=" +
      lat +
      "&lon=" +
      lon +
      "&city=" +
      encodeURIComponent(S.city),
  );
  if (!d || d.error) return;
  htm(
    "w-result",
    `
    <div style="display:flex;align-items:center;gap:1rem;padding:1rem;background:linear-gradient(135deg,#f0fdf4,#dcfce7);border-radius:11px;margin-bottom:.75rem">
      <div style="font-size:40px">${d.icon}</div>
      <div>
        <div style="font-size:28px;font-weight:800;color:#166534">${d.temperature}°C</div>
        <div style="font-size:13px;color:#166534;opacity:.85">${d.condition}</div>
        <div style="font-size:11px;color:#6b7280;margin-top:3px">Feels ${d.feels_like}°C · ${d.humidity}% RH · Wind ${d.wind_kmh} km/h · UV ${d.uv_index}</div>
      </div>
    </div>
    <div style="font-size:10px;color:var(--text3)">📡 ${d.source} · ${S.city}</div>`,
  );
}

async function loadForecast() {
  const lat = +el("w-lat").value;
  const lon = +el("w-lon").value;
  const days = +el("w-days").value;
  htm(
    "w-result",
    '<div style="text-align:center;padding:2rem"><span class="spin"></span><br><small class="muted" style="display:block;margin-top:.5rem">Fetching from Open-Meteo…</small></div>',
  );
  const d = await api("/api/weather/forecast", {
    method: "POST",
    body: JSON.stringify({ lat, lon, days, city: S.city }),
  });
  if (!d) return;
  set("w-city-lbl", d.city);
  htm(
    "w-result",
    '<div class="fc-header"><span>Date</span><span>Condition</span><span>Temp</span><span>Hum</span><span>Rain</span><span>Wind</span><span>UV</span></div>' +
      d.forecast
        .map(
          (f) => `
      <div class="fc-row">
        <span style="color:var(--text2);font-weight:600">${f.date}</span>
        <span>${f.icon} ${f.condition}</span>
        <span style="color:#dc2626;font-weight:600">${f.temp_max}/${f.temp_min}°</span>
        <span style="color:#2563eb">${f.humidity}%</span>
        <span style="color:#16a34a">${Math.round(f.rainfall_probability * 100)}%</span>
        <span style="color:#6b7280">${f.wind_kmh}</span>
        <span style="color:#9333ea">${f.uv_index}</span>
      </div>`,
        )
        .join("") +
      `<div style="font-size:10px;color:var(--text3);padding:.4rem .7rem">📡 ${d.source}</div>`,
  );
  buildWChart(d.forecast);
}

function buildWChart(fc) {
  if (S.charts.weather) S.charts.weather.destroy();
  S.charts.weather = new Chart(el("w-chart").getContext("2d"), {
    type: "line",
    data: {
      labels: fc.map((f) => f.date),
      datasets: [
        {
          label: "Max Temp",
          data: fc.map((f) => f.temp_max),
          borderColor: "#ef4444",
          borderWidth: 2,
          pointRadius: 3,
          tension: 0.4,
          fill: false,
        },
        {
          label: "Min Temp",
          data: fc.map((f) => f.temp_min),
          borderColor: "#fb923c",
          borderWidth: 1.5,
          pointRadius: 2,
          tension: 0.4,
          fill: false,
          borderDash: [4, 3],
        },
        {
          label: "Humidity",
          data: fc.map((f) => f.humidity),
          borderColor: "#2563eb",
          borderWidth: 1.5,
          pointRadius: 2,
          tension: 0.4,
        },
        {
          label: "Rain %",
          data: fc.map((f) => f.rainfall_probability * 100),
          borderColor: "#16a34a",
          borderWidth: 1.5,
          pointRadius: 2,
          tension: 0.4,
        },
      ],
    },
    options: { ...CO(), scales: { y: YA(), x: XA() } },
  });
}

// ── CROP ──────────────────────────────────────────────────────────────────────
function autofill() {
  if (!S.sensors) return;
  const s = S.sensors;
  el("c-temp").value = s.temperature;
  el("c-hum").value = s.humidity;
  el("c-moist").value = s.soil_moisture;
  el("c-ph").value = s.ph_level;
  el("c-n").value = s.nitrogen;
  el("c-p").value = s.phosphorus;
  el("c-k").value = s.potassium;
}

async function doCrop() {
  htm(
    "crop-result",
    '<div style="text-align:center;padding:2rem"><span class="spin"></span></div>',
  );
  const d = await api("/api/predict/crop", {
    method: "POST",
    body: JSON.stringify({
      temperature: +el("c-temp").value,
      humidity: +el("c-hum").value,
      soil_moisture: +el("c-moist").value,
      ph_level: +el("c-ph").value,
      nitrogen: +el("c-n").value,
      phosphorus: +el("c-p").value,
      potassium: +el("c-k").value,
    }),
  });
  if (!d) {
    htm("crop-result", '<p class="muted">Failed. Please try again.</p>');
    return;
  }
  htm(
    "crop-result",
    `
    <div class="result-hero">
      <div class="rh-icon">${d.icon}</div>
      <div>
        <div class="rh-name">${d.crop}</div>
        <div class="rh-sub">⭐ Best match · ${d.confidence}% confidence</div>
        <div class="rh-sub">${d.model}</div>
      </div>
    </div>
    <div class="section-h">Top 5 Matches</div>
    ${d.top5
      .map(
        (c) => `
      <div class="score-row">
        <div class="score-lbl">${c.icon} ${c.name}</div>
        <div class="score-track"><div class="score-fill" style="width:${c.score}%"></div></div>
        <div class="score-pct">${c.score}%</div>
      </div>`,
      )
      .join("")}
    <div style="font-size:11px;color:var(--text3);margin-top:.65rem">Temp ${d.top5[0].temp} · pH ${d.top5[0].ph}</div>`,
  );
}

// ── DISEASE ───────────────────────────────────────────────────────────────────
function previewImg(input) {
  const file = input.files[0];
  if (!file) return;
  leafMimeType = file.type || "image/jpeg";
  const img = el("u-prev");
  const objectUrl = URL.createObjectURL(file);
  img.src = objectUrl;
  img.style.display = "block";
  el("u-ph").style.display = "none";
  const video = el("leaf-camera-video");
  if (video) video.style.display = "none";
  // Hide warning, enable button
  const msg = el("no-img-msg");
  if (msg) msg.style.display = "none";
  const reader = new FileReader();
  reader.onload = (e) => {
    const result = e.target.result;
    leafImageB64 = result.split(",")[1];
  };
  reader.readAsDataURL(file);
  // Reset result so user knows a new analysis is needed
  htm(
    "disease-result",
    '<div style="text-align:center;padding:1.5rem 0;color:var(--text3);font-size:12px">📸 Image loaded — click Analyse Image to detect disease</div>',
  );
}

async function doDisease() {
  const crop = el("dis-crop").value;
  const fi = el("dis-img");
  let img64 = null;

  // Warn if no image — analysis is less reliable
  const noMsg = el("no-img-msg");
  if (!fi.files[0]) {
    img64 = leafImageB64;
    if (noMsg) noMsg.style.display = "block";
    htm(
      "disease-result",
      '<div style="text-align:center;padding:2rem;color:var(--warn)">' +
        '<div style="font-size:24px;margin-bottom:.5rem">⚠️</div>' +
        "<b>No image uploaded</b><br>" +
        '<span style="font-size:11px;color:var(--text3);margin-top:.4rem;display:block">' +
        "Please upload a leaf photo for accurate disease detection.<br>" +
        "Without an image the result cannot be reliable.</span></div>",
    );
    return;
  }

  htm(
    "disease-result",
    '<div style="text-align:center;padding:2rem"><span class="spin"></span> Analysing image…</div>',
  );
  if (fi.files[0]) {
    img64 = await new Promise((res) => {
      const r = new FileReader();
      r.onload = () => res(r.result.split(",")[1]);
      r.readAsDataURL(fi.files[0]);
    });
  }
  const d = await api("/api/predict/disease", {
    method: "POST",
    body: JSON.stringify({ crop, image: img64 }),
  });
  if (!d) {
    htm("disease-result", '<p class="muted">Failed.</p>');
    return;
  }
  if (d.disease === "ADD IMAGE OF PLANT") {
    htm(
      "disease-result",
      `
      <div style="text-align:center;padding:2.2rem 1rem;color:var(--warn)">
        <div style="font-size:34px;margin-bottom:.6rem">🍃</div>
        <div style="font-size:16px;font-weight:800;letter-spacing:.2px">ADD IMAGE OF PLANT</div>
        <div style="font-size:12px;color:var(--text3);margin-top:.45rem;line-height:1.5">
          The uploaded picture does not look like a plant leaf.
          <br />Please upload or capture a leaf image for disease detection.
        </div>
      </div>`,
    );
    return;
  }
  const bgCls = d.healthy ? "a-ok" : "a-danger";
  const icon = d.healthy ? "✅" : "⚠️";
  const fertHtml = buildFertilizerSection(d.disease, S.sensors);
  // Auto-sync disease result to fertilizer tab
  if (d && d.disease && d.disease !== "No image")
    syncDiseaseToFertilizer(d.disease);
  htm(
    "disease-result",
    `
    <div class="disease-hero ${bgCls}" style="border-color:${d.color}">
      <div class="d-icon">${icon}</div>
      <div>
        <div class="d-name" style="color:${d.color}">${prettifyDiseaseLabel(d.disease)}</div>
        <div class="d-sub">${d.crop} · ${d.confidence}% confidence · ${d.severity} severity</div>
        <div class="d-treat">${d.treatment}</div>
      </div>
    </div>
    <div class="section-h">Probability Breakdown</div>
    <div class="prob-list">
    ${Object.entries(d.probs)
      .sort((a, b) => b[1] - a[1])
      .map(
        ([name, pct]) => `
      <div class="prob-row">
        <div class="prob-lbl" title="${prettifyDiseaseLabel(name)}">${prettifyDiseaseLabel(name)}</div>
        <div class="prob-track"><div class="prob-fill" style="width:${pct}%;background:${d.color}"></div></div>
        <div class="prob-pct">${pct}%</div>
      </div>`,
      )
      .join("")}
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:.6rem;font-size:10px;color:var(--text3)"><span>${d.model}</span><span style="background:var(--card2);padding:2px 8px;border-radius:20px;border:1px solid var(--border)">🔒 Same image = same result</span></div>
    ${fertHtml}`,
  );
}

// ── SOIL ─────────────────────────────────────────────────────────────────────
async function doSoil() {
  htm(
    "soil-result",
    '<div style="text-align:center;padding:2rem"><span class="spin"></span></div>',
  );
  const d = await api("/api/predict/soil", {
    method: "POST",
    body: JSON.stringify({
      nitrogen: +el("s-n").value,
      phosphorus: +el("s-p").value,
      potassium: +el("s-k").value,
      ph_level: +el("s-ph").value,
      organic_matter: +el("s-om").value,
    }),
  });
  if (!d) {
    htm("soil-result", '<p class="muted">Failed.</p>');
    return;
  }
  const RC = {
    ok: "r-ok",
    warn: "r-warn",
    caution: "r-caution",
    action: "r-action",
    info: "r-info",
  };
  const RI = { ok: "✅", warn: "⚠️", caution: "🔶", action: "🔵", info: "💡" };
  htm(
    "soil-result",
    `
    <div class="soil-hero">
      <div class="soil-score" style="color:${d.color}">${d.score}</div>
      <div>
        <div style="font-size:16px;font-weight:700;color:${d.color}">${d.status}</div>
        <div style="font-size:11px;color:var(--text2);margin-top:2px">NPK Ratio: ${d.npk}</div>
        <div style="font-size:10px;color:var(--text3);margin-top:2px">${d.model}</div>
      </div>
    </div>
    <div class="section-h">Recommendations</div>
    ${d.recs.map((r) => `<div class="rec-item ${RC[r.type] || "r-info"}">${RI[r.type] || "•"} ${r.text}</div>`).join("")}
    <div class="section-h" style="margin-top:.8rem">Score Breakdown</div>
    ${Object.entries(d.breakdown)
      .map(
        ([k, v]) => `
      <div class="score-row">
        <div class="score-lbl">${k}</div>
        <div class="score-track"><div class="score-fill" style="width:${(v / 30) * 100}%"></div></div>
        <div class="score-pct">${v}</div>
      </div>`,
      )
      .join("")}`,
  );
}

// ── DATA LOG ──────────────────────────────────────────────────────────────────
const LOG_FIELDS = [
  "timestamp",
  "temperature",
  "soil_moisture",
  "humidity",
  "ph_level",
  "light_intensity",
  "nitrogen",
  "phosphorus",
  "potassium",
];

function addToLog(s) {
  S.log.unshift(s);
  if (S.log.length > 20) S.log.pop();
  renderLog();
}

function renderLog() {
  const tbody = el("log-body");
  if (!tbody) return;
  set("log-count", S.log.length);
  tbody.innerHTML = S.log
    .map(
      (r) => `<tr>
    <td>${new Date(r.timestamp).toLocaleTimeString()}</td>
    <td>${r.temperature}</td><td>${r.soil_moisture}</td>
    <td>${r.humidity}</td><td>${r.ph_level}</td>
    <td>${Number(r.light_intensity).toLocaleString()}</td>
    <td>${r.nitrogen}</td><td>${r.phosphorus}</td><td>${r.potassium}</td>
  </tr>`,
    )
    .join("");
}

function sortLog(col) {
  S.sortAsc = S.sortCol === col ? !S.sortAsc : true;
  S.sortCol = col;
  const f = LOG_FIELDS[col];
  S.log.sort((a, b) => {
    let va = a[f],
      vb = b[f];
    if (typeof va === "string") {
      va = va.toLowerCase();
      vb = vb.toLowerCase();
    }
    return S.sortAsc
      ? va < vb
        ? -1
        : va > vb
          ? 1
          : 0
      : va > vb
        ? -1
        : va < vb
          ? 1
          : 0;
  });
  document.querySelectorAll("#log-table th").forEach((th, i) => {
    const base = th.textContent.replace(/ [↑↓⇅]$/, "");
    th.textContent = base + (i === col ? (S.sortAsc ? " ↑" : " ↓") : " ⇅");
  });
  renderLog();
}

function exportCSV() {
  if (!S.log.length) {
    alert("No data yet — wait a moment for sensor readings.");
    return;
  }
  const hdr = [
    "Timestamp",
    "Temperature",
    "Soil Moisture",
    "Humidity",
    "pH",
    "Light",
    "N",
    "P",
    "K",
  ];
  const rows = S.log.map((r) => [
    r.timestamp,
    r.temperature,
    r.soil_moisture,
    r.humidity,
    r.ph_level,
    r.light_intensity,
    r.nitrogen,
    r.phosphorus,
    r.potassium,
  ]);
  dlFile(
    "agritech_" + new Date().toISOString().slice(0, 10) + ".csv",
    [hdr, ...rows].map((r) => r.join(",")).join("\n"),
    "text/csv",
  );
}

function exportJSON() {
  if (!S.log.length) {
    alert("No data yet.");
    return;
  }
  dlFile(
    "agritech_" + new Date().toISOString().slice(0, 10) + ".json",
    JSON.stringify(
      { exported: new Date().toISOString(), location: S.city, data: S.log },
      null,
      2,
    ),
    "application/json",
  );
}

function clearLog() {
  if (!confirm("Clear all log entries?")) return;
  S.log = [];
  renderLog();
}

function dlFile(name, content, mime) {
  const a = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(new Blob([content], { type: mime })),
    download: name,
  });
  a.click();
  URL.revokeObjectURL(a.href);
}

// ── NLP INTENT ────────────────────────────────────────────────────────────────
async function doIntent() {
  const text = el("nlp-text").value.trim();
  if (!text) return;
  htm("nlp-result", '<span class="spin"></span>');
  const d = await api("/api/predict/intent", {
    method: "POST",
    body: JSON.stringify({ text, language: el("nlp-lang").value }),
  });
  if (!d) {
    htm("nlp-result", "");
    return;
  }
  htm(
    "nlp-result",
    `
    <div style="margin-top:.45rem;display:flex;align-items:center;gap:.7rem;flex-wrap:wrap">
      <span class="intent-chip">${d.icon} ${d.intent}</span>
      <span style="font-size:11px;color:var(--text2)">Confidence: <b>${Math.round(d.confidence * 100)}%</b></span>
      <span style="font-size:11px;color:var(--text3)">${d.model}</span>
    </div>`,
  );
}

// ── FERTILIZER ADVISOR TAB ───────────────────────────────────────────────────
function updateFertilizerTab() {
  const disease = el("fert-disease") ? el("fert-disease").value : "Healthy";
  const html = buildFertilizerSection(disease, S.sensors);
  htm("fert-result", html || '<p class="muted">No recommendations needed.</p>');
}

// ── FERTILIZER TAB PANELS ────────────────────────────────────────────────────
function switchFertTab(tab) {
  ["disease", "manual", "guide"].forEach((t) => {
    el(`fpanel-${t}`).style.display = t === tab ? "block" : "none";
    el(`ftab-${t}`).classList.toggle("active", t === tab);
  });
}

// Auto-fill disease dropdown from Disease AI result
function syncDiseaseToFertilizer(diseaseName) {
  const sel = el("fert-disease");
  if (!sel) return;
  // Try exact match first, then partial
  for (let i = 0; i < sel.options.length; i++) {
    const opt = sel.options[i].value.toLowerCase();
    if (
      diseaseName.toLowerCase().includes(opt) ||
      opt.includes(diseaseName.toLowerCase())
    ) {
      sel.selectedIndex = i;
      const notice = el("fert-auto-notice");
      if (notice) notice.style.display = "block";
      return;
    }
  }
}

// Manual symptom-based search
function manualSearch() {
  const crop = el("ms-crop").value;
  const stage = el("ms-stage").value;
  const symptom = el("ms-symptom").value;
  const ph = el("ms-ph").value;

  if (!symptom) {
    htm(
      "ms-result",
      '<p style="color:var(--warn);font-size:12px">Please select at least a symptom.</p>',
    );
    return;
  }

  // Symptom → nutrient/problem mapping
  const SYMPTOM_MAP = {
    "Yellow leaves (older first)": {
      nutrient: "Nitrogen (N)",
      problem: "N Deficiency",
      color: "#166534",
      bg: "#f0fdf4",
      products: [
        "Urea (46% N) — 25 kg/ha top-dress",
        "Ammonium Nitrate (34% N)",
        "DAP as basal",
        "Farm Yard Manure (FYM)",
      ],
      dose: "Apply 25–30 kg N/ha in split doses. First dose at planting, second at 30 days.",
      note: "Nitrogen is mobile — deficiency shows on older leaves first.",
    },
    "Yellow leaves (younger first)": {
      nutrient: "Sulfur (S) or Iron (Fe)",
      problem: "S/Fe Deficiency",
      color: "#b45309",
      bg: "#fffbeb",
      products: [
        "Gypsum (CaSO₄) — 200 kg/ha",
        "Ferrous Sulfate (FeSO₄) 0.5% foliar",
        "Ammonium Sulfate",
      ],
      dose: "Sulfur: 20–30 kg/ha at planting. Iron: 0.5% FeSO₄ foliar spray.",
      note: "Sulfur and Iron are immobile — deficiency shows in young leaves first.",
    },
    "Purple / red tint on leaves": {
      nutrient: "Phosphorus (P)",
      problem: "P Deficiency",
      color: "#1e40af",
      bg: "#eff6ff",
      products: [
        "SSP (16% P₂O₅) — 300 kg/ha",
        "DAP (46% P₂O₅) — 100 kg/ha",
        "Rock Phosphate (acidic soils)",
        "Bone Meal (organic)",
      ],
      dose: "Apply 40–60 kg P₂O₅/ha as basal before planting. Incorporate into soil.",
      note: "Phosphorus promotes root development and energy transfer.",
    },
    "Brown leaf margins": {
      nutrient: "Potassium (K)",
      problem: "K Deficiency",
      color: "#7c2d12",
      bg: "#fff7ed",
      products: [
        "MOP (60% K₂O) — 75 kg/ha",
        "SOP (50% K₂O) — for sensitive crops",
        "Wood Ash (organic, ~5% K)",
        "Potassium Schoenite",
      ],
      dose: "Apply 40–60 kg K₂O/ha. Split between planting and flowering.",
      note: "Potassium improves drought tolerance, disease resistance, and fruit quality.",
    },
    "White powdery coating": {
      nutrient: "Fungicide needed",
      problem: "Powdery Mildew (Fungal)",
      color: "#d97706",
      bg: "#fffbeb",
      products: [
        "Sulfur 80% WP — 2.5 g/L spray",
        "Hexaconazole 5% EC — 2 mL/L",
        "Neem oil 2% spray",
        "Potassium bicarbonate 0.5%",
      ],
      dose: "Spray at first sign. Repeat every 7–10 days. Avoid spraying in heat >35°C.",
      note: "Improve air circulation. Reduce excess nitrogen. Increase Potassium.",
    },
    "Brown / dark spots on leaves": {
      nutrient: "Fungicide needed",
      problem: "Leaf Spot / Blight (Fungal)",
      color: "#ea580c",
      bg: "#fff7ed",
      products: [
        "Mancozeb 75% WP — 2.5 g/L",
        "Chlorothalonil 75% WP — 2 g/L",
        "Copper Hydroxide (Kocide) — 2 g/L",
        "Azoxystrobin 23% SC — 1 mL/L",
      ],
      dose: "Spray preventively. Repeat every 10–14 days in wet conditions.",
      note: "Remove infected leaves. Avoid overhead irrigation.",
    },
    "Orange / rust coloured patches": {
      nutrient: "Fungicide needed",
      problem: "Rust Disease (Fungal)",
      color: "#dc2626",
      bg: "#fef2f2",
      products: [
        "Propiconazole 25% EC (Tilt) — 1 mL/L",
        "Tebuconazole 25.9% EC — 1 mL/L",
        "Azoxystrobin 23% SC — 1 mL/L",
      ],
      dose: "Apply at first sign. Repeat every 7–14 days. Rotate fungicides.",
      note: "Rust spreads rapidly in cool humid conditions. Act quickly.",
    },
    "Wilting despite adequate water": {
      nutrient: "Fungicide + soil treatment",
      problem: "Wilt Disease (Fusarium/Bacterial)",
      color: "#7c3aed",
      bg: "#f5f3ff",
      products: [
        "Carbendazim 50% WP — 1 g/L soil drench",
        "Trichoderma viride — 5 g/kg seed",
        "Copper Oxychloride 50% WP — 3 g/L",
        "Pseudomonas fluorescens (bio-agent)",
      ],
      dose: "Soil drench around affected plants. Apply Trichoderma at planting.",
      note: "Improve drainage. Avoid waterlogging. Rotate crops.",
    },
    "Stunted growth": {
      nutrient: "NPK + micronutrients",
      problem: "Multiple deficiencies or soil pH issue",
      color: "#166534",
      bg: "#f0fdf4",
      products: [
        "Complete NPK fertilizer 19:19:19 — 5 g/L foliar",
        "Zinc Sulfate 21% — 25 kg/ha soil",
        "Lime if pH < 6 — 1–2 tonnes/ha",
        "FYM/Compost — 10 tonnes/ha",
      ],
      dose: "Apply balanced NPK. Test soil pH. Apply micronutrients if deficient.",
      note: "Get soil test done. pH between 6.0–7.0 is ideal for most crops.",
    },
    "No visible symptoms": {
      nutrient: "Preventive maintenance",
      problem: "Healthy crop — preventive care",
      color: "#16a34a",
      bg: "#f0fdf4",
      products: [
        "Balanced NPK 20:20:20 — as per crop schedule",
        "FYM/Compost — 5–10 t/ha",
        "Micronutrient mix foliar spray",
      ],
      dose: "Follow recommended fertilizer schedule for your crop and stage.",
      note: "Healthy crops need regular nutrition. Prevention is better than cure.",
    },
  };

  const match = SYMPTOM_MAP[symptom] || {
    nutrient: "Consult agronomist",
    problem: "Unknown",
    color: "#6b7280",
    bg: "#f9fafb",
    products: ["Get soil tested first", "Consult local KVK or agronomist"],
    dose: "Diagnosis needed before recommending specific products.",
    note: "Contact your local Krishi Vigyan Kendra (KVK) for free soil testing.",
  };

  const phNote = ph
    ? parseFloat(ph) < 6.0
      ? `<div style="font-size:11px;color:#dc2626;margin-top:.5rem">⚠️ Acidic soil (pH ${ph}) — apply agricultural lime to raise pH above 6.0 before fertilizing.</div>`
      : parseFloat(ph) > 7.5
        ? `<div style="font-size:11px;color:#d97706;margin-top:.5rem">⚠️ Alkaline soil (pH ${ph}) — apply elemental sulfur to lower pH. High pH reduces nutrient availability.</div>`
        : `<div style="font-size:11px;color:#16a34a;margin-top:.5rem">✅ Soil pH ${ph} — within optimal range for nutrient uptake.</div>`
    : "";

  htm(
    "ms-result",
    `
    <div style="padding:.9rem 1rem;background:${match.bg};border:1px solid ${match.color}33;border-radius:11px;margin-bottom:.85rem">
      <div style="font-size:13px;font-weight:700;color:${match.color};margin-bottom:.3rem">${match.problem}</div>
      <div style="font-size:11px;color:var(--text2)">Nutrient / Issue: <b>${match.nutrient}</b></div>
      ${crop ? `<div style="font-size:11px;color:var(--text2)">Crop: ${crop} ${stage ? "· Stage: " + stage : ""}</div>` : ""}
      ${phNote}
    </div>
    <div class="section-h">Recommended Products</div>
    ${match.products
      .map(
        (
          p,
        ) => `<div style="display:flex;gap:.45rem;padding:.4rem .6rem;background:var(--card2);border-radius:6px;margin-bottom:.3rem;font-size:12px">
      <span style="color:${match.color};flex-shrink:0">●</span><span>${p}</span></div>`,
      )
      .join("")}
    <div style="font-size:11px;color:#6b7280;margin-top:.65rem;padding:.5rem .75rem;background:var(--card2);border-radius:6px">
      📋 <b>Dosage:</b> ${match.dose}
    </div>
    <div style="font-size:11px;color:#9333ea;margin-top:.4rem">💡 ${match.note}</div>`,
  );
}

// ── AI CHAT ── Gemini streaming + image analysis ─────────────────────────────
let chatHistory = []; // {role, content} array — persists per session
let chatInited = false;
let chatBusy = false;
let leafImageB64 = null;
let leafMimeType = "image/jpeg";
let cameraStream = null;
let cameraActive = false;
let cameraCaptured = false;
let diseasePlaceholderWasVisible = true;
let diseasePreviewWasVisible = false;
let voiceActive = false;
let voiceCtx = null;
let voiceSource = null;
let voiceProcessor = null;
let voiceStream = null;
let voiceBuffers = [];
let voiceLength = 0;

function initChat() {
  if (chatInited) return;
  chatInited = true;
}

function autoResize(ta) {
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
}

function chatKeyDown(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
}

function askSuggestion(btn) {
  el("chat-input").value = btn.textContent.trim();
  sendChat();
}

function clearChat() {
  chatHistory = [];
  clearLeafImage();
  htm(
    "chat-messages",
    `<div class="chat-msg bot">
    <div class="chat-avatar">🤖</div>
    <div class="chat-bubble">Chat cleared. How can I help you? 🌱</div>
  </div>`,
  );
  el("chat-typing").style.display = "none";
}

// ── Leaf image handling ────────────────────────────────────────────────────────
function handleLeafImage(input) {
  const file = input.files[0];
  if (!file) return;
  leafMimeType = file.type || "image/jpeg";
  const reader = new FileReader();
  reader.onload = (e) => {
    const result = e.target.result;
    leafImageB64 = result.split(",")[1]; // base64 only, no prefix
    const preview = el("leaf-preview-img");
    const ph = el("leaf-upload-placeholder");
    preview.src = result;
    preview.style.display = "block";
    if (ph) ph.style.display = "none";
    const cropRow = el("leaf-crop-row");
    if (cropRow) cropRow.style.display = "block";
  };
  reader.readAsDataURL(file);
}

function clearLeafImage() {
  leafImageB64 = null;
  const input = el("leaf-img-input");
  if (input) input.value = "";
  const preview = el("leaf-preview-img");
  if (preview) {
    preview.src = "";
    preview.style.display = "none";
  }
  const ph = el("leaf-upload-placeholder");
  if (ph) ph.style.display = "flex";
  const cropRow = el("leaf-crop-row");
  if (cropRow) cropRow.style.display = "none";
}

async function startCamera() {
  try {
    if (cameraActive) return;
    const video = el("leaf-camera-video");
    if (!video) return;

    const ph = el("u-ph");
    const preview = el("u-prev");
    diseasePlaceholderWasVisible = !!(ph && ph.style.display !== "none");
    diseasePreviewWasVisible = !!(preview && preview.style.display !== "none");
    cameraCaptured = false;

    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" },
      audio: false,
    });

    video.srcObject = cameraStream;
    video.muted = true;
    video.playsInline = true;
    video.style.display = "block";
    video.onloadedmetadata = () => {
      video.play().catch(() => {});
    };
    cameraActive = true;

    // Hide upload prompt and preview to show only camera
    if (ph) ph.style.display = "none";
    if (preview) preview.style.display = "none";

    const startBtn = el("leaf-camera-start");
    const stopBtn = el("leaf-camera-stop");
    const captureBtn = el("leaf-camera-capture");
    if (startBtn) startBtn.style.display = "none";
    if (stopBtn) stopBtn.style.display = "inline-block";
    if (captureBtn) captureBtn.style.display = "inline-block";
  } catch (err) {
    console.error("Camera access denied:", err);
    alert("⚠️ Camera access denied. Please enable camera in browser settings.");
  }
}

function captureSnapshot() {
  if (!cameraActive) return;
  const video = el("leaf-camera-video");
  const canvas = el("leaf-camera-canvas");
  if (!video || !canvas) return;

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0);

  // Convert canvas to base64
  const dataUrl = canvas.toDataURL("image/jpeg");
  leafImageB64 = dataUrl.split(",")[1];
  leafMimeType = "image/jpeg";
  cameraCaptured = true;

  // Show preview
  const preview = el("u-prev");
  if (preview) {
    preview.src = dataUrl;
    preview.style.display = "block";
  }

  const ph = el("u-ph");
  if (ph) ph.style.display = "none";

  const msg = el("no-img-msg");
  if (msg) msg.style.display = "none";

  // Stop camera after capture
  stopCamera();
}

function stopCamera() {
  if (!cameraStream) return;

  cameraStream.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  cameraActive = false;

  const video = el("leaf-camera-video");
  if (video) video.style.display = "none";

  // If no image was captured, restore the previous Disease-tab state.
  if (!cameraCaptured) {
    const ph = el("u-ph");
    const preview = el("u-prev");
    if (ph) ph.style.display = diseasePlaceholderWasVisible ? "block" : "none";
    if (preview)
      preview.style.display = diseasePreviewWasVisible ? "block" : "none";
  }

  const startBtn = el("leaf-camera-start");
  const stopBtn = el("leaf-camera-stop");
  const captureBtn = el("leaf-camera-capture");
  if (startBtn) startBtn.style.display = "inline-block";
  if (stopBtn) stopBtn.style.display = "none";
  if (captureBtn) captureBtn.style.display = "none";
}

async function analyseLeafImage() {
  if (!leafImageB64) return;
  const crop = el("leaf-crop-select")
    ? el("leaf-crop-select").value
    : "unknown crop";

  // Show user message with image thumbnail
  appendMsg(
    "user",
    `<img src="data:${leafMimeType};base64,${leafImageB64}" style="max-width:180px;max-height:120px;border-radius:6px;display:block;margin-bottom:.4rem">` +
      `<span>🔬 Analysing ${crop} leaf for disease…</span>`,
  );

  setBusy(true);

  try {
    const r = await fetch(apiUrl("/api/chat/analyse-image"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image: leafImageB64,
        mime_type: leafMimeType,
        crop: crop,
        messages: chatHistory.slice(-4),
      }),
    });
    const d = await r.json();

    if (!r.ok || d.error) {
      appendBotMsg(
        "Sorry sir, This feature is not available at this moment.",
        true,
      );
    } else {
      const formatted = formatMarkdown(d.reply || "");
      appendBotMsg(formatted);
      // Add to history as text (not re-sending image each time)
      chatHistory.push({ role: "user", content: `[Leaf image of ${crop}]` });
      chatHistory.push({ role: "assistant", content: d.reply });
    }
  } catch (err) {
    appendBotMsg(
      "Sorry sir, This feature is not available at this moment.",
      true,
    );
  }

  setBusy(false);
  clearLeafImage();
}

function setVoiceStatus(msg, isError = false) {
  const status = el("chat-voice-status");
  if (!status) return;
  status.textContent = msg || "";
  status.style.color = isError ? "var(--danger)" : "var(--text3)";
}

function setVoiceButtonState(recording) {
  const btn = el("chat-voice");
  if (!btn) return;
  btn.textContent = recording ? "⏹" : "🎤";
  btn.title = recording ? "Stop Voice Recording" : "Voice Command";
  btn.style.background = recording ? "var(--danger)" : "var(--accent)";
}

function mergeFloatBuffers(buffers, totalLength) {
  const out = new Float32Array(totalLength);
  let offset = 0;
  for (const b of buffers) {
    out.set(b, offset);
    offset += b.length;
  }
  return out;
}

function floatTo16BitPCM(view, offset, input) {
  for (let i = 0; i < input.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
}

function writeWavHeader(view, sampleRate, numSamples) {
  const writeStr = (off, str) => {
    for (let i = 0; i < str.length; i++)
      view.setUint8(off + i, str.charCodeAt(i));
  };

  const bytesPerSample = 2;
  const dataSize = numSamples * bytesPerSample;

  writeStr(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, dataSize, true);
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeWavHeader(view, sampleRate, samples.length);
  floatTo16BitPCM(view, 44, samples);
  return buffer;
}

function arrayBufferToBase64(buffer) {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode.apply(null, chunk);
  }
  return btoa(binary);
}

async function transcribeVoiceWav(wavB64) {
  try {
    const r = await fetch(apiUrl("/api/chat/transcribe"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audio: wavB64, mime_type: "audio/wav" }),
    });
    const d = await r.json();

    if (!r.ok || d.error) {
      setVoiceStatus(
        d.message || d.error || "Voice transcription failed.",
        true,
      );
      return;
    }

    const text = (d.text || "").trim();
    if (!text) {
      setVoiceStatus(
        "No clear speech detected. Try speaking closer to the mic.",
        true,
      );
      return;
    }

    const input = el("chat-input");
    const current = (input.value || "").trim();
    input.value = current ? `${current} ${text}` : text;
    autoResize(input);
    input.focus();
    setVoiceStatus("Voice captured. You can edit text and press send.");
  } catch (err) {
    setVoiceStatus(
      "Voice transcription failed. Check connection and try again.",
      true,
    );
  }
}

async function startVoiceCapture() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setVoiceStatus("Microphone is not supported in this browser.", true);
    return;
  }

  try {
    voiceStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    voiceCtx = new AudioCtx();
    voiceSource = voiceCtx.createMediaStreamSource(voiceStream);
    voiceProcessor = voiceCtx.createScriptProcessor(4096, 1, 1);
    voiceBuffers = [];
    voiceLength = 0;

    voiceProcessor.onaudioprocess = (e) => {
      if (!voiceActive) return;
      const input = e.inputBuffer.getChannelData(0);
      const copy = new Float32Array(input.length);
      copy.set(input);
      voiceBuffers.push(copy);
      voiceLength += copy.length;
    };

    voiceSource.connect(voiceProcessor);
    voiceProcessor.connect(voiceCtx.destination);

    voiceActive = true;
    setVoiceButtonState(true);
    setVoiceStatus("Listening... click the stop button when done.");
  } catch (err) {
    setVoiceStatus("Microphone access denied or unavailable.", true);
  }
}

async function stopVoiceCapture() {
  try {
    voiceActive = false;
    setVoiceButtonState(false);

    if (voiceProcessor) {
      voiceProcessor.disconnect();
      voiceProcessor.onaudioprocess = null;
    }
    if (voiceSource) voiceSource.disconnect();
    if (voiceStream) voiceStream.getTracks().forEach((t) => t.stop());

    const sampleRate = voiceCtx ? voiceCtx.sampleRate : 16000;
    if (voiceCtx) await voiceCtx.close();

    const total = voiceLength;
    if (!total) {
      setVoiceStatus("No audio captured. Try again.", true);
      return;
    }

    setVoiceStatus("Processing voice...", false);
    const merged = mergeFloatBuffers(voiceBuffers, total);
    const wavBuffer = encodeWav(merged, sampleRate);
    const wavB64 = arrayBufferToBase64(wavBuffer);
    await transcribeVoiceWav(wavB64);
  } catch (err) {
    setVoiceStatus("Failed to process voice recording.", true);
  } finally {
    voiceCtx = null;
    voiceSource = null;
    voiceProcessor = null;
    voiceStream = null;
    voiceBuffers = [];
    voiceLength = 0;
  }
}

function toggleVoiceInput() {
  if (chatBusy) return;
  if (voiceActive) {
    stopVoiceCapture();
  } else {
    startVoiceCapture();
  }
}

// ── Streaming text chat with retry logic ───────────────────────────────────
async function sendChat() {
  if (chatBusy) return;
  if (voiceActive) {
    setVoiceStatus("Stop voice recording before sending.", true);
    return;
  }
  const input = el("chat-input");
  const text = input.value.trim();
  if (!text) return;

  appendMsg("user", escHtml(text));
  chatHistory.push({ role: "user", content: text });
  input.value = "";
  input.style.height = "auto";
  setBusy(true);

  // Create bot message bubble for streaming into
  const msgDiv = createBotMsgDiv();

  // Retry logic with exponential backoff
  const MAX_RETRIES = 3;
  let attempt = 0;
  let lastError = null;

  while (attempt < MAX_RETRIES) {
    try {
      attempt++;
      const lat = +el("w-lat").value || 30.2139;
      const lon = +el("w-lon").value || 78.174;
      const city = el("w-city-lbl")?.textContent || "Dehradun";

      const r = await fetch(apiUrl("/api/chat/stream"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: chatHistory,
          session_id: S.session_id,
          location: { city, latitude: lat, longitude: lon },
        }),
      });

      // Handle 429 (rate limit) - wait and retry
      if (r.status === 429) {
        const d = await r.json().catch(() => ({}));
        const waitTime = d.retry_after || attempt * 1.5; // exponential backoff
        msgDiv.innerHTML = `⏳ Rate limited. Retrying in ${Math.ceil(waitTime)}s... (attempt ${attempt}/${MAX_RETRIES})`;
        scrollChat();
        await new Promise((res) => setTimeout(res, waitTime * 1000));
        continue; // retry
      }

      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        lastError = d.message || d.error || `Error ${r.status}`;
        if (r.status >= 500) {
          // Server error - retry
          if (attempt < MAX_RETRIES) {
            const waitTime = attempt * 1.5;
            msgDiv.innerHTML = `🔄 Server busy. Retrying in ${Math.ceil(waitTime)}s... (attempt ${attempt}/${MAX_RETRIES})`;
            scrollChat();
            await new Promise((res) => setTimeout(res, waitTime * 1000));
            continue;
          }
        }
        // Client error - don't retry
        msgDiv.textContent = "⚠️ " + escHtml(lastError);
        msgDiv.classList.add("error");
        setBusy(false);
        return;
      }

      // Success - read SSE stream
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let fullReply = "";
      msgDiv.classList.add("streaming-cursor");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (data === "[DONE]") break;
          try {
            const parsed = JSON.parse(data);
            if (parsed.error) {
              const errMsg = parsed.error || "";
              if (
                errMsg.includes("rate limit") ||
                errMsg.includes("Rate limit") ||
                errMsg.includes("⏳")
              ) {
                showRateLimitCountdown(msgDiv, 60, (html) => {
                  msgDiv.innerHTML = html;
                });
              } else {
                msgDiv.innerHTML = escHtml(errMsg);
                msgDiv.classList.add("error");
              }
              fullReply = "";
              break;
            }
            if (false) {
              let _dummy = msgDiv.classList.add("error");
              fullReply = "";
              break;
            }
            if (parsed.text) {
              fullReply += parsed.text;
              msgDiv.innerHTML = formatMarkdown(fullReply);
              msgDiv.classList.add("streaming-cursor");
              scrollChat();
            }
          } catch (_) {}
        }
      }

      msgDiv.classList.remove("streaming-cursor");
      if (fullReply) {
        chatHistory.push({ role: "assistant", content: fullReply });
        if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);
      }
      break; // Success - exit retry loop
    } catch (err) {
      lastError = err.message;
      if (attempt < MAX_RETRIES) {
        const waitTime = attempt * 1.5;
        msgDiv.innerHTML = `🔄 Connection interrupted. Retrying in ${Math.ceil(waitTime)}s... (attempt ${attempt}/${MAX_RETRIES})`;
        scrollChat();
        await new Promise((res) => setTimeout(res, waitTime * 1000));
        continue;
      }
    }
  }

  if (attempt >= MAX_RETRIES && lastError) {
    msgDiv.textContent = `⚠️ Failed after ${MAX_RETRIES} attempts. Check your API key and internet connection.`;
    msgDiv.classList.add("error");
  }

  setBusy(false);
  input.focus();
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function setBusy(busy) {
  chatBusy = busy;
  const btn = el("chat-send");
  const voiceBtn = el("chat-voice");
  if (btn) btn.disabled = busy;
  if (voiceBtn) voiceBtn.disabled = busy;
  el("chat-typing").style.display = busy ? "block" : "none";
  scrollChat();
}

function scrollChat() {
  const c = el("chat-messages");
  if (c) c.scrollTop = c.scrollHeight;
}

function appendMsg(role, html) {
  const container = el("chat-messages");
  const wrap = document.createElement("div");
  wrap.className = `chat-msg ${role}`;
  const avatar = role === "user" ? "👤" : "🤖";
  wrap.innerHTML = `<div class="chat-avatar">${avatar}</div><div class="chat-bubble">${html}</div>`;
  container.appendChild(wrap);
  scrollChat();
}

function appendBotMsg(html, isError) {
  const container = el("chat-messages");
  const wrap = document.createElement("div");
  wrap.className = "chat-msg bot";
  wrap.innerHTML = `<div class="chat-avatar">🤖</div>
    <div class="chat-bubble${isError ? " error" : ""}">${html}</div>`;
  container.appendChild(wrap);
  scrollChat();
}

function createBotMsgDiv() {
  const container = el("chat-messages");
  const wrap = document.createElement("div");
  wrap.className = "chat-msg bot";
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  wrap.innerHTML = '<div class="chat-avatar">🤖</div>';
  wrap.appendChild(bubble);
  container.appendChild(wrap);
  scrollChat();
  return bubble;
}

function formatMarkdown(text) {
  return escHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/\*(.+?)\*/g, "<i>$1</i>")
    .replace(/^### (.+)$/gm, '<b style="font-size:13px">$1</b>')
    .replace(/^## (.+)$/gm, '<b style="font-size:14px">$1</b>')
    .replace(/^# (.+)$/gm, '<b style="font-size:15px">$1</b>')
    .replace(/^- (.+)$/gm, "• $1")
    .replace(/^\d+\. (.+)$/gm, "  $1")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ── RATE LIMIT COUNTDOWN TIMER ───────────────────────────────────────────────
function showRateLimitCountdown(element, seconds, updateFn) {
  let remaining = seconds;
  element.classList.add("error");
  const tick = () => {
    updateFn(
      `⏳ <b>Gemini rate limit reached</b> (free tier: 15 requests/min)<br>` +
        `<span style="font-size:12px">Auto-retrying in <b>${remaining}s</b>… ` +
        `<span style="color:var(--text3)">(or type a new message to try now)</span></span>`,
    );
    if (remaining > 0) {
      remaining--;
      setTimeout(tick, 1000);
    } else {
      element.innerHTML = "✅ Ready! You can send your message now.";
      element.classList.remove("error");
      element.style.background = "#f0fdf4";
      setTimeout(() => {
        element.style.background = "";
      }, 3000);
    }
  };
  tick();
}

// ── MOBILE SIDEBAR ────────────────────────────────────────────────────────────
function toggleSidebar() {
  el("sidebar").classList.toggle("open");
}
function checkMobile() {
  const btn = el("menu-btn");
  if (btn) btn.style.display = window.innerWidth <= 768 ? "block" : "none";
}
window.addEventListener("resize", checkMobile);
checkMobile();

// ── KEYBOARD SHORTCUTS ────────────────────────────────────────────────────────
const KB = {
  1: "dashboard",
  2: "sensors",
  3: "weather",
  4: "crop",
  5: "disease",
  6: "soil",
  7: "maps",
  8: "analytics",
  9: "aichat",
};
document.addEventListener("keydown", (e) => {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
  if (KB[e.key]) goTab(KB[e.key]);
  if (e.key === "r" || e.key === "R") {
    pollSensors();
    pollAlerts();
  }
  if (e.key === "e" || e.key === "E") exportCSV();
  if (e.key === "?")
    alert(
      "Keyboard shortcuts:\n1-9  Switch tabs\nR    Refresh sensors\nE    Export CSV\n?    Show this help",
    );
});

// ── GEOLOCATION ──────────────────────────────────────────────────────────────
let geoGranted = false;

// ── setAllLocationText — single function to update EVERY location text ────────
function setAllLocationText(city, cityShort, lat, lon) {
  // Sidebar widget
  set("loc-city-name", cityShort);
  set("loc-coords", `${lat.toFixed(5)}°N, ${lon.toFixed(5)}°E`);
  // Sidebar footer
  set("footer-city", cityShort);
  // Topbar pills
  set("tw-city", cityShort);
  set("topbar-city-pill", cityShort);
  // Weather banner inside text
  set("wb-banner-loc", city);
  // Weather tab forecast label
  set("w-city-lbl", city);
  // Weather form inputs
  const wlat = el("w-lat");
  if (wlat) wlat.value = lat;
  const wlon = el("w-lon");
  if (wlon) wlon.value = lon;
}

// ── onLocationUpdate: called whenever GPS coords change ───────────────────────
async function onLocationUpdate(lat, lon) {
  // 1. Save to global state
  S.lat = lat;
  S.lon = lon;

  // 2. Show interim "locating..." state with coords
  const coordStr = `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E`;
  set("loc-status", "🔄 Locating city...");
  set("loc-city-name", coordStr);
  set("loc-coords", `${lat.toFixed(5)}°N, ${lon.toFixed(5)}°E`);

  // 3. Accurate reverse geocode (BigDataCloud → OSM Nominatim fallback)
  const geo = await api(`/api/weather/geocode_reverse?lat=${lat}&lon=${lon}`);
  const city = geo && geo.city ? geo.city : coordStr;
  const cityShort =
    geo && geo.city_short ? geo.city_short : city.split(",")[0].trim();
  S.city = city;

  // 4. Update EVERY location display in one call
  setAllLocationText(city, cityShort, lat, lon);
  set(
    "loc-status",
    geo && geo.source ? `🟢 via ${geo.source}` : "🟢 GPS located",
  );

  // 5. Refresh all live data for the new location
  console.info(`📍 Location → ${city} (${lat}, ${lon})`);
  await Promise.all([loadWeatherBanner(), pollSensors(), pollAlerts()]);
}

// ── MANUAL LOCATION INPUT ──────────────────────────────────────────────────────
function openLocationModal() {
  el("location-modal").style.display = "flex";
}

function closeLocationModal() {
  el("location-modal").style.display = "none";
}

function switchLocTab(tab) {
  ["name", "coords", "saved"].forEach((t) => {
    const panel = el(`loc-tab-${t}`);
    const btn = document.querySelector(
      `.loc-tab-btn:nth-child(${t === "name" ? 1 : t === "coords" ? 2 : 3})`,
    );
    if (panel) panel.style.display = t === tab ? "block" : "none";
    if (btn) {
      btn.style.color = t === tab ? "#2dd4bf" : "#888";
      btn.style.borderBottomColor = t === tab ? "#2dd4bf" : "transparent";
    }
  });
}

async function searchLocationByName() {
  const name = el("loc-search-name").value.trim();
  if (!name) {
    htm(
      "loc-search-result",
      '<p style="color:#888;font-size:12px">Enter a city name</p>',
    );
    return;
  }

  htm(
    "loc-search-result",
    '<p style="color:#888;font-size:12px">🔍 Searching...</p>',
  );
  const d = await api("/api/weather/geocode?city=" + encodeURIComponent(name));
  if (!d || d.error) {
    htm(
      "loc-search-result",
      '<p style="color:#dc2626;font-size:12px">❌ City not found</p>',
    );
    return;
  }

  htm(
    "loc-search-result",
    `
    <div style="background:#222;padding:1rem;border-radius:8px;border:1px solid #2dd4bf;cursor:pointer" onclick="selectLocation(${d.latitude}, ${d.longitude}, '${d.city}')">
      <div style="color:#2dd4bf;font-weight:600;font-size:13px">✓ ${d.city}</div>
      <div style="color:#888;font-size:11px;margin-top:0.3rem">Lat: ${d.latitude.toFixed(5)}° Lon: ${d.longitude.toFixed(5)}°</div>
      <div style="color:#666;font-size:10px;margin-top:0.2rem">geocoding</div>
    </div>
  `,
  );
}

async function applyCoordinates() {
  const lat = parseFloat(el("loc-input-lat").value);
  const lon = parseFloat(el("loc-input-lon").value);
  if (
    isNaN(lat) ||
    isNaN(lon) ||
    lat < -90 ||
    lat > 90 ||
    lon < -180 ||
    lon > 180
  ) {
    alert("Invalid coordinates. Lat: -90 to 90, Lon: -180 to 180");
    return;
  }
  selectLocation(lat, lon, "Custom Location");
}

async function selectLocation(lat, lon, city) {
  closeLocationModal();
  await onLocationUpdate(lat, lon);
}

// ── MANUAL LOCATION INPUT ──────────────────────────────────────────────────────
async function updateLocationFromInput() {
  const input = el("manual-city").value.trim();
  if (!input) {
    alert("Please enter a city name or coordinates (lat, lon)");
    return;
  }

  // Check if it's coordinates or city name
  if (input.includes(",")) {
    // Try parsing as coordinates
    const parts = input.split(",").map((s) => parseFloat(s.trim()));
    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
      const lat = parts[0];
      const lon = parts[1];
      if (lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
        el("manual-city").value = "";
        await onLocationUpdate(lat, lon);
        return;
      }
    }
  }

  // Search as city name
  const d = await api("/api/weather/geocode?city=" + encodeURIComponent(input));
  if (!d || d.error) {
    alert("City not found. Try: Dehradun, Agra, Bangalore, etc.");
    return;
  }
  el("manual-city").value = "";
  S.city = d.city;
  await onLocationUpdate(d.latitude, d.longitude);
}

// ── HARDWARE SENSOR MANAGEMENT ───────────────────────────────────────────────────
let hwScanTimer = null;

async function isHardwareActuallyActive() {
  const status = await api("/api/hardware/status");
  const sensors = await api(`/api/sensors?lat=${S.lat}&lon=${S.lon}`);

  if (!status || !sensors) return false;

  // Require both connection status and hardware-backed sensor source.
  return Boolean(
    status.connected &&
    sensors.hardware_connected &&
    String(sensors.source || "").toLowerCase() === "hardware",
  );
}

async function scanHardware() {
  const btn = el("connect-btn");
  const hwSection = el("hardware-section");
  const hwStatusText = el("hw-status-text");
  const hwStatusSub = el("hw-status-sub");
  const hwStatusIcon = el("hw-status-icon");

  btn.disabled = true;
  let countdown = 5;
  hwStatusText.textContent = "Scanning...";
  hwStatusSub.textContent = `Searching for sensors (${countdown}s)`;
  hwStatusIcon.textContent = "🔍";

  // Countdown timer
  hwScanTimer = setInterval(() => {
    countdown--;
    if (countdown >= 0) {
      hwStatusSub.textContent = `Searching for sensors (${countdown}s)`;
    }
  }, 1000);

  // Wait 5 seconds to simulate scanning
  await new Promise((res) => setTimeout(res, 5000));
  clearInterval(hwScanTimer);

  // Check if hardware actually exists (call API to trigger simulated detection)
  const d = await api("/api/hardware/connect", {
    method: "POST",
    body: JSON.stringify({
      device: "Auto-Detected Sensor",
      connection_type: "usb",
    }),
  });

  if (d && d.success) {
    // Double-check with live sensor source before showing connected state.
    const active = await isHardwareActuallyActive();
    if (active) {
      hwStatusIcon.textContent = "✅";
      hwStatusText.textContent = "HARDWARE SENSOR CONNECTED (USB)";
      hwStatusSub.textContent = `Device: ${d.status.device}`;
      el("hw-badge").style.display = "block";
      el("hw-badge").textContent = "✓ CONNECTED VIA USB";
      el("disconnect-btn").style.display = "inline-block";
      btn.style.display = "none";
      showHardwareReadings();
    } else {
      await api("/api/hardware/disconnect", { method: "POST" });
      hwStatusIcon.textContent = "❌";
      hwStatusText.textContent = "No Hardware Detected";
      hwStatusSub.textContent = "Sensor not responding. Using simulated data.";
      el("hw-badge").style.display = "none";
      el("disconnect-btn").style.display = "none";
      btn.style.display = "inline-block";
      el("hw-readings").innerHTML = "";
    }
  } else {
    // No hardware found
    hwStatusIcon.textContent = "❌";
    hwStatusText.textContent = "No Hardware Detected";
    hwStatusSub.textContent = "Connect a USB or Bluetooth sensor to continue";
    el("hw-badge").style.display = "none";
    el("disconnect-btn").style.display = "none";
    btn.style.display = "inline-block";
  }

  btn.disabled = false;
}

async function showHardwareReadings() {
  const hwReadings = el("hw-readings");
  if (!hwReadings) return;

  // Fetch fresh sensor data
  const d = await api(`/api/sensors?lat=${S.lat}&lon=${S.lon}`);
  if (!d) return;

  const readings = [
    { label: "🌡️ Temperature", value: d.temperature + "°C" },
    { label: "🌫️ Humidity", value: d.humidity + "%" },
    { label: "💧 Soil Moisture", value: d.soil_moisture + "%" },
    { label: "⚗️ pH Level", value: d.ph_level },
  ];

  hwReadings.innerHTML = readings
    .map(
      (r) =>
        `<div style="background:#222;padding:.6rem;border-radius:6px">
        <div style="font-size:11px;color:#888">${r.label}</div>
        <div style="font-size:16px;font-weight:700;color:#2dd4bf;margin-top:0.2rem">${r.value}</div>
      </div>`,
    )
    .join("");
}

async function disconnectHardware() {
  const d = await api("/api/hardware/disconnect", { method: "POST" });
  if (d && d.success) {
    // Hardware successfully disconnected
    el("hw-status-icon").textContent = "🔌";
    el("hw-status-text").textContent = "Disconnected";
    el("hw-status-sub").textContent =
      "No hardware connected. Using simulated data.";
    el("hw-badge").style.display = "none";
    el("disconnect-btn").style.display = "none";
    el("connect-btn").style.display = "inline-block";
    el("hw-readings").innerHTML = "";
    // Hide hardware section
    const hwSection = el("hardware-section");
    if (hwSection) hwSection.style.display = "none";
  } else {
    // If API fails, force local UI update anyway
    el("hw-status-icon").textContent = "🔌";
    el("hw-status-text").textContent = "Disconnected";
    el("hw-status-sub").textContent =
      "No hardware connected. Using simulated data.";
    el("hw-badge").style.display = "none";
    el("disconnect-btn").style.display = "none";
    el("connect-btn").style.display = "inline-block";
    el("hw-readings").innerHTML = "";
    const hwSection = el("hardware-section");
    if (hwSection) hwSection.style.display = "none";
  }
}

async function refreshHardwareStatus() {
  const d = await api("/api/hardware/status");
  if (!d) return;

  const hwSection = el("hardware-section");
  const active = d.connected ? await isHardwareActuallyActive() : false;
  if (active) {
    // Hardware is connected - show section
    hwSection.style.display = "block";
    el("hw-status-icon").textContent = "⚡";
    el("hw-status-text").textContent =
      `HARDWARE SENSOR CONNECTED (${d.connection_type.toUpperCase()})`;
    el("hw-status-sub").textContent = `Device: ${d.device}`;
    el("hw-badge").style.display = "block";
    el("hw-badge").textContent =
      `✓ CONNECTED VIA ${d.connection_type.toUpperCase()}`;
    el("disconnect-btn").style.display = "inline-block";
    el("connect-btn").style.display = "none";
    showHardwareReadings();
  } else {
    // Hardware is NOT connected - show section with disconnect option
    hwSection.style.display = "block";
    el("hw-status-icon").textContent = "🔌";
    el("hw-status-text").textContent = "Disconnected";
    el("hw-status-sub").textContent =
      "No hardware connected. Using simulated data.";
    el("hw-badge").style.display = "none";
    el("disconnect-btn").style.display = "none";
    el("connect-btn").style.display = "inline-block";
    el("hw-readings").innerHTML = "";
  }
}

function requestLocation() {
  if (!navigator.geolocation) {
    set("loc-status", "❌ GPS not supported");
    return;
  }
  set("loc-status", "🔄 Requesting GPS...");
  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      geoGranted = true;
      const lat = parseFloat(pos.coords.latitude.toFixed(6));
      const lon = parseFloat(pos.coords.longitude.toFixed(6));
      await onLocationUpdate(lat, lon);
    },
    (err) => {
      // User denied or error — silently stay on default location
      const msgs = {
        1: "🔒 Location denied — using default",
        2: "⚠️ GPS unavailable — using default",
        3: "⏱️ GPS timed out — using default",
      };
      set("loc-status", msgs[err.code] || "📍 Using default location");
      console.info("Geolocation:", err.message);
    },
    {
      enableHighAccuracy: true, // use GPS chip not just IP
      timeout: 10000,
      maximumAge: 30000, // accept cached position up to 30s old
    },
  );
}

// ── FERTILIZER RECOMMENDATIONS ────────────────────────────────────────────────
// Disease → fertilizer & treatment products map
const DISEASE_FERTILIZERS = {
  "Powdery Mildew": {
    fungicides: [
      "Sulfur-based spray (Kumulus DF)",
      "Myclobutanil (Eagle 20EW)",
      "Neem oil (Trilogy)",
    ],
    preventive:
      "Improve air circulation. Avoid overhead watering. Apply potassium silicate to strengthen cell walls.",
    npk_boost:
      "Reduce excess Nitrogen (promotes soft tissue). Boost Potassium (K) to improve plant immunity.",
    urgency: "warn",
  },
  "Leaf Spot": {
    fungicides: [
      "Chlorothalonil (Daconil)",
      "Mancozeb (Dithane M-45)",
      "Copper hydroxide (Kocide 3000)",
    ],
    preventive:
      "Remove infected leaves. Avoid wetting foliage. Rotate crops next season.",
    npk_boost:
      "Ensure adequate Phosphorus (P) and Potassium (K) for disease resistance.",
    urgency: "warn",
  },
  Rust: {
    fungicides: [
      "Propiconazole (Tilt 250E)",
      "Tebuconazole (Folicur)",
      "Azoxystrobin (Amistar)",
    ],
    preventive:
      "Remove volunteer plants. Apply at first sign of infection. Repeat every 7–14 days.",
    npk_boost:
      "Reduce excess Nitrogen. Apply Potassium (K) — potassium silicate sprays reduce rust severity.",
    urgency: "danger",
  },
  Blight: {
    fungicides: [
      "Metalaxyl + Mancozeb (Ridomil Gold MZ)",
      "Cymoxanil (Curzate)",
      "Dimethomorph (Forum)",
    ],
    preventive:
      "Destroy infected plants immediately. Avoid overhead irrigation. Improve drainage.",
    npk_boost:
      "Balanced NPK critical. Avoid excess Nitrogen. Boost Calcium and Potassium for cell wall strength.",
    urgency: "danger",
  },
  Wilt: {
    fungicides: [
      "Carbendazim (Bavistin)",
      "Thiram + Carbendazim (seed treatment)",
      "Trichoderma viride (bio-fungicide)",
    ],
    preventive:
      "Soil drenching with fungicide. Remove infected roots. Solarize soil before next crop.",
    npk_boost:
      "Improve soil drainage. Apply balanced NPK. Phosphorus (P) supports healthy root development.",
    urgency: "danger",
  },
  Healthy: {
    fungicides: [],
    preventive:
      "Continue current practices. Monitor weekly for early signs of disease.",
    npk_boost: "",
    urgency: "ok",
  },
};

// NPK low thresholds and their specific fertilizer recommendations
const NPK_FERTILIZERS = {
  nitrogen: {
    threshold: 50,
    products: [
      "Urea (46% N) — most economical",
      "Ammonium Nitrate (34% N)",
      "DAP — Diammonium Phosphate",
      "Calcium Ammonium Nitrate (CAN)",
    ],
    dose: "Apply 20–30 kg N/ha in split doses. First at planting, second at vegetative stage.",
    note: "Excess nitrogen promotes vegetative growth but reduces disease resistance.",
  },
  phosphorus: {
    threshold: 20,
    products: [
      "Single Super Phosphate (SSP — 16% P₂O₅)",
      "DAP — Diammonium Phosphate (46% P₂O₅)",
      "Rock Phosphate (for acidic soils)",
      "Bone meal (organic)",
    ],
    dose: "Apply 40–60 kg P₂O₅/ha at planting. Phosphorus is relatively immobile — incorporate into soil.",
    note: "Phosphorus is critical for root development and early plant establishment.",
  },
  potassium: {
    threshold: 100,
    products: [
      "Muriate of Potash — MOP (60% K₂O)",
      "Sulphate of Potash — SOP (50% K₂O, preferred for sensitive crops)",
      "Potassium Schoenite (organic source)",
      "Wood ash (organic, ~5–10% K)",
    ],
    dose: "Apply 40–60 kg K₂O/ha. Split between planting and flowering for best results.",
    note: "Potassium improves drought tolerance, disease resistance, and fruit quality.",
  },
};

function buildFertilizerSection(disease, sensorData) {
  const df = DISEASE_FERTILIZERS[disease] || DISEASE_FERTILIZERS["Healthy"];
  const isSick = disease !== "Healthy";
  const UC = { ok: "#16a34a", warn: "#d97706", danger: "#dc2626" };
  const color = UC[df.urgency] || "#2563eb";

  // Disease-based fungicide recommendations
  let html = "";
  if (isSick && df.fungicides.length > 0) {
    html += `
      <div style="margin-top:1rem;padding:1rem;background:linear-gradient(135deg,#fef2f2,#fff7ed);border:1px solid ${color}33;border-radius:12px">
        <div style="font-size:12px;font-weight:700;color:${color};text-transform:uppercase;letter-spacing:.8px;margin-bottom:.6rem">
          💊 Recommended Fungicides / Treatments
        </div>
        ${df.fungicides
          .map(
            (f) => `
          <div style="display:flex;gap:.5rem;align-items:flex-start;padding:.4rem .5rem;background:rgba(255,255,255,.7);border-radius:6px;margin-bottom:.3rem;font-size:12px">
            <span style="color:${color};flex-shrink:0">●</span>
            <span style="color:#1a1a1a;font-weight:500">${f}</span>
          </div>`,
          )
          .join("")}
        <div style="font-size:11px;color:#6b7280;margin-top:.6rem;padding:.5rem;background:rgba(255,255,255,.5);border-radius:6px">
          🛡️ <b>Prevention:</b> ${df.preventive}
        </div>
        ${df.npk_boost ? `<div style="font-size:11px;color:#d97706;margin-top:.4rem">🌿 <b>Nutrient tip:</b> ${df.npk_boost}</div>` : ""}
      </div>`;
  }

  // NPK-based fertilizer recommendations from live sensor data
  if (sensorData) {
    const npkRecs = [];
    const n = sensorData.nitrogen,
      p = sensorData.phosphorus,
      k = sensorData.potassium;

    if (n < NPK_FERTILIZERS.nitrogen.threshold) {
      npkRecs.push({
        label: `Low Nitrogen (${n} mg/kg)`,
        ...NPK_FERTILIZERS.nitrogen,
        color: "#166534",
        bg: "#f0fdf4",
      });
    }
    if (p < NPK_FERTILIZERS.phosphorus.threshold) {
      npkRecs.push({
        label: `Low Phosphorus (${p} mg/kg)`,
        ...NPK_FERTILIZERS.phosphorus,
        color: "#1e40af",
        bg: "#eff6ff",
      });
    }
    if (k < NPK_FERTILIZERS.potassium.threshold) {
      npkRecs.push({
        label: `Low Potassium (${k} mg/kg)`,
        ...NPK_FERTILIZERS.potassium,
        color: "#7c2d12",
        bg: "#fff7ed",
      });
    }

    if (npkRecs.length > 0) {
      html += `<div style="margin-top:1rem">
        <div style="font-size:12px;font-weight:700;color:#4a4a4a;text-transform:uppercase;letter-spacing:.8px;margin-bottom:.6rem">
          🌱 NPK Fertilizer Recommendations
        </div>
        ${npkRecs
          .map(
            (rec) => `
          <div style="padding:.85rem 1rem;background:${rec.bg};border:1px solid ${rec.color}22;border-radius:10px;margin-bottom:.6rem">
            <div style="font-size:12px;font-weight:700;color:${rec.color};margin-bottom:.4rem">⚠️ ${rec.label}</div>
            <div style="font-size:11px;color:#374151;margin-bottom:.4rem;font-weight:600">Recommended Products:</div>
            ${rec.products
              .map(
                (p) => `
              <div style="font-size:11px;color:#1a1a1a;padding:.25rem .5rem;background:rgba(255,255,255,.7);border-radius:5px;margin-bottom:.2rem">
                🔹 ${p}
              </div>`,
              )
              .join("")}
            <div style="font-size:11px;color:#6b7280;margin-top:.5rem">📋 <b>Dosage:</b> ${rec.dose}</div>
            <div style="font-size:11px;color:#9333ea;margin-top:.3rem">💡 ${rec.note}</div>
          </div>`,
          )
          .join("")}
      </div>`;
    } else if (!isSick) {
      html += `<div style="margin-top:.75rem;padding:.75rem 1rem;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;font-size:12px;color:#166534">
        ✅ NPK levels are within optimal range — no fertilizer addition needed right now.
      </div>`;
    }
  }

  return html;
}

// ── INIT ──────────────────────────────────────────────────────────────────────
// Define initApp function
async function initApp() {
  try {
    await Promise.all([loadWeatherBanner(), pollSensors(), pollAlerts()]);
    initDashChart();
    refreshHardwareStatus();
    requestLocation();
  } catch (e) {
    console.error("Init error:", e);
  }

  // Polling intervals
  setInterval(pollSensors, 60000);
  setInterval(pollAlerts, 10000);
  setInterval(loadWeatherBanner, 300000);

  // Sensors tab hardware refresh
  document
    .querySelector("[data-tab='sensors']")
    ?.addEventListener("click", refreshHardwareStatus);
}

// Initialize on page load OR immediately if already loaded
if (document.readyState === "loading") {
  window.addEventListener("load", initApp);
} else {
  initApp();
}
