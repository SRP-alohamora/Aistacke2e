"use strict";
// Eval Quality tab: promptfoo-style dashboard for the fusion-fuel-demo suite.
const EQ_COLORS = ["#4285f4", "#f9ab00", "#34a853", "#ea4335", "#a142f4"];
const eqState = { filter: "all", search: "", candidate: null };

async function renderEvalQuality() {
  state.evalTab = state.evalTab || "results";
  const d = await api("/api/evals/dashboard");
  state.evalDash = d;
  const ran = d.models.filter((m) => m.evidence_id);
  const sim = ran.some((m) => m.simulated);
  eqState.candidate = eqState.candidate || (ran.find((m) => m.model_key !== d.baseline) || {}).model_key;
  const tabs = [["results", "Results"], ["dataset", "Dataset review"], ["assertions", "Assertions"], ["history", "History"]];
  $("tabEval").innerHTML = `
    <div class="card eq-head">
      <div class="eq-meta">
        <span class="eq-chip"><b>Suite</b> ${esc(d.suite)}</span>
        <span class="eq-chip"><b>Runs</b> ${ran.map((m) => esc(m.evidence_id)).join(", ") || "none"}</span>
        <span class="eq-chip"><b>Author</b> demo user</span>
        ${sim ? '<span class="chip-sim">Simulated evidence - offline fixture, not measured</span>' : ""}
      </div>
      <div class="eq-controls">
        <label>Display <select id="eqFilter">
          ${[["all", "Show all results"], ["fail", "Failures only"], ["pass", "Passes only"], ["error", "Errors only"]].map(([v, t]) => `<option value="${v}" ${eqState.filter === v ? "selected" : ""}>${t}</option>`).join("")}
        </select></label>
        <label>Search <input id="eqSearch" placeholder="Text or regex" value="${esc(eqState.search)}"></label>
        <button class="btn filled" id="eqRunAll">Run all evals</button>
      </div>
    </div>
    ${ran.length ? `<div class="card eq-charts">${chartPassRate(ran)}${chartScoreHist(ran, d)}${chartScatter(d, ran)}</div>` : ""}
    <div class="card">
      <nav class="subtabs">${tabs.map(([k, t]) => `<button class="subtab ${state.evalTab === k ? "on" : ""}" data-sub="${k}">${t}</button>`).join("")}</nav>
      <div id="eqBody">${ran.length ? eqBody(d, ran) : `<p class="muted">No eval runs yet. Press <b>Run all evals</b>.</p>`}</div>
    </div>`;
  $("tabEval").querySelectorAll("[data-sub]").forEach((b) => b.onclick = () => { state.evalTab = b.dataset.sub; renderEvalQuality(); });
  $("eqFilter").onchange = () => { eqState.filter = $("eqFilter").value; $("eqBody").innerHTML = eqBody(d, ran); };
  $("eqSearch").oninput = () => { eqState.search = $("eqSearch").value; $("eqBody").innerHTML = eqBody(d, ran); };
  $("eqRunAll").onclick = () => busy($("eqRunAll"), async () => {
    $("eqRunAll").textContent = "Running…";
    await api("/api/evals/all", { method: "POST" });
    await renderEvalQuality();
    if (state.rec) await recommend();
  });
  const cand = $("eqCandidate");
  if (cand) cand.onchange = () => { eqState.candidate = cand.value; renderEvalQuality(); };
}

function eqBody(d, ran) {
  if (state.evalTab === "dataset") return eqDataset(d);
  if (state.evalTab === "assertions") return eqAssertions(d, ran);
  if (state.evalTab === "history") return eqHistory(ran);
  return eqResults(d, ran);
}

