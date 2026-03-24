/**
 * dashboard.js

 * Fetches data from Flask API endpoints and renders Chart.js charts.

 * Flow:
 * 1. Page loads → initDashboard() runs
 * 2. We fetch JSON from /api/stats, /api/flights/by-county, etc.
 * 3. We pass the data to Chart.js to render the charts
 * 4. A timer refreshes all data every 60 seconds

 * fetch() is the browser's built-in HTTP client. It returns a Promise
 * (an async value). We use async/await to write it like synchronous code.
 */


// Helpers


/**
 * Fetch JSON from a local API endpoint.
 * @param {string} path - e.g. "/api/stats"
 * @returns {Promise<any>} parsed JSON
 */
async function apiFetch(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`API error: ${res.status} ${path}`);
  return res.json();
}

// Shared Chart.js default colors (Catppuccin Mocha palette)
const COLORS = [
  "#89b4fa", "#a6e3a1", "#fab387", "#f38ba8",
  "#cba6f7", "#94e2d5", "#f9e2af", "#74c7ec"
];

// Store chart instances so we can destroy and recreate them on refresh
const charts = {};



// KPI cards


async function loadKPIs() {
  const data = await apiFetch("/api/stats");
  document.getElementById("kpi-total-flights").textContent =
    data.total_flights.toLocaleString();
  document.getElementById("kpi-active-flights").textContent =
    data.active_flights.toLocaleString();
  document.getElementById("kpi-registrations").textContent =
    data.total_registrations.toLocaleString();
  document.getElementById("kpi-incidents").textContent =
    data.total_incidents.toLocaleString();
}


// Bar chart: flights by county


async function loadCountyChart() {
  const data = await apiFetch("/api/flights/by-county");

  // Limit to top 10 counties to keep the chart readable
  const top10 = data.slice(0, 10);
  const labels = top10.map(d => d.county);
  const counts = top10.map(d => d.count);

  // Destroy old chart if it exists (avoid "Canvas already in use" error)
  if (charts.county) charts.county.destroy();

  const ctx = document.getElementById("countyChart").getContext("2d");
  charts.county = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Flight Records",
        data: counts,
        backgroundColor: COLORS[0],
        borderRadius: 6
      }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#a6adc8" }, grid: { color: "#45475a" } },
        y: { ticks: { color: "#a6adc8" }, grid: { color: "#45475a" } }
      }
    }
  });
}



// Pie chart: commercial vs recreational


async function loadPurposeChart() {
  const data = await apiFetch("/api/registrations/by-purpose");
  const labels = data.map(d => d.purpose || "Unknown");
  const counts = data.map(d => d.count);

  if (charts.purpose) charts.purpose.destroy();

  const ctx = document.getElementById("purposeChart").getContext("2d");
  charts.purpose = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: counts,
        backgroundColor: [COLORS[0], COLORS[1], COLORS[2]],
        borderWidth: 0
      }]
    },
    options: {
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#a6adc8", padding: 12 }
        }
      }
    }
  });
}



// Histogram: altitude distribution


async function loadAltitudeChart() {
  const data = await apiFetch("/api/flights/altitude-distribution");
  const labels = data.map(d => d.range);
  const counts = data.map(d => d.count);

  if (charts.altitude) charts.altitude.destroy();

  const ctx = document.getElementById("altitudeChart").getContext("2d");
  charts.altitude = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Number of Flights",
        data: counts,
        backgroundColor: COLORS[2],
        borderRadius: 6
      }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#a6adc8" }, grid: { color: "#45475a" } },
        y: { ticks: { color: "#a6adc8" }, grid: { color: "#45475a" } }
      }
    }
  });
}



// Main init


async function initDashboard() {
  try {
    // Run all fetches in parallel — Promise.all waits for all of them
    await Promise.all([
      loadKPIs(),
      loadCountyChart(),
      loadPurposeChart(),
      loadAltitudeChart()
    ]);
    console.log("Dashboard loaded successfully");
  } catch (err) {
    console.error("Dashboard load error:", err);
  }
}

// Run on page load
initDashboard();

// Auto-refresh every 60 seconds
setInterval(initDashboard, 60_000);
