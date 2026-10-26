const charts = {};
const statusEl = document.getElementById("status");
const filterDefs = [
  ["manufacturer", "Manufacturer"], ["battery_type", "Battery type"],
  ["region", "Region"], ["category", "Category"],
];
const chartDefs = [
  ["c_manufacturer", "sales_by_manufacturer", "bar"], ["c_battery", "sales_by_battery", "bar"],
  ["c_region", "sales_by_region", "bar"], ["c_category", "sales_by_category", "bar"],
  ["c_country", "sales_by_country", "bar"], ["c_trend", "sales_trend", "line"],
  ["c_rating", "rating_by_category", "bar"], ["c_range", "range_by_category", "bar"],
  ["c_energy", "energy_by_category", "bar"],
];
const kpiDefs = [
  ["total_sales", "Annual sales (sum)"], ["avg_rating", "Avg customer rating"],
  ["manufacturers", "Manufacturers"], ["avg_range", "Avg range"],
  ["avg_battery", "Avg battery capacity"], ["total_co2", "CO2 savings (sum)"],
];

function fmt(v) { return v === null || v === undefined ? "n/a" : Number(v).toLocaleString(); }

async function init() {
  const res = await fetch("/api/options");
  const opt = await res.json();
  if (!res.ok) { statusEl.textContent = opt.error; statusEl.classList.add("error"); return; }
  const box = document.getElementById("filters");
  filterDefs.forEach(([key, label]) => {
    if (!opt[key]) return;
    const l = document.createElement("label");
    l.innerHTML = `${label}<select id="f_${key}"><option value="">All</option>` +
      opt[key].map(v => `<option>${v}</option>`).join("") + "</select>";
    box.appendChild(l);
  });
  if (opt.year_range) {
    ["min", "max"].forEach((k, i) => {
      const l = document.createElement("label");
      l.innerHTML = `Year ${k}<input type="number" id="f_year_${k}" value="${opt.year_range[i]}" min="${opt.year_range[0]}" max="${opt.year_range[1]}">`;
      box.appendChild(l);
    });
  }
  box.addEventListener("change", refresh);
  refresh();
}

async function refresh() {
  const p = new URLSearchParams();
  document.querySelectorAll("#filters select, #filters input").forEach(el => {
    if (el.value) p.set(el.id.replace("f_", ""), el.value);
  });
  statusEl.textContent = "Loading data..."; statusEl.classList.remove("error");
  const res = await fetch("/api/data?" + p);
  const d = await res.json();
  if (!res.ok) { statusEl.textContent = d.error; statusEl.classList.add("error"); return; }
  statusEl.textContent = d.kpis.rows ? `${fmt(d.kpis.rows)} records match the selected filters.` : "No records match these filters.";
  document.getElementById("kpis").innerHTML = kpiDefs
    .filter(([k]) => d.kpis[k] !== null)
    .map(([k, l]) => `<div class="kpi"><span>${l}</span><b>${fmt(d.kpis[k])}</b></div>`).join("");
  chartDefs.forEach(([id, key, type]) => draw(id, d[key], type));
}

function draw(id, series, type) {
  const el = document.getElementById(id);
  el.parentElement.style.display = series.labels.length ? "" : "none";
  if (charts[id]) charts[id].destroy();
  if (!series.labels.length) return;
  charts[id] = new Chart(el, {
    type,
    data: { labels: series.labels, datasets: [{ data: series.values, backgroundColor: "#1b8a5a", borderColor: "#1b8a5a", tension: .3 }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
  });
}

init();
