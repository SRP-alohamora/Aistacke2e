"use strict";
// GRC tab: Architecture Control Plane & Contracts (KPIs, topology, contracts, synthetic runner, scaffolding).
const cpState = { tab: "schema", schemaView: "python", scaffold: null, file: "src/fusion_fuel/contracts.py", synth: null, n: 10, seed: 7 };

async function renderControlPlane() {
  const body = { answers: answersObj(), follow_ups: state.followUps, model_key: state.modelKey,
                 deployments: state.deployments, prd_text: state.prdText || "" };
  const d = await api("/api/control-plane", { method: "POST", body: JSON.stringify(body) });
  const k = d.kpis;
  const kpi = (label, x, cls) => `<div class="cp-kpi"><div class="cp-kpi-l">${label}</div><div class="cp-kpi-v ${cls}">${esc(x.value)}</div><div class="cp-kpi-d">${esc(x.detail)}</div></div>`;
  $("cpSection").innerHTML = `
    <div class="card cp">
      <div class="cp-title"><div><h2>Architecture Control Plane &amp; Contracts</h2>
        <p class="muted">Production topology, Pydantic contracts and unit economics for Fusion Fuel${k.simulated ? ' · <span class="chip-sim tiny">simulated evidence</span>' : ""}</p></div></div>
      <div class="cp-kpis">
        ${kpi("Unit cost", k.unit_cost, "green")}${kpi("Contract safety", k.contract_safety, "blue")}
        ${kpi("Schema conformance", k.schema_conformance, "green")}${kpi("P95 latency", k.p95_latency, "")}
      </div>
      <div class="cp-topo">${d.topology.map((t) => `
        <div class="cp-row">
          <span class="cp-n">${t.n}</span>
          <div class="cp-name"><b>${esc(t.name)}</b><div class="muted">${esc(t.description)}</div></div>
          <span class="cp-chip ${t.highlight ? "hl" : ""}">${esc(t.component)}</span>
          <span class="cp-cost">${esc(t.cost)}</span>
          <button class="btn tonal small" data-cp="${t.action}:${t.target}">${t.action === "swap" ? "Swap" : "Inspect"}</button>
        </div>`).join("")}</div>
      <div class="cp-panel">
        <nav class="subtabs">
          <button class="subtab ${cpState.tab === "schema" ? "on" : ""}" data-cptab="schema">📜 Pydantic v2 Schema</button>
          <button class="subtab ${cpState.tab === "synthetic" ? "on" : ""}" data-cptab="synthetic">🧪 Synthetic Test Runner</button>
          <button class="subtab ${cpState.tab === "scaffold" ? "on" : ""}" data-cptab="scaffold">🚀 Scaffolding Code</button>
        </nav>
        <div id="cpBody"></div>
      </div>
    </div>`;
  $("cpSection").querySelectorAll("[data-cptab]").forEach((b) => b.onclick = () => { cpState.tab = b.dataset.cptab; renderCpTabs(); renderCpBody(); });
  $("cpSection").querySelectorAll("[data-cp]").forEach((b) => b.onclick = () => cpAction(b.dataset.cp));
  await renderCpBody();
}

function renderCpTabs() {
  $("cpSection").querySelectorAll("[data-cptab]").forEach((b) => b.classList.toggle("on", b.dataset.cptab === cpState.tab));
}

async function cpAction(a) {
  const [kind, target] = a.split(":");
  if (kind === "swap") return openModal();
  if (target === "contracts") { cpState.tab = "schema"; renderCpTabs(); await renderCpBody(); return $("cpBody").scrollIntoView({ behavior: "smooth" }); }
  if (target === "api") { cpState.tab = "scaffold"; cpState.file = "src/fusion_fuel/api.py"; renderCpTabs(); await renderCpBody(); return $("cpBody").scrollIntoView({ behavior: "smooth" }); }
  if (target === "tools") return openTools();
  if (target === "knowledge") return openKnowledge();
  if (target === "decision") {
    $("modalTitle").textContent = "Decision router · why none";
    $("modalContent").innerHTML = `<p>A <b>decision model</b> (for example TypeSafe AI's JEV, a typed choice/score model) can do cheap routing and safety triage.
      For Fusion Fuel it is <b>not recommended</b>: the safety gate is a deterministic rule that runs before the model, and a decision model would save about <b>$2 per month</b> at 60k recipes.</p>
      <p>It is worth evaluating for high-volume triage, reranking or per-step checks inside agent loops. See PRD section 15.4.</p>`;
    $("modal").classList.remove("hidden");
  }
}

function codeBlock(text) { return `<pre class="cp-code"><code>${esc(text)}</code></pre>`; }

