"use strict";
const $ = (id) => document.getElementById(id);
const number = (v) => Math.round(v).toLocaleString("en-GB");
const pct = (v) => (100 * v).toFixed(1) + "%";
const stamp = (m) =>
  new Date(m + "-15T12:00:00Z").toLocaleDateString("en-GB", {
    month: "short",
    year: "2-digit",
    timeZone: "UTC",
  });
let data;
function chart(target, rows, keys, options = {}) {
  const w = 1000,
    h = options.compact ? 320 : 350,
    p = { l: 62, r: 20, t: 15, b: 42 };
  const values = rows
    .flatMap((r) => keys.map((k) => r[k]))
    .filter((v) => v != null);
  let lo = options.zero ? Math.min(0, ...values) : Math.min(...values) * 0.94,
    hi = Math.max(...values) * 1.06;
  if (options.error) {
    const bound = Math.max(...values.map(Math.abs)) * 1.15;
    lo = -bound;
    hi = bound;
  }
  if (hi === lo) hi++;
  const x = (i) => p.l + (i * (w - p.l - p.r)) / Math.max(1, rows.length - 1),
    y = (v) => h - p.b - ((v - lo) / (hi - lo)) * (h - p.t - p.b);
  const compact = (v) =>
    Math.abs(v) >= 1e6
      ? (v / 1e6).toFixed(2) + "m"
      : (v / 1000).toFixed(0) + "k";
  let out = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${options.label || "Attendance chart"}">`;
  for (let i = 0; i <= 4; i++) {
    let v = lo + ((hi - lo) * i) / 4;
    out += `<line x1="${p.l}" x2="${w - p.r}" y1="${y(v)}" y2="${y(v)}" stroke="#e6ebe6"/><text x="${p.l - 12}" y="${y(v) + 4}" text-anchor="end">${compact(v)}</text>`;
  }
  if (options.band) {
    const points = rows
      .map((r, i) => `${x(i)},${y(r.upper)}`)
      .concat(
        [...rows]
          .reverse()
          .map((r, j) => `${x(rows.length - 1 - j)},${y(r.lower)}`),
      );
    out += `<polygon points="${points.join(" ")}" fill="#e9ede3"/>`;
  }
  if (options.error) {
    out += `<line x1="${p.l}" x2="${w - p.r}" y1="${y(0)}" y2="${y(0)}" stroke="#637276"/>`;
    rows.forEach((r, i) => {
      const v = r.error;
      out += `<rect x="${x(i) - 10}" y="${Math.min(y(0), y(v))}" width="20" height="${Math.max(1, Math.abs(y(v) - y(0)))}" fill="${v < 0 ? "#d78057" : "#19776d"}"><title>${stamp(r.month)}: ${number(v)} attendances</title></rect>`;
    });
  } else
    keys
      .filter((k) => k !== "upper" && k !== "lower")
      .forEach((k, idx) => {
        let color = idx === 0 ? "#19776d" : "#d78057";
        out += `<polyline points="${rows.map((r, i) => `${x(i)},${y(r[k])}`).join(" ")}" fill="none" stroke="${color}" stroke-width="2.5" ${idx ? 'stroke-dasharray="6 3"' : ""}/>`;
        if (rows.length < 50)
          rows.forEach(
            (r, i) =>
              (out += `<circle cx="${x(i)}" cy="${y(r[k])}" r="3" fill="${color}"><title>${stamp(r.month)} · ${k}: ${number(r[k])}</title></circle>`),
          );
      });
  rows.forEach((r, i) => {
    if (i % Math.ceil(rows.length / 7) === 0 || i === rows.length - 1)
      out += `<text x="${x(i)}" y="${h - 12}" text-anchor="middle">${stamp(r.month)}</text>`;
  });
  $(target).innerHTML = out + "</svg>";
}
function render() {
  const h = Number($("horizon").value),
    model = $("model").value,
    chosen = model === data.selected;
  const rows = data.test.filter((r) => r.horizon === h && r.model === model),
    m = data.metrics.find((r) => r.horizon === h && r.model === model);
  const width = chosen
    ? rows.reduce((s, r) => s + r.upper - r.lower, 0) / rows.length
    : null;
  const cards = [
    ["Mean absolute error", number(m.mae), "attendances per target month"],
    [
      "Weighted absolute error",
      pct(m.wape),
      "sum of absolute errors / actual totals",
    ],
    [
      "Mean bias",
      (m.bias > 0 ? "+" : "") + number(m.bias),
      m.bias < 0 ? "underestimated on average" : "overestimated on average",
    ],
    [
      "Band coverage",
      chosen ? pct(m.coverage) : "Not calibrated",
      chosen
        ? `${Math.round(m.coverage * 20)} / 20 targets · nominal 90%`
        : "bands are reserved for the selected model",
    ],
  ];
  $("metrics").innerHTML = cards
    .map(
      ([a, b, c]) =>
        `<article class="metric"><span>${a}</span><strong>${b}</strong><small>${c}</small></article>`,
    )
    .join("");
  $("chart-note").textContent =
    `${data.models[model]} · ${h}-month horizon · 20 rolling origins · ${stamp(rows[0].month)}–${stamp(rows.at(-1).month)} targets`;
  chart(
    "backtest-chart",
    rows,
    chosen
      ? ["actual", "predicted", "upper", "lower"]
      : ["actual", "predicted"],
    { band: chosen, label: "Held-out actual and predicted monthly attendance" },
  );
  $("interval-note").textContent = chosen
    ? `Shading: frozen nominal 90% empirical band. Mean full width: ${number(width)} attendances. All 20 targets are covered; wide bands are not proof of precise forecasting.`
    : "This model was not selected. No interval was calibrated for it; its final test performance is shown for comparison only.";
  chart("error-chart", rows, ["error"], {
    error: true,
    compact: true,
    label: "Signed forecast error by target month",
  });
  const comparisons = data.metrics.filter((r) => r.horizon === h),
    max = Math.max(...comparisons.map((r) => r.mae));
  $("comparison").innerHTML = comparisons
    .map(
      (r) =>
        `<div class="comparison-row"><div class="labels"><span>${data.models[r.model]}${r.model === data.selected ? " · selected" : ""}</span><b>${number(r.mae)}</b></div><div class="bar-track"><div class="bar ${r.model === data.selected ? "chosen" : ""}" style="width:${(100 * r.mae) / max}%"></div></div></div>`,
    )
    .join("");
}
function history() {
  const rows = data.history
    .filter((r) => r.month >= $("window").value)
    .map((r) => ({
      ...r,
      daily:
        r.attendances /
        new Date(
          Number(r.month.slice(0, 4)),
          Number(r.month.slice(5)),
          0,
        ).getDate(),
    }));
  chart("history-chart", rows, ["daily"], {
    label: "National monthly average daily Type 1 attendance history",
  });
}
fetch("report.json")
  .then((r) => {
    if (!r.ok) throw Error("Data unavailable");
    return r.json();
  })
  .then((r) => {
    data = r;
    render();
    history();
    $("horizon").addEventListener("change", render);
    $("model").addEventListener("change", render);
    $("window").addEventListener("change", history);
    $("projections").innerHTML =
      "<table><thead><tr><th>Target</th><th>Prediction</th><th>Empirical band</th></tr></thead><tbody>" +
      data.projection
        .map(
          (r) =>
            `<tr><td>${stamp(r.month)} · ${r.horizon} month</td><td>${number(r.predicted)}</td><td>${number(r.lower)}–${number(r.upper)}</td></tr>`,
        )
        .join("") +
      "</tbody></table>";
  })
  .catch((e) => {
    $("metrics").textContent =
      "The report data could not load. Please refresh or open the repository downloads.";
    console.error(e);
  });
