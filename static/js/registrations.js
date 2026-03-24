/**
 * registrations.js

 * Powers the registrations page.
 *
 * Features:
 * - KPI cards: total, commercial count, recreational count
 * - County bar chart (top 15)
 * - Year-over-year trend line chart
 * - Searchable, sortable, paginated registrations table
 * - CSV export of filtered data

 * Pagination: we load ALL records once, then slice them into pages
 * client-side. For very large datasets (100k+ rows) you'd want
 * server-side pagination instead, but FAA WA data is manageable.
 */


// State


let allRegs    = [];           // Full dataset from /api/registrations
let filtered   = [];           // After filters applied
let sortCol    = "registered_date";
let sortAsc    = false;        // Newest first by default
let currentPage = 1;
const PAGE_SIZE = 50;          // Rows per page

const COLORS = ["#89b4fa","#a6e3a1","#fab387","#f38ba8",
                "#cba6f7","#94e2d5","#f9e2af","#74c7ec",
                "#b4befe","#cba6f7","#eba0ac","#f38ba8",
                "#a6e3a1","#89dceb","#cdd6f4"];
const charts = {};



// Data loading


async function loadRegistrations() {
  try {
    allRegs = await fetch("/api/registrations").then(r => r.json());
    populateFilters(allRegs);
    updateKPIs(allRegs);
    renderCountyChart(allRegs);
    renderTrendChart(allRegs);
    applyFiltersAndRender();
  } catch (err) {
    console.error("Failed to load registrations:", err);
  }
}



// Filter helpers


function populateFilters(regs) {
  // County filter
  const counties = [...new Set(regs.map(r => r.owner_county).filter(Boolean))].sort();
  const cSel = document.getElementById("county-filter");
  counties.forEach(c => {
    const o = document.createElement("option");
    o.value = o.textContent = c;
    cSel.appendChild(o);
  });

  // Type filter
  const types = [...new Set(regs.map(r => r.drone_type).filter(Boolean))].sort();
  const tSel = document.getElementById("type-filter");
  types.forEach(t => {
    const o = document.createElement("option");
    o.value = o.textContent = t;
    tSel.appendChild(o);
  });
}

function applyFilters() {
  const search  = document.getElementById("search-input").value.toLowerCase();
  const purpose = document.getElementById("purpose-filter").value;
  const county  = document.getElementById("county-filter").value;
  const type    = document.getElementById("type-filter").value;

  return allRegs.filter(r => {
    if (search) {
      const hay = `${r.registration_no} ${r.owner_county} ${r.drone_type}`.toLowerCase();
      if (!hay.includes(search)) return false;
    }
    if (purpose && r.purpose     !== purpose) return false;
    if (county  && r.owner_county !== county)  return false;
    if (type    && r.drone_type   !== type)    return false;
    return true;
  });
}

function applyFiltersAndRender() {
  filtered = sortData(applyFilters(), sortCol, sortAsc);
  currentPage = 1;
  renderTable();
}



// KPI cards


function updateKPIs(regs) {
  const commercial   = regs.filter(r => r.purpose === "Commercial").length;
  const recreational = regs.filter(r => r.purpose === "Recreational").length;

  document.getElementById("kpi-total").textContent        = regs.length.toLocaleString();
  document.getElementById("kpi-commercial").textContent   = commercial.toLocaleString();
  document.getElementById("kpi-recreational").textContent = recreational.toLocaleString();
}



// Charts


function renderCountyChart(regs) {
  // Count registrations per county
  const counts = {};
  regs.forEach(r => {
    const c = r.owner_county || "Unknown";
    counts[c] = (counts[c] || 0) + 1;
  });

  // Sort by count descending, take top 15
  const sorted = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15);

  const labels = sorted.map(([c]) => c);
  const values = sorted.map(([, n]) => n);

  if (charts.county) charts.county.destroy();
  const ctx = document.getElementById("regsByCountyChart").getContext("2d");
  charts.county = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Registrations",
        data: values,
        backgroundColor: COLORS[0],
        borderRadius: 5
      }]
    },
    options: {
      indexAxis: "y",    // Horizontal bar chart — easier to read county names
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#a6adc8" }, grid: { color: "#45475a" } },
        y: { ticks: { color: "#a6adc8", font: { size: 11 } }, grid: { display: false } }
      }
    }
  });
}

