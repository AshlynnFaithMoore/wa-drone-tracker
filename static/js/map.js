/**
 * map.js

 * Powers the interactive Leaflet.js flight map.
 *
 * Responsibilities:
 * - Initialize the Leaflet map centered on Washington State
 * - Fetch flight records from /api/flights/recent
 * - Draw a colored circle marker for each flight
 * - Show a detail popup on marker click
 * - Support county filter, altitude slider, and heatmap toggle
 * - Auto-refresh every 60 seconds
 */


// Map initialization


/**
 * L is the global Leaflet object (loaded from the CDN script tag).
 * L.map("map") attaches Leaflet to the <div id="map"> element.
 * setView([lat, lon], zoom) sets the initial center and zoom level.
 * Washington State center is roughly [47.4, -120.5], zoom 7 shows the whole state.
 */
const map = L.map("map").setView([47.4, -120.5], 7);

/**
 * Tile layer = the background map image.
 * OpenStreetMap provides free map tiles. {s}, {z}, {x}, {y} are template
 * variables Leaflet fills in to load the right image for the current zoom/position.
 * attribution is legally required when using OSM tiles.
 */
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap contributors",

}).addTo(map);


// State


let allFlights   = [];       // Raw data from API
let markerLayer  = L.layerGroup().addTo(map);  // Group for flight markers
let heatLayer    = null;     // Heatmap layer (created on demand)
let heatmapOn    = false;    // Toggle state
let countySet    = new Set(); // Unique counties seen so far


// Color coding by altitude


/**
 * Returns a hex color based on altitude in meters.
 * Green = low (safe, normal), orange = mid, red = high (near ceiling).
 */
function altColor(alt) {
  if (alt == null)  return "#89b4fa";  // Unknown — blue
  if (alt < 50)     return "#a6e3a1";  // Low     — green
  if (alt < 100)    return "#fab387";  // Mid     — orange
  return                 "#f38ba8";   // High    — red
}


// Render markers


/**
 * Clears the marker layer and redraws markers for all flights that
 * pass the current county and altitude filters.
 *
 * L.circleMarker(latlng, options) draws a fixed-size circle (in pixels,
 * not meters) — good for data points that shouldn't scale with zoom.
 */
function renderMarkers() {
  markerLayer.clearLayers();

  const countyFilter = document.getElementById("county-filter").value;
  const maxAlt       = parseInt(document.getElementById("alt-filter").value);

  const filtered = allFlights.filter(f => {
    if (countyFilter && f.county !== countyFilter) return false;
    if (f.altitude != null && f.altitude > maxAlt)  return false;
    return f.latitude != null && f.longitude != null;
  });

  // Update the flight count badge
  document.getElementById("flight-count").textContent =
    `Showing ${filtered.length} of ${allFlights.length} flights`;

  filtered.forEach(f => {
    const marker = L.circleMarker([f.latitude, f.longitude], {
      radius:      7,
      fillColor:   altColor(f.altitude),
      color:       "#1e1e2e",   // Dark border ring
      weight:      1,
      opacity:     1,
      fillOpacity: 0.85
    });

    // Popup content — shown when the user clicks a marker
    const alt   = f.altitude != null ? f.altitude.toFixed(1) + "m" : "Unknown";
    const spd   = f.velocity != null ? (f.velocity * 3.6).toFixed(1) + " km/h" : "Unknown";
    const time  = f.recorded_at ? new Date(f.recorded_at).toLocaleTimeString() : "Unknown";
    const sign  = f.callsign || f.icao24 || "Unknown";

    marker.bindPopup(`
      <div style="min-width:160px; line-height:1.8">
        <strong style="font-size:1rem">${sign}</strong><br>
        <span style="color:#a6adc8;font-size:0.8rem">ICAO: ${f.icao24 || "—"}</span><br>
        <hr style="border-color:#45475a; margin:6px 0">
        📍 ${f.county || "Unknown County"}<br>
        📐 Altitude: ${alt}<br>
        💨 Speed: ${spd}<br>
        🕐 Captured: ${time}
      </div>
    `);

    markerLayer.addLayer(marker);
  });

  // Rebuild heatmap if it's currently active
  if (heatmapOn) renderHeatmap(filtered);
}


// Heatmap


/**
 * Leaflet.heat accepts an array of [lat, lon, intensity] points.
 * We use altitude as the intensity — higher flights show as "hotter."
 * If altitude is unknown we default to 0.5.
 */
function renderHeatmap(flights) {
  if (heatLayer) { heatLayer.remove(); heatLayer = null; }

  const pts = flights
    .filter(f => f.latitude && f.longitude)
    .map(f => [
      f.latitude,
      f.longitude,
      f.altitude != null ? f.altitude / 122 : 0.5  // Normalize to 0–1
    ]);

  heatLayer = L.heatLayer(pts, {
    radius:  25,
    blur:    15,
    maxZoom: 10,
    gradient: { 0.2: "#89b4fa", 0.5: "#fab387", 1.0: "#f38ba8" }
  }).addTo(map);
}


// County filter population


/**
 * After loading flights, collect all unique county names and
 * populate the <select> dropdown dynamically.
 */
function populateCountyFilter(flights) {
  flights.forEach(f => { if (f.county) countySet.add(f.county); });

  const sel = document.getElementById("county-filter");
  // Remove old options (keep the "All Counties" placeholder at index 0)
  while (sel.options.length > 1) sel.remove(1);

  [...countySet].sort().forEach(county => {
    const opt = document.createElement("option");
    opt.value = opt.textContent = county;
    sel.appendChild(opt);
  });
}


// Data fetching


async function loadFlights() {
  try {
    const data = await fetch("/api/flights/recent").then(r => r.json());
    allFlights = data;
    populateCountyFilter(data);
    renderMarkers();
  } catch (err) {
    console.error("Failed to load flights:", err);
  }
}


// Event listeners


// County filter change → re-render markers
document.getElementById("county-filter")
  .addEventListener("change", renderMarkers);

// Altitude slider → update label + re-render markers
document.getElementById("alt-filter").addEventListener("input", e => {
  document.getElementById("alt-value").textContent = e.target.value + "m";
  renderMarkers();
});

// Heatmap toggle button
document.getElementById("heatmap-btn").addEventListener("click", () => {
  heatmapOn = !heatmapOn;
  const btn = document.getElementById("heatmap-btn");

  if (heatmapOn) {
    btn.classList.replace("bg-indigo-600", "bg-orange-500");
    markerLayer.clearLayers();  // Hide individual markers when heatmap is on
    renderHeatmap(allFlights);
  } else {
    btn.classList.replace("bg-orange-500", "bg-indigo-600");
    if (heatLayer) { heatLayer.remove(); heatLayer = null; }
    renderMarkers();
  }
});

// Manual refresh button
document.getElementById("refresh-btn").addEventListener("click", loadFlights);


// Init + auto-refresh


loadFlights();
setInterval(loadFlights, 60_000);
