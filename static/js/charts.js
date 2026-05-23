'use strict';
/**
 * static/js/charts.js
 * Reusable Chart.js factory functions for AgriTech v3.
 * All chart creation and update logic lives here.
 */

const AgriCharts = (() => {

  // ── Shared Chart.js options ────────────────────────────────────────────────
  function baseOpts() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      plugins: {
        legend: {
          labels: {
            color: '#888',
            font: { family: 'Plus Jakarta Sans', size: 11 },
            boxWidth: 10,
          },
        },
        tooltip: {
          backgroundColor: 'rgba(255,255,255,0.95)',
          titleColor: '#1a1a1a',
          bodyColor: '#4a4a4a',
          borderColor: '#e8dfc8',
          borderWidth: 1,
        },
      },
    };
  }

  function yAxis(opts = {}) {
    return {
      grid:  { color: 'rgba(0,0,0,0.05)' },
      ticks: { color: '#aaa', font: { family: 'Plus Jakarta Sans', size: 10 }, ...opts },
    };
  }

  function xAxis(opts = {}) {
    return {
      grid:  { color: 'rgba(0,0,0,0.03)' },
      ticks: { color: '#aaa', font: { family: 'Plus Jakarta Sans', size: 10 }, maxTicksLimit: 8, ...opts },
    };
  }

  // ── 24-Hour Dashboard Trend Chart ─────────────────────────────────────────
  function createDashChart(canvasId, data) {
    const pts    = data.slice(-48);
    const labels = pts.map(p =>
      new Date(p.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
    );
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Temp °C',    data: pts.map(p => p.temperature),  borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,.07)',  borderWidth: 2, pointRadius: 0, tension: 0.4 },
          { label: 'Moisture %', data: pts.map(p => p.soil_moisture), borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,.07)',  borderWidth: 2, pointRadius: 0, tension: 0.4 },
        ],
      },
      options: { ...baseOpts(), scales: { y: yAxis(), x: xAxis() } },
    });
  }

  // ── Sensor Comparison Bar Chart ────────────────────────────────────────────
  function createSensorChart(canvasId) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx.getContext('2d'), {
      type: 'bar',
      data: {
        labels: [],
        datasets: [{
          data: [],
          backgroundColor: [
            'rgba(45,106,79,.55)',
            'rgba(37,99,235,.55)',
            'rgba(8,145,178,.55)',
            'rgba(147,51,234,.55)',
          ],
          borderRadius: 6,
        }],
      },
      options: {
        ...baseOpts(),
        plugins: { legend: { display: false } },
        scales: { y: yAxis(), x: xAxis() },
      },
    });
  }

  function updateSensorChart(chart, labels, values) {
    if (!chart) return;
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.update('none');
  }

  // ── Multi-sensor Analytics Trend Chart ────────────────────────────────────
  function createTrendChart(canvasId, data) {
    const pts    = data.slice(-48);
    const labels = pts.map(p =>
      new Date(p.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
    );
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Temperature', data: pts.map(p => p.temperature),  borderColor: '#ef4444', borderWidth: 2, pointRadius: 0, tension: 0.4, fill: false },
          { label: 'Moisture',    data: pts.map(p => p.soil_moisture), borderColor: '#2563eb', borderWidth: 2, pointRadius: 0, tension: 0.4, fill: false },
          { label: 'Humidity',    data: pts.map(p => p.humidity),      borderColor: '#0891b2', borderWidth: 2, pointRadius: 0, tension: 0.4, fill: false },
        ],
      },
      options: { ...baseOpts(), scales: { y: yAxis(), x: xAxis() } },
    });
  }

  // ── Farm Health Donut Chart ────────────────────────────────────────────────
  let _donut = null;

  function updateDonut(canvasId, score) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const color = score >= 70 ? '#16a34a' : score >= 40 ? '#d97706' : '#dc2626';
    if (_donut) _donut.destroy();
    _donut = new Chart(canvas.getContext('2d'), {
      type: 'doughnut',
      data: {
        datasets: [{
          data: [score, 100 - score],
          backgroundColor: [color, '#f3f4f6'],
          borderWidth: 0,
          circumference: 270,
          rotation: -135,
        }],
      },
      options: {
        responsive: false,
        plugins: { legend: { display: false } },
        cutout: '76%',
      },
    });
    return _donut;
  }

  // ── Weather Forecast Chart ─────────────────────────────────────────────────
  function createWeatherChart(canvasId, forecast) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx.getContext('2d'), {
      type: 'line',
      data: {
        labels: forecast.map(f => f.date),
        datasets: [
          { label: 'Max Temp', data: forecast.map(f => f.temp_max),                   borderColor: '#ef4444', borderWidth: 2, pointRadius: 3, tension: 0.4, fill: false },
          { label: 'Min Temp', data: forecast.map(f => f.temp_min),                   borderColor: '#fb923c', borderWidth: 1.5, pointRadius: 2, tension: 0.4, fill: false, borderDash: [4, 3] },
          { label: 'Humidity', data: forecast.map(f => f.humidity),                   borderColor: '#2563eb', borderWidth: 1.5, pointRadius: 2, tension: 0.4 },
          { label: 'Rain %',   data: forecast.map(f => f.rainfall_probability * 100), borderColor: '#16a34a', borderWidth: 1.5, pointRadius: 2, tension: 0.4 },
        ],
      },
      options: { ...baseOpts(), scales: { y: yAxis(), x: xAxis() } },
    });
  }

  // ── Irrigation Water Usage Bar Chart ─────────────────────────────────────
  function createIrrigationChart(canvasId, zones) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx.getContext('2d'), {
      type: 'bar',
      data: {
        labels: zones.map(z => z.name),
        datasets: [{
          label: 'Litres Used Today',
          data:            zones.map(z => z.liters),
          backgroundColor: zones.map(z => z.active ? 'rgba(22,163,74,.55)' : 'rgba(209,213,219,.55)'),
          borderColor:     zones.map(z => z.active ? '#16a34a' : '#9ca3af'),
          borderWidth: 1,
          borderRadius: 7,
        }],
      },
      options: {
        ...baseOpts(),
        plugins: { legend: { display: false } },
        scales: { y: yAxis(), x: xAxis() },
      },
    });
  }

  function updateIrrigationChart(chart, zones) {
    if (!chart) return;
    chart.data.labels                          = zones.map(z => z.name);
    chart.data.datasets[0].data              = zones.map(z => z.liters);
    chart.data.datasets[0].backgroundColor   = zones.map(z => z.active ? 'rgba(22,163,74,.55)' : 'rgba(209,213,219,.55)');
    chart.data.datasets[0].borderColor       = zones.map(z => z.active ? '#16a34a' : '#9ca3af');
    chart.update();
  }

  // ── Public API ─────────────────────────────────────────────────────────────
  return {
    createDashChart,
    createSensorChart,
    updateSensorChart,
    createTrendChart,
    updateDonut,
    createWeatherChart,
    createIrrigationChart,
    updateIrrigationChart,
  };

})();

window.AgriCharts = AgriCharts;