function renderTrendChart(regs) {
  /**
   * Build year-over-year counts from registered_date field.
   * registered_date format: "YYYY-MM-DD" — slice the year out.
   */
  const yearCounts = {};
  regs.forEach(r => {
    if (!r.registered_date) return;
    const year = r.registered_date.slice(0, 4);
    yearCounts[year] = (yearCounts[year] || 0) + 1;
  });

  const years  = Object.keys(yearCounts).sort();
  const counts = years.map(y => yearCounts[y]);

  if (charts.trend) charts.trend.destroy();
  const ctx = document.getElementById("trendChart").getContext("2d");
  charts.trend = new Chart(ctx, {
    type: "line",
    data: {
      labels: years,
      datasets: [{
        label: "Registrations",
        data: counts,
        borderColor: "#89b4fa",
        backgroundColor: "rgba(137,180,250,0.15)",
        tension: 0.3,        // Slightly curved line
        fill: true,
        pointBackgroundColor: "#89b4fa",
        pointRadius: 4
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



// Table rendering with pagination


function sortData(data, col, asc) {
  return [...data].sort((a, b) => {
    let va = a[col] ?? "";
    let vb = b[col] ?? "";
    if (typeof va === "string") return asc ? va.localeCompare(vb) : vb.localeCompare(va);
    return asc ? va - vb : vb - va;
  });
}

function purposeStyle(purpose) {
  if (purpose === "Commercial")   return "color:#fab387; font-weight:600";
  if (purpose === "Recreational") return "color:#a6e3a1; font-weight:600";
  return "";
}

function renderTable() {
  const total      = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  currentPage      = Math.min(currentPage, totalPages);

  const start  = (currentPage - 1) * PAGE_SIZE;
  const end    = Math.min(start + PAGE_SIZE, total);
  const pageRows = filtered.slice(start, end);

  // Update row count and pagination indicator
  document.getElementById("row-count").textContent =
    `${total.toLocaleString()} registration${total !== 1 ? "s" : ""}`;
  document.getElementById("page-indicator").textContent =
    `Page ${currentPage} of ${totalPages}`;

  // Enable/disable pagination buttons
  document.getElementById("prev-btn").disabled = currentPage === 1;
  document.getElementById("next-btn").disabled = currentPage === totalPages;

  // Render rows
  document.getElementById("reg-body").innerHTML = pageRows.map(r => `
    <tr>
      <td style="font-family:monospace; color:#cba6f7">${r.registration_no || "—"}</td>
      <td>${r.owner_county || "—"}</td>
      <td style="color:#a6adc8">${r.drone_type || "—"}</td>
      <td style="${purposeStyle(r.purpose)}">${r.purpose || "—"}</td>
      <td>${r.registered_date || "—"}</td>
    </tr>
  `).join("");

  // Update sort arrows
  document.querySelectorAll("thead th[data-col]").forEach(th => {
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



// CSV export


document.getElementById("export-btn").addEventListener("click", () => {
  const headers = ["Registration No", "County", "Type", "Purpose", "Registered Date"];
  const rows = filtered.map(r => [
    r.registration_no || "",
    r.owner_county    || "",
    r.drone_type      || "",
    r.purpose         || "",
    r.registered_date || ""
  ].join(","));

  const csv  = [headers.join(","), ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `wa_drone_registrations_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast("CSV downloaded!");   // Uses the showToast() from base.html
});



// Event listeners


document.getElementById("search-input").addEventListener("input", applyFiltersAndRender);
document.getElementById("purpose-filter").addEventListener("change", applyFiltersAndRender);
document.getElementById("county-filter").addEventListener("change", applyFiltersAndRender);
document.getElementById("type-filter").addEventListener("change", applyFiltersAndRender);

document.getElementById("prev-btn").addEventListener("click", () => {
  if (currentPage > 1) { currentPage--; renderTable(); }
});
document.getElementById("next-btn").addEventListener("click", () => {
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  if (currentPage < totalPages) { currentPage++; renderTable(); }
});

document.querySelectorAll("thead th[data-col]").forEach(th => {
  th.addEventListener("click", () => {
    const col = th.dataset.col;
    if (sortCol === col) { sortAsc = !sortAsc; }
    else { sortCol = col; sortAsc = true; }
    filtered = sortData(filtered, sortCol, sortAsc);
    currentPage = 1;
    renderTable();
  });
});


// Init

loadRegistrations();