// --- charts (inline SVG) ------------------------------------------------------------
function frame(title, inner, xLabel) {
  return `<figure class="eq-chart"><svg viewBox="0 0 320 190" role="img" aria-label="${esc(title)}">${inner}</svg><figcaption>${esc(xLabel)}</figcaption></figure>`;
}
function yAxis(max, x0, y0, h, ticks) {
  let g = "";
  for (let i = 0; i <= ticks; i++) {
    const v = (max / ticks) * i, y = y0 - (h * i) / ticks;
    g += `<line x1="${x0}" x2="310" y1="${y}" y2="${y}" stroke="#eceff1"/><text x="${x0 - 6}" y="${y + 3}" text-anchor="end" class="ax">${Math.round(v)}</text>`;
  }
  return g;
}
function chartPassRate(ran) {
  const x0 = 34, y0 = 160, h = 140, w = (310 - x0) / ran.length;
  let g = yAxis(100, x0, y0, h, 4);
  ran.forEach((m, i) => {
    const bh = (h * m.pass_rate) / 100, x = x0 + i * w + w * 0.2;
    g += `<rect x="${x}" y="${y0 - bh}" width="${w * 0.6}" height="${bh}" fill="${EQ_COLORS[i % 5]}" rx="2"><title>${esc(m.label)}: ${m.pass_rate}%</title></rect>
      <text x="${x + w * 0.3}" y="${y0 - bh - 4}" text-anchor="middle" class="ax">${m.pass_rate}%</text>
      <text x="${x + w * 0.3}" y="${y0 + 14}" text-anchor="middle" class="ax">${esc(m.label.replace("Claude ", "").replace("OpenAI ", ""))}</text>`;
  });
  return frame("Pass rate by model", g, "Pass rate (%)");
}
function chartScoreHist(ran, d) {
  const bins = [0, 0.25, 0.5, 0.75, 1], x0 = 30, y0 = 160, h = 140;
  const counts = ran.map((m) => bins.map((b) => Object.values(m.results).filter((r) => Math.abs(r.score - b) < 0.13).length));
  const max = Math.max(1, ...counts.flat());
  const bw = (310 - x0) / bins.length;
  let g = yAxis(max, x0, y0, h, Math.min(max, 5));
  bins.forEach((b, j) => {
    ran.forEach((m, i) => {
      const c = counts[i][j], bh = (h * c) / max, w = (bw * 0.8) / ran.length, x = x0 + j * bw + bw * 0.1 + i * w;
      if (c) g += `<rect x="${x}" y="${y0 - bh}" width="${w - 1}" height="${bh}" fill="${EQ_COLORS[i % 5]}"><title>${esc(m.label)}: ${c} case(s) scored ${b}</title></rect>`;
    });
    g += `<text x="${x0 + j * bw + bw / 2}" y="${y0 + 14}" text-anchor="middle" class="ax">${b}</text>`;
  });
  return frame("Score distribution", g, "Score per case (share of checks passed)");
}
function chartScatter(d, ran) {
  const base = ran.find((m) => m.model_key === d.baseline), cand = ran.find((m) => m.model_key === eqState.candidate);
  const x0 = 40, y0 = 160, size = 130;
  let g = yAxis(100, x0, y0, size, 4) + `<line x1="${x0}" y1="${y0}" x2="${x0 + size * 2}" y2="${y0 - size}" stroke="#9aa0a6" stroke-dasharray="4 4"/>`;
  if (base && cand) {
    Object.keys(base.results).forEach((id, k) => {
      const bx = base.results[id].score, cy = cand.results[id] ? cand.results[id].score : 0;
      const jitter = ((k % 5) - 2) * 3;
      const color = cy > bx ? "#34a853" : cy < bx ? "#ea4335" : "#4285f4";
      g += `<circle cx="${x0 + bx * size * 2 + jitter}" cy="${y0 - cy * size + jitter}" r="4" fill="${color}" opacity=".8"><title>${id}: ${bx} vs ${cy}</title></circle>`;
    });
    [0, 50, 100].forEach((v) => { g += `<text x="${x0 + (v / 100) * size * 2}" y="${y0 + 14}" text-anchor="middle" class="ax">${v}%</text>`; });
  }
  const sel = `<select id="eqCandidate" class="eq-mini">${ran.filter((m) => m.model_key !== d.baseline).map((m) => `<option value="${m.model_key}" ${m.model_key === eqState.candidate ? "selected" : ""}>${esc(m.label)}</option>`).join("")}</select>`;
  return `<figure class="eq-chart"><svg viewBox="0 0 320 190" role="img" aria-label="Per-case score: baseline vs candidate">${g}</svg>
    <figcaption>${esc(base ? base.label : "baseline")} score (x) vs ${sel} (y) · green = candidate better, red = worse</figcaption></figure>`;
}