async function renderCpBody() {
  const el = $("cpBody");
  if (cpState.tab === "schema") {
    const c = state.contracts || (state.contracts = await api("/api/contracts"));
    el.innerHTML = `<div class="cp-toolbar"><div class="seg" style="width:auto">
        <button data-view="python" class="${cpState.schemaView === "python" ? "on" : ""}">Python (Pydantic v2)</button>
        <button data-view="json" class="${cpState.schemaView === "json" ? "on" : ""}">JSON Schema</button></div>
        <span class="muted cp-small">RecipeRequest@1.4.0 · RecipeCard@2.3.0 · x-aistack semantic tags (units, data classes)</span></div>
      ${cpState.schemaView === "python" ? codeBlock(c.source) : codeBlock(JSON.stringify(c.json_schema, null, 2))}`;
    el.querySelectorAll("[data-view]").forEach((b) => b.onclick = () => { cpState.schemaView = b.dataset.view; renderCpBody(); });
  } else if (cpState.tab === "synthetic") {
    const r = cpState.synth;
    el.innerHTML = `<div class="cp-toolbar">
        <label class="cp-small">Cases <select id="synN">${[5, 10, 20, 30].map((n) => `<option ${n === cpState.n ? "selected" : ""}>${n}</option>`).join("")}</select></label>
        <label class="cp-small">Seed <input id="synSeed" type="number" value="${cpState.seed}" style="width:80px"></label>
        <button class="btn filled small" id="synRun">Generate &amp; run on ${esc(state.status.models[state.modelKey].label)}</button>
        <span class="muted cp-small">Axes: cuisine pair · carb target · activity · exclusions · adversarial dosing (every 5th case)</span></div>
      ${r ? `<p><b>${r.passed}/${r.total} passed</b> ${r.simulated ? '<span class="chip-sim tiny">simulated model</span>' : '<span class="pill green">live</span>'} <span class="muted cp-small">${esc(r.note)}</span></p>
        <table class="sec-table"><tr><th>ID</th><th>Kind</th><th>Variables</th><th>Result</th><th>Why</th><th>Output</th></tr>
        ${r.cases.map((c) => `<tr><td class="comp">${esc(c.id)}</td><td>${esc(c.kind)}</td>
          <td>${c.kind === "safety" ? `"${esc(c.request.note)}"` : `${esc(c.request.cuisines.join(" + "))} · ${c.request.carb_target_g} g · ${esc(c.request.activity.replace("_", " "))}${c.request.exclusions && c.request.exclusions.length ? ` · exclude ${esc(c.request.exclusions.join(", "))}` : ""}`}</td>
          <td><span class="eq-badge ${c.status.toLowerCase()}">${c.status}</span></td><td>${esc(c.why)}</td>
          <td class="muted">${esc(c.title || "")}${c.carbs != null ? ` · ${c.carbs} g carbs` : ""}</td></tr>`).join("")}</table>`
      : `<p class="muted">Generate synthetic cases from the requirements and run them through the pipeline.</p>`}`;
    $("synN").onchange = () => { cpState.n = Number($("synN").value); };
    $("synSeed").onchange = () => { cpState.seed = Number($("synSeed").value) || 7; };
    $("synRun").onclick = () => busy($("synRun"), async () => {
      cpState.synth = await api("/api/synthetic", { method: "POST", body: JSON.stringify({ model_key: state.modelKey, n: cpState.n, seed: cpState.seed }) });
      renderCpBody();
    });
  } else {
    const s = cpState.scaffold || (cpState.scaffold = await api("/api/scaffold", { method: "POST", body: JSON.stringify({
      answers: answersObj(), follow_ups: state.followUps, model_key: state.modelKey, deployments: state.deployments, prd_text: state.prdText || "" }) }));
    const f = s.files.find((x) => x.path === cpState.file) || s.files[0];
    el.innerHTML = `<div class="cp-toolbar"><span class="muted cp-small">${s.files.length} files generated from the manifest · ${esc(s.root)}</span>
        <button class="btn tonal small" id="cpZip">Download app (.zip)</button><button class="btn text small" id="cpRefresh">Regenerate</button></div>
      <div class="cp-scaffold">
        <ul class="cp-files">${s.files.map((x) => `<li><button class="${x.path === f.path ? "on" : ""}" data-file="${esc(x.path)}">${esc(x.path)} <span class="muted">${x.lines}</span></button></li>`).join("")}</ul>
        <div class="cp-file"><div class="cp-file-h comp">${esc(f.path)}</div>${codeBlock(f.content)}</div>
      </div>`;
    el.querySelectorAll("[data-file]").forEach((b) => b.onclick = () => { cpState.file = b.dataset.file; renderCpBody(); });
    $("cpZip").onclick = () => $("btnGenerate").click();
    $("cpRefresh").onclick = () => { cpState.scaffold = null; renderCpBody(); };
  }
}
