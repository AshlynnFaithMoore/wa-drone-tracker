/**
 * incidents.js

 * Handles the incidents table: loading, filtering, sorting,
 * row detail modal, and CSV export.
 *
 * All filtering and sorting happens client-side on the full dataset
 * that was fetched once on page load. This keeps the UI instant
 * (no extra API calls on every filter change).
 */


// State


let allIncidents = [];          // Full unfiltered dataset from API
let sortCol      = "incident_date";  // Currently sorted column
let sortAsc      = false;            // false = descending (newest first)



// Data loading


async function loadIncidents() {
  try {
    allIncidents = await fetch("/api/incidents").then(r => r.json());
    populateCountyFilter(allIncidents);
    renderTable();
  } catch (err) {
    console.error("Failed to load incidents:", err);
  }
}

function populateCountyFilter(incidents) {
  const counties = [...new Set(incidents.map(i => i.county).filter(Boolean))].sort();
  const sel = document.getElementById("county-filter");
  counties.forEach(c => {
    const opt = document.createElement("option");
    opt.value = opt.textContent = c;
    sel.appendChild(opt);
  });
}



// Filtering


/**
 * Reads all filter inputs and returns a subset of allIncidents.
 * Every filter is AND-ed together — a row must pass all of them.
 */
function applyFilters() {
  const search   = document.getElementById("search-input").value.toLowerCase();
  const severity = document.getElementById("severity-filter").value;
  const county   = document.getElementById("county-filter").value;

  return allIncidents.filter(inc => {
    // Text search across location and description fields
    if (search) {
      const haystack = `${inc.location} ${inc.description}`.toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    if (severity && inc.severity !== severity) return false;
    if (county   && inc.county   !== county)   return false;
    return true;
  });
}



// Sorting


/**
 * Sorts an array of incident objects by a given field.
 * String fields use localeCompare; everything else uses < > comparison.
 * asc=true → A→Z / oldest first; asc=false → Z→A / newest first.
 */
function sortData(data, col, asc) {
  return [...data].sort((a, b) => {
    let va = a[col] ?? "";
    let vb = b[col] ?? "";
    // Treat dates as strings — ISO format (YYYY-MM-DD) sorts correctly as string
    if (typeof va === "string") {
      return asc ? va.localeCompare(vb) : vb.localeCompare(va);
    }
    return asc ? va - vb : vb - va;
  });
}



// Severity badge HTML


function severityBadge(sev) {
  const cls = {
    "Minor":    "badge-minor",
    "Moderate": "badge-moderate",
    "Severe":   "badge-severe"
  }[sev] || "badge-minor";
  return `<span class="badge ${cls}">${sev || "Unknown"}</span>`;
}



// Table rendering


/**
 * Applies filters, sorts, and rebuilds the <tbody> rows from scratch.
 * Called on every filter change, sort click, or data load.
 */
function renderTable() {
  const filtered = applyFilters();
  const sorted   = sortData(filtered, sortCol, sortAsc);

  const tbody = document.getElementById("incidents-body");
  const empty = document.getElementById("empty-state");

  document.getElementById("row-count").textContent =
    `${sorted.length} incident${sorted.length !== 1 ? "s" : ""}`;

  if (sorted.length === 0) {
    tbody.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");

  // Build all rows as one HTML string for performance (fewer DOM operations)
  tbody.innerHTML = sorted.map(inc => `
    <tr data-id="${inc.id}">
      <td>${inc.incident_date || "—"}</td>
      <td>${inc.location || "—"}</td>
      <td>${inc.county || "—"}</td>
      <td>${severityBadge(inc.severity)}</td>
      <td>${inc.reported_by || "—"}</td>
      <td style="max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
        ${inc.description || "—"}
      </td>
    </tr>
  `).join("");

  // Attach click handlers after building rows
  // We use event delegation — one listener on tbody rather than one per row
  tbody.querySelectorAll("tr").forEach(row => {
    row.addEventListener("click", () => {
      const id  = parseInt(row.dataset.id);
      const inc = allIncidents.find(i => i.id === id);
      if (inc) openModal(inc);
    });
  });

  // Update sort arrows in headers
  document.querySelectorAll("thead th").forEach(th => {
    th.classList.remove("sorted");
    const arrow = th.querySelector(".sort-arrow");
    if (th.dataset.col === sortCol) {
      th.classList.add("sorted");
      arrow.textContent = sortAsc ? " ▲" : " ▼";
    } else {
      arrow.textContent = "";
    }
  });
}



// Detail modal


/**
 * Opens the detail modal for a clicked incident row.
 * Shows all fields including description and coordinates.
 */
function openModal(inc) {
  document.getElementById("modal-title").textContent =
    `Incident — ${inc.incident_date || "Unknown Date"}`;

  document.getElementById("modal-content").innerHTML = `
    <div class="modal-row"><span class="modal-label">Location</span><span>${inc.location || "—"}</span></div>
    <div class="modal-row"><span class="modal-label">County</span><span>${inc.county || "—"}</span></div>
    <div class="modal-row"><span class="modal-label">Severity</span>${severityBadge(inc.severity)}</div>
    <div class="modal-row"><span class="modal-label">Reported By</span><span>${inc.reported_by || "—"}</span></div>
    ${inc.latitude && inc.longitude ? `
    <div class="modal-row">
      <span class="modal-label">Coordinates</span>
      <a href="https://www.openstreetmap.org/?mlat=${inc.latitude}&mlon=${inc.longitude}&zoom=13"
         target="_blank" style="color:#89b4fa">
        ${inc.latitude.toFixed(4)}, ${inc.longitude.toFixed(4)} ↗
      </a>
    </div>` : ""}
    <hr style="border-color:#45475a; margin:12px 0">
    <div style="font-size:0.875rem; line-height:1.7; color:#cdd6f4">
      ${inc.description || "No description available."}
    </div>
  `;

  document.getElementById("modal-overlay").classList.add("open");
}

// Close modal on overlay click or close button
document.getElementById("modal-overlay").addEventListener("click", e => {
  if (e.target === e.currentTarget) closeModal();
});
document.getElementById("modal-close").addEventListener("click", closeModal);
function closeModal() {
  document.getElementById("modal-overlay").classList.remove("open");
}

// Close modal with Escape key
document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeModal();
});