// --- sub-tabs ----------------------------------------------------------------------------
function badge(status) { return `<span class="eq-badge ${status.toLowerCase()}">${status}</span>`; }
function passPill(m) {
  const cls = m.pass_rate >= 90 ? "good" : m.pass_rate >= 60 ? "mid" : "bad";
  return `<div class="eq-pass ${cls}"><b>${m.pass_rate.toFixed(2)}% passing</b> (${m.passing}/${m.total} cases)</div>`;
}
function eqResults(d, ran) {
  let rx = null;
  try { rx = eqState.search ? new RegExp(eqState.search, "i") : null; } catch { rx = null; }
  const rows = d.cases.filter((c) => {
    const statuses = ran.map((m) => (m.results[c.id] || {}).status);
    if (eqState.filter === "fail" && !statuses.includes("FAIL")) return false;
    if (eqState.filter === "pass" && !statuses.every((s) => s === "PASS")) return false;
    if (eqState.filter === "error" && !statuses.includes("ERROR")) return false;
    if (rx) {
      const hay = [c.id, c.cuisines.join(" "), c.activity, c.exclusions.join(" "), c.note, ...ran.map((m) => (m.results[c.id] || {}).reason || "")].join(" ");
      if (!rx.test(hay)) return false;
    }
    return true;
  });
  const head = ran.map((m, i) => `<th class="eq-model"><div class="eq-model-name"><span class="eq-sw" style="background:${EQ_COLORS[i % 5]}"></span>${esc(m.provider)}:<b>${esc(m.label.replace(/^(Claude|OpenAI) /, ""))}</b></div>
      ${passPill(m)}${m.errors ? `<div class="eq-pass bad">Errors: ${m.errors}</div>` : ""}
      <div class="eq-stats">Asserts: ${m.asserts_passed}/${m.asserts_total} passed<br>Total cost: $${m.total_cost_usd.toFixed(4)}<br>Total tokens: ${m.total_tokens.toLocaleString()}<br>
        Avg tokens: ${m.avg_tokens}<br>Avg latency: ${m.avg_latency_ms.toLocaleString()} ms<br>Tokens/sec: ${m.tokens_per_sec}${m.simulated ? '<br><span class="chip-sim tiny">simulated</span>' : ""}</div></th>`).join("");
  const body = rows.map((c, n) => `<tr><td class="eq-row">${esc(c.id)}</td>
      <td class="eq-vars"><b>${c.kind === "safety" ? "Safety" : "Recipe"}</b><br>${esc(c.cuisines.join(" + "))} · ${c.carb_target_g} g · ${esc((c.activity || "").replace("_", " "))}
        ${c.exclusions.length ? `<br><span class="muted">exclude ${esc(c.exclusions.join(", "))}</span>` : ""}${c.note ? `<br><span class="muted">"${esc(c.note)}"</span>` : ""}</td>
      ${ran.map((m) => { const r = m.results[c.id] || { status: "ERROR", reason: "not run", score: 0 };
        return `<td class="eq-cell">${badge(r.status)}<div class="eq-reason ${r.status.toLowerCase()}">${esc(r.reason)}</div>
          <div class="muted eq-small">score ${r.score}${r.final_carbs_g != null ? ` · carbs ${r.final_carbs_g} g (draft ${r.draft_carbs_g} g)` : ""}${r.usage ? ` · ${r.usage.latency_ms} ms` : ""}</div></td>`; }).join("")}</tr>`).join("");
  return `<div class="table-scroll"><table class="eq-table"><tr><th></th><th>Variables</th>${head}</tr>${body ||
    `<tr><td colspan="${ran.length + 2}" class="muted">No cases match the filter.</td></tr>`}</table></div>`;
}
function eqDataset(d) {
  const ds = d.dataset;
  const maxT = Math.max(...ds.carb_targets);
  const bars = ds.carb_targets.map((t) => `<span class="eq-bar" style="height:${(t / maxT) * 60}px" title="${t} g"></span>`).join("");
  return `<div class="eq-kpis">
      <div class="eq-kpi"><b>${ds.n}</b><span>cases (need ${ds.required_min})</span></div>
      <div class="eq-kpi"><b>${ds.task}</b><span>recipe cases</span></div>
      <div class="eq-kpi"><b>${ds.safety}</b><span>safety cases</span></div>
      <div class="eq-kpi"><b>${ds.with_exclusions}</b><span>with exclusions</span></div>
      <div class="eq-kpi"><b>${ds.cuisines_covered.length}/${ds.cuisines_total}</b><span>cuisines covered</span></div>
    </div>
    <div class="eq-two">
      <div><div class="sub">Carb targets across cases</div><div class="eq-bars">${bars}</div><div class="muted eq-small">${Math.min(...ds.carb_targets)}-${maxT} g</div></div>
      <div><div class="sub">Activity split</div>${Object.entries(ds.activities).map(([k, v]) => `<div class="eq-split"><span>${esc(k.replace("_", " "))}</span><span class="eq-splitbar"><span style="width:${(v / ds.n) * 100}%"></span></span><b>${v}</b></div>`).join("")}</div>
    </div>
    <div class="sub">Dataset issues to fix</div><ul>${ds.issues.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    <div class="sub">Cases</div>
    <table class="sec-table"><tr><th>ID</th><th>Kind</th><th>Cuisines</th><th class="num">Carb target</th><th>Activity</th><th>Exclusions</th><th>Prompt note</th><th>Source</th></tr>
      ${d.cases.map((c) => `<tr><td class="comp">${esc(c.id)}</td><td>${esc(c.kind)}</td><td>${esc(c.cuisines.join(", "))}</td><td class="num">${c.carb_target_g} g</td><td>${esc(c.activity || "")}</td><td>${esc(c.exclusions.join(", ") || "-")}</td><td>${esc(c.note || "-")}</td><td>${esc(c.source)}</td></tr>`).join("")}</table>
    <p class="muted eq-small"><a href="source/eval_cases.yaml.html" target="_blank" rel="noopener">Open eval_cases.yaml</a></p>`;
}
function eqAssertions(d, ran) {
  return `<table class="sec-table"><tr><th>Check</th><th>Applies to</th><th class="num">Gate</th>${ran.map((m) => `<th class="num">${esc(m.label)}</th>`).join("")}</tr>
    ${d.gates.map((g) => `<tr><td><b>${esc(g.label)}</b><div class="muted comp">${esc(g.key)}</div></td><td>${esc(g.applies_to)}</td><td class="num">≥ ${Math.round(g.threshold * 100)}%</td>
      ${ran.map((m) => { const v = m.gate_rates[g.key]; const ok = v != null && v >= g.threshold;
        return `<td class="num"><span class="eq-gate ${v == null ? "" : ok ? "good" : "bad"}">${v == null ? "-" : Math.round(v * 100) + "%"}</span></td>`; }).join("")}</tr>`).join("")}</table>
    <p class="muted eq-small">All checks are deterministic code checks; no LLM judge is used in this suite. <a href="source/evals.py.html" target="_blank" rel="noopener">evals.py</a></p>`;
}
function eqHistory(ran) {
  return `<table class="sec-table"><tr><th>Run</th><th>Model</th><th>Created</th><th>Expires</th><th>Evidence</th><th class="num">Pass rate</th></tr>
    ${ran.map((m) => `<tr><td class="comp">${esc(m.evidence_id)}</td><td>${esc(m.label)}</td><td>${esc(m.created_at)}</td><td>${esc(m.expires_at.slice(0, 10))}</td>
      <td>${m.simulated ? '<span class="chip-sim tiny">simulated</span>' : '<span class="pill green">measured</span>'}</td><td class="num">${m.pass_rate}%</td></tr>`).join("")}</table>
    <p class="muted eq-small">The demo keeps the latest run per model. Production keeps every run so regressions can be compared over time.</p>`;
}