// CSV export


/**
 * Converts the currently filtered & sorted incident list to CSV
 * and triggers a browser download. No server needed — this runs
 * entirely in the browser using a Blob and a fake <a> click.
 */
document.getElementById("export-btn").addEventListener("click", () => {
  const filtered = sortData(applyFilters(), sortCol, sortAsc);

  const headers = ["Date", "Location", "County", "Severity", "Reported By", "Description"];
  const rows = filtered.map(inc => [
    inc.incident_date || "",
    inc.location      || "",
    inc.county        || "",
    inc.severity      || "",
    inc.reported_by   || "",
    // Wrap description in quotes and escape any internal quotes
    `"${(inc.description || "").replace(/"/g, '""')}"`
  ].join(","));

  const csv  = [headers.join(","), ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);

  // Programmatically click a hidden <a> to trigger the download
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `wa_drone_incidents_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);  // Free the memory after download starts
});



// Column sort click handlers


document.querySelectorAll("thead th[data-col]").forEach(th => {
  th.addEventListener("click", () => {
    const col = th.dataset.col;
    if (sortCol === col) {
      sortAsc = !sortAsc;   // Same column → flip direction
    } else {
      sortCol = col;
      sortAsc = true;       // New column → start ascending
    }
    renderTable();
  });
});



// Filter event listeners


document.getElementById("search-input").addEventListener("input", renderTable);
document.getElementById("severity-filter").addEventListener("change", renderTable);
document.getElementById("county-filter").addEventListener("change", renderTable);


// Init


loadIncidents();
