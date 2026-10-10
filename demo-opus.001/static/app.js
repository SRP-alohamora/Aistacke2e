"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const usd = (v, d = 4) => (v == null ? "unknown" : "$" + Number(v).toFixed(v >= 100 ? 0 : v >= 1 ? 2 : d));

const QUESTIONS = ["What do you want to build?", "Who is the intended user?", "What should the application accomplish?",
  "Additional experience, tips or guidance"];
const TYPE_MS = [null, null, null, 6000]; // per-question typing time; null = 1-2 s by length
const GOALS = [
  { key: "balanced", label: "Balanced", carb: 45, info: "About 45 g carbs" },
  { key: "high_protein", label: "High protein", carb: 40, info: "35 g+ protein" },
  { key: "keto", label: "Keto (high protein + fat)", carb: 20, info: "≤ 25 g carbs, 30 g+ protein and fat" },
  { key: "high_fiber", label: "High fiber", carb: 45, info: "10 g+ fiber" },
  { key: "low_sodium", label: "Low sodium", carb: null, info: "≤ 600 mg sodium" },
];
const CUISINES = ["korean", "mexican", "japanese", "indian", "thai", "mediterranean", "italian", "american"];
const state = {
  step: 0,
  answers: ["A quick fusion-recipe app",
            "A physically active person managing type 1 diabetes",
            "Suggest 30-minute fusion meals that fit carb targets around workouts, using a nutrition database",
            "Generate the recipe with a picture of the recipe and a recipe card under it, and a left panel of tunable tiles " +
            "for organic, budget friendly, etc. Add a text box saying \"Enter ingredients available to find select recipes\". " +
            "Also allow adding another restriction."],
  prefs: { organic: false, budget_friendly: false },
  goals: new Set(["balanced"]),
  cuisines: new Set(["korean", "mexican"]), activity: "post_workout",
  restrictions: [], restrictionOptions: [], last: null, lastBudget: false,
  profile: null, followUps: {}, modelKey: null, deployments: {}, rec: null, status: null,
};

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "content-type": "application/json" }, ...opts });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return r.headers.get("content-type")?.includes("json") ? r.json() : r;
}
async function busy(btn, fn) { btn.disabled = true; try { await fn(); } catch (e) { alert(e.message); } finally { btn.disabled = false; } }
function show(id) { ["wizard", "prdScreen", "building", "app", "prod"].forEach((s) => $(s).classList.toggle("hidden", s !== id)); window.scrollTo(0, 0); }
const answersObj = () => ({ build: state.answers[0], user: state.answers[1], goal: state.answers[2], guidance: state.answers[3] });

async function loadStatus() {
  state.status = await api("/api/status");
  state.modelKey = state.modelKey || state.status.baseline;
  const m = state.status.models[state.modelKey];
  const live = m.mode === "live";
  for (const id of ["modeChip", "modeChip2"]) {
    $(id).className = "chip-mode" + (live ? " live" : "");
    $(id).textContent = live ? `Live · ${m.label}` : "Offline · simulated model";
  }
}

// Screen 1: wizard ----------------------------------------------------------------
// Each answer is "typed" into the box the first time its screen is shown (about 1-2 s).
const typing = { done: new Set(), timer: null, step: null };

function finishTyping() {
  if (!typing.timer) return;
  clearInterval(typing.timer);
  typing.timer = null;
  const s = typing.step;
  if (s === state.step) $("qInput").value = state.answers[s];
  $("sum" + s).textContent = state.answers[s];
  typing.done.add(s);
}

function typeAnswer(step) {
  const text = state.answers[step];
  const duration = TYPE_MS[step] || Math.min(2000, Math.max(1000, text.length * 30));
  const perChar = duration / Math.max(1, text.length);
  const start = performance.now();
  typing.step = step;
  $("qInput").value = "";
  $("sum" + step).textContent = "";
  typing.timer = setInterval(() => {
    const n = Math.min(text.length, Math.ceil((performance.now() - start) / perChar));
    const partial = text.slice(0, n);
    $("qInput").value = partial;
    $("sum" + step).textContent = partial;
    $("qInput").setSelectionRange(n, n);
    if (n >= text.length) finishTyping();
  }, 16);
}

function renderWizard() {
  finishTyping();
  const s = state.step;
  $("qText").textContent = QUESTIONS[s];
  $("qHint").classList.toggle("hidden", s !== 3);
  $("qInput").value = state.answers[s];
  $("stepLabel").textContent = `Question ${s + 1} of ${QUESTIONS.length}`;
  document.querySelectorAll(".dot").forEach((d) => d.classList.toggle("on", Number(d.dataset.s) <= s));
  document.querySelectorAll(".summary-row").forEach((row) => {
    const i = Number(row.dataset.s);
    row.classList.toggle("active", i === s);
    row.classList.toggle("done", i < s);
  });
  state.answers.forEach((a, i) => { $("sum" + i).textContent = i <= s ? a : ""; });
  $("btnBack").style.visibility = s === 0 ? "hidden" : "visible";
  $("btnNext").textContent = "Next";
  $("qInput").focus();
  $("qInput").setSelectionRange($("qInput").value.length, $("qInput").value.length);
  if (!typing.done.has(s)) typeAnswer(s);
}
$("qInput").addEventListener("input", () => { state.answers[state.step] = $("qInput").value; $("sum" + state.step).textContent = $("qInput").value; });
$("qInput").addEventListener("mousedown", finishTyping);
$("qInput").addEventListener("keydown", (e) => { if (typing.timer) { finishTyping(); if (e.key !== "Enter") return; } if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("btnNext").click(); } });
$("btnBack").onclick = () => { state.step = Math.max(0, state.step - 1); renderWizard(); };
$("btnNext").onclick = () => {
  finishTyping();
  if (!state.answers[state.step].trim()) { $("qInput").focus(); return; }
  if (state.step < QUESTIONS.length - 1) { state.step += 1; renderWizard(); } else showPrd();
};

// Screen 5: PRD typed from the answers --------------------------------------------------
const prdTyping = { timer: null };
async function showPrd() {
  show("prdScreen");
  $("prdText").value = "";
  $("prdStatus").textContent = "Drafting from your answers…";
  const d = await api("/api/prd", { method: "POST", body: JSON.stringify(answersObj()) });
  $("prdTitle").textContent = d.title;
  state.prdText = d.text;
  typePrd(d.text);
}
function typePrd(text) {
  clearInterval(prdTyping.timer);
  const start = performance.now(), perChar = 9000 / text.length; // whole document in about 9 s
  prdTyping.timer = setInterval(() => {
    const n = Math.min(text.length, Math.ceil((performance.now() - start) / perChar));
    $("prdText").value = text.slice(0, n);
    $("prdText").scrollTop = $("prdText").scrollHeight;
    if (n >= text.length) finishPrd();
  }, 30);
}
function finishPrd() {
  if (prdTyping.timer) { clearInterval(prdTyping.timer); prdTyping.timer = null; }
  if (state.prdText && $("prdText").value.length < state.prdText.length) $("prdText").value = state.prdText;
  $("prdStatus").textContent = "Draft ready - edit anything before generating";
}
$("prdText").addEventListener("input", () => { if (!prdTyping.timer) state.prdText = $("prdText").value; });
$("prdText").addEventListener("mousedown", finishPrd);
$("prdSkip").onclick = finishPrd;
$("prdBack").onclick = () => { finishPrd(); show("wizard"); renderWizard(); };
$("btnGenApp").onclick = () => { finishPrd(); state.prdText = $("prdText").value; buildApp(); };

async function buildApp() {
  show("building");
  const steps = ["Choosing the simplest architecture", "Generating typed contracts (RecipeRequest, RecipeCard)", "Generating your application"];
  let i = 0;
  const t = setInterval(() => { $("buildingStep").textContent = steps[Math.min(++i, steps.length - 1)]; }, 450);
  try {
    state.profile = await api("/api/profile", { method: "POST", body: JSON.stringify(answersObj()) });
    state.followUps = Object.fromEntries(state.profile.follow_ups.map((q) => [q.id, q.default]));
    state.rec = null;
    await new Promise((r) => setTimeout(r, 900));
    show("app");
    await findRecipe();
  } catch (e) { alert(e.message); show("wizard"); } finally { clearInterval(t); }
}

// Screen 2: app preview -------------------------------------------------------------
function renderControls() {
  $("cuisines").innerHTML = CUISINES.map((c) => `<button data-c="${c}" class="${state.cuisines.has(c) ? "on" : ""}">${c[0].toUpperCase() + c.slice(1)}</button>`).join("");
  $("cuisines").querySelectorAll("button").forEach((b) => b.onclick = () => {
    const c = b.dataset.c;
    if (state.cuisines.has(c)) { if (state.cuisines.size > 1) state.cuisines.delete(c); }
    else if (state.cuisines.size < 3) state.cuisines.add(c);
    renderControls();
  });
}
document.querySelectorAll(".tile").forEach((t) => t.onclick = () => {
  const k = t.dataset.pref;
  state.prefs[k] = !state.prefs[k];
  t.setAttribute("aria-pressed", String(state.prefs[k]));
  t.querySelector(".state-text").textContent = state.prefs[k] ? "On" : "Off";
  findRecipe();
});
function carbTarget() {
  const targets = GOALS.filter((g) => state.goals.has(g.key) && g.carb != null).map((g) => g.carb);
  return targets.length ? Math.min(...targets) : 45;
}
function renderGoals() {
  $("goals").innerHTML = GOALS.map((g) => `<button class="goal ${g.key === "keto" ? "wide-goal" : ""}" data-g="${g.key}" aria-pressed="${state.goals.has(g.key)}">
    <span class="goal-check">${state.goals.has(g.key) ? "✓" : ""}</span><span><b>${esc(g.label)}</b><small>${esc(g.info)}</small></span></button>`).join("");
  $("goals").querySelectorAll(".goal").forEach((b) => b.onclick = () => {
    const k = b.dataset.g;
    if (k === "balanced") state.goals = new Set(["balanced"]);
    else {
      state.goals.delete("balanced");
      state.goals.has(k) ? state.goals.delete(k) : state.goals.add(k);
      if (!state.goals.size) state.goals.add("balanced");
    }
    renderGoals();
    findRecipe();
  });
  const keto = state.goals.has("keto");
  $("goalInfo").innerHTML = `Carb target: <b>${carbTarget()} g</b> per meal` +
    (keto ? `<br><span class="keto-note">Very low-carb eating with type 1 diabetes should be planned with your care team.</span>` : "");
}
$("activity").querySelectorAll("button").forEach((b) => b.onclick = () => {
  state.activity = b.dataset.v;
  $("activity").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
});
$("btnFind").onclick = (e) => busy(e.target, findRecipe);

function renderRestrictions() {
  const opts = state.restrictionOptions;
  $("restrictions").innerHTML = state.restrictions.map((key, idx) => {
    const choices = opts.filter((o) => o.key === key || !state.restrictions.includes(o.key));
    return `<div class="restriction-row"><select data-idx="${idx}" aria-label="Health condition or restriction">${choices.map((o) =>
      `<option value="${o.key}" ${o.key === key ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select>
      <button data-remove="${idx}" aria-label="Remove">×</button></div>`;
  }).join("");
  $("btnAddRestriction").disabled = state.restrictions.length >= opts.length;
  $("restrictions").querySelectorAll("select").forEach((sel) => sel.onchange = () => {
    state.restrictions[Number(sel.dataset.idx)] = sel.value; renderRestrictions(); findRecipe();
  });
  $("restrictions").querySelectorAll("[data-remove]").forEach((b) => b.onclick = () => {
    state.restrictions.splice(Number(b.dataset.remove), 1); renderRestrictions(); findRecipe();
  });
}
$("btnAddRestriction").onclick = () => {
  const next = state.restrictionOptions.find((o) => !state.restrictions.includes(o.key));
  if (!next) return;
  state.restrictions.push(next.key);
  renderRestrictions();
  findRecipe();
};

async function findRecipe() {
  const pantry = $("pantry").value.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);
  const request = { cuisines: [...state.cuisines], carb_target_g: carbTarget(), activity: state.activity,
    nutrition_goals: [...state.goals],
    exclusions: [], organic: state.prefs.organic, budget_friendly: state.prefs.budget_friendly, available_ingredients: pantry,
    restrictions: state.restrictions };
  $("recipe").innerHTML = `<div class="empty"><div class="spinner" style="margin:0 auto 12px"></div>Finding a recipe…</div>`;
  const res = await api("/api/run", { method: "POST", body: JSON.stringify({ model_key: state.modelKey, request }) });
  const prev = state.last, prevBudget = state.lastBudget;
  $("recipe").innerHTML = renderRecipe(res, pantry, prev, prevBudget);
  if (res.card) { state.last = res; state.lastBudget = state.prefs.budget_friendly; }
  const apply = $("btnApplyBudget");
  if (apply) apply.onclick = () => busy(apply, applyBudgetOptions);
}

function renderSavings(res, prev, prevBudget) {
  const t = res.shopping.totals, opts = res.shopping.budget_options || [];
  let swaps = "";
  if (prev && prev.card && prev.shopping && !prevBudget) {
    const cost = (shop, n) => (shop.items.find((x) => x.name === n) || {}).wholefoods?.cost ?? 0;
    const before = prev.card.ingredients.map((i) => i.name), after = res.card.ingredients.map((i) => i.name);
    const removed = before.filter((n) => !after.includes(n)), added = after.filter((n) => !before.includes(n));
    const pairs = removed.map((r, i) => [r, added[i]])
      .filter(([r, a]) => a && cost(prev.shopping, r) > cost(res.shopping, a))
      .map(([r, a]) => `${esc(r)} → ${esc(a)} <span class="muted">(about $${(cost(prev.shopping, r) - cost(res.shopping, a)).toFixed(2)} less)</span>`);
    if (pairs.length) swaps = `<div class="sv-sub">Already swapped in this recipe</div><ul class="swaps">${pairs.map((p) => `<li>${p}</li>`).join("")}</ul>`;
  }
  const total = (t.wholefoods - t.walmart_with_options).toFixed(2);
  const optList = opts.length ? `
    <div class="sv-sub">Budget-friendly ingredient options</div>
    <ul class="swaps">${opts.map((o) => `<li><b>${esc(o.from)}</b> → <b>${esc(o.to)}</b> · save $${o.saves_usd.toFixed(2)}
      <span class="muted">· carbs ${o.carb_delta_g >= 0 ? "+" : ""}${o.carb_delta_g} g (rebalanced when applied)</span>
      <a class="store-link walmart" href="${esc(o.walmart_url)}" target="_blank" rel="noopener">${esc(o.to)} at Walmart</a></li>`).join("")}</ul>
    <button class="btn tonal small" id="btnApplyBudget">Use these options</button>`
    : `<div class="sv-sub">This recipe already uses the budget picks we know about.</div>`;
  return `<div class="savings">
    <div>Buy at Walmart instead of Whole Foods: <b>$${t.walmart.toFixed(2)}</b> vs $${t.wholefoods.toFixed(2)} · save <b>$${t.savings.toFixed(2)}</b> (${t.savings_pct}%) per serving</div>
    ${opts.length ? `<div class="sv-line">With the options below: <b>$${t.walmart_with_options.toFixed(2)}</b> at Walmart · <b>$${total}</b> less than Whole Foods</div>` : ""}
    ${swaps}${optList}
    <div class="fine">${esc(res.shopping.disclaimer)}</div></div>`;
}

function applyBudgetOptions() {
  const opts = (state.last && state.last.shopping && state.last.shopping.budget_options) || [];
  const pantry = $("pantry").value.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);
  for (const o of opts) if (!pantry.includes(o.to)) pantry.push(o.to);
  $("pantry").value = pantry.join(", ");
  return findRecipe();
}

function renderRecipe(res, pantry, prev, prevBudget) {
  if (res.status === "blocked") return `<div class="notice"><b>We can't help with that.</b> ${esc(res.blocked.message)}</div>`;
  if (res.status === "error") return `<div class="notice"><b>${esc(res.error.code)}</b> ${esc(res.error.detail)}${res.error.retryable ? " - try again." : ""}</div>`;
  const c = res.card;
  if (!c) return `<div class="notice"><b>The model's recipe failed validation</b>, so it was not shown. ${(res.validation_errors || []).map(esc).join("; ")}</div>`;
  const ok = Math.abs(c.carbs_g - c.carb_target_g) <= 5;
  const u = res.usage || {};
  const pills = [
    `<span class="pill">${c.prep_minutes} min</span>`,
    `<span class="pill ${ok ? "green" : "red"}">${c.carbs_g} g carbs · target ${c.carb_target_g} g</span>`,
    ...(c.goals || []).filter((g) => g.key !== "balanced").map((g) => `<span class="pill ${g.met ? "green" : "amber"}" title="${esc(g.checks.map((x) => x.text).join(", "))}">${g.met ? "✓" : "!"} ${esc(g.label)}: ${esc(g.checks.map((x) => x.text).join(", "))}</span>`),
    ...c.tags.map((t) => `<span class="pill blue">${esc(t)}</span>`),
    c.pantry_used.length ? `<span class="pill green">Uses your ${c.pantry_used.map(esc).join(", ")}</span>` : "",
    pantry.length && !c.pantry_used.length ? `<span class="pill amber">None of your ingredients fit this recipe</span>` : "",
    res.adjusted_by_tool ? `<span class="pill">Portions adjusted to hit your carb target</span>` : "",
  ].join("");
  const issues = [...(res.exclusion_violations || []), ...(res.pantry_unknown || []).map((x) => `"${x}" isn't in the nutrition table`)];
  return `
    ${res.photo ? `<div class="hero"><img src="${esc(res.photo.src)}" alt="${esc(res.photo.title)}">
      <div class="caption">Real photo of a similar dish (closest match in our library, not this exact recipe) ·
        <a href="${esc(res.photo.page)}" target="_blank" rel="noopener">${esc(res.photo.title)}</a> by ${esc(res.photo.artist)} ·
        <a href="${esc(res.photo.license_url)}" target="_blank" rel="noopener">${esc(res.photo.license)}</a></div></div>`
      : `<div class="hero">${window.recipeArt(c)}<div class="caption">Illustration drawn from this recipe's ingredients</div></div>`}
    <div class="recipe-card">
      <h2>${esc(c.title)}</h2>
      <div class="meta">${pills}</div>
      ${renderNutrients(c)}
      ${c.tags.includes("organic") ? `<p class="muted" style="margin-top:-6px">Choose organic versions of these ingredients where available.</p>` : ""}
      ${state.prefs.budget_friendly && res.shopping ? renderSavings(res, prev, prevBudget) : ""}
      <div class="two-col">
        <div><div class="sub">Ingredients</div>
          <table><tr><th>Item</th><th class="num">Grams</th><th class="num">Carbs</th></tr>
          ${c.ingredients.map((i) => `<tr><td>${esc(i.name)}${c.pantry_used.includes(i.name) ? ' <span class="pill green" style="padding:1px 6px">have</span>' : ""}${storeLinks(res, i.name)}</td><td class="num">${i.grams}</td><td class="num">${i.carbs_g} g</td></tr>`).join("")}
          <tr><td><b>Total</b></td><td></td><td class="num"><b>${c.carbs_g} g</b></td></tr></table>
          ${res.shopping && !state.prefs.budget_friendly ? `<div class="price-total">Estimated at Whole Foods: $${res.shopping.totals.wholefoods.toFixed(2)} per serving (sample prices)</div>` : ""}</div>
        <div><div class="sub">Steps</div><ol class="steps-list">${c.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol></div>
      </div>
      ${issues.length ? `<p class="note-line warn">${issues.map(esc).join(" · ")}</p>` : ""}
      <div class="disclaimer">${esc(c.disclaimer)}</div>
      <div class="how">${res.mode === "live" ? "Live model call" : "Simulated (offline) model"} · ${esc(u.model || "")} · carbs computed by the nutrition tool${u.latency_ms ? ` · ${u.latency_ms} ms` : ""}</div>
    </div>`;
}

function renderNutrients(c) {
  const n = c.nutrients;
  if (!n) return "";
  const dv = n.pct_daily_value;
  const lowSodium = state.restrictions.includes("low_sodium");
  const rows = [
    ["Carbs", `${n.carbs_g} g`, dv.carbs_g, ""],
    ["Protein", `${n.protein_g} g`, dv.protein_g, ""],
    ["Fat", `${n.fat_g} g`, dv.fat_g, ""],
    ["Sodium", `${n.sodium_mg} mg`, dv.sodium_mg, dv.sodium_mg > (lowSodium ? 20 : 35) ? "warn" : ""],
    ["Fiber", `${n.fiber_g} g`, dv.fiber_g, ""],
  ];
  return `<div class="nutrients">
    <div class="nutrients-head"><span>Nutrients per meal</span><span class="muted">${n.calories_kcal} kcal · % Daily Value</span></div>
    <div class="nutrient-grid">${rows.map(([label, val, pct, cls]) => `
      <div class="nutrient ${cls}"><div class="n-label">${label}</div><div class="n-val">${val}</div>
        <div class="n-bar"><span style="width:${Math.min(100, pct)}%"></span></div><div class="n-pct">${pct}% DV</div></div>`).join("")}
    </div>
    <div class="n-note">Approximate values from the demo nutrition table. % Daily Value uses FDA reference amounts for a 2,000 kcal diet.</div>
  </div>`;
}

function storeLinks(res, name) {
  const item = res.shopping && res.shopping.items.find((x) => x.name === name);
  if (!item) return "";
  const wfLink = `<a class="store-link" href="${esc(item.wholefoods.url)}" target="_blank" rel="noopener">Whole Foods $${item.wholefoods.cost.toFixed(2)}</a>`;
  if (state.prefs.budget_friendly) {
    const opt = (res.shopping.budget_options || []).find((o) => o.from === name);
    return `<div class="links">${wfLink}<a class="store-link walmart" href="${esc(item.walmart.url)}" target="_blank" rel="noopener">Walmart $${item.walmart.cost.toFixed(2)}</a></div>`
      + (opt ? `<div class="budget-opt">Budget option: ${esc(opt.to)} (−$${opt.saves_usd.toFixed(2)})</div>` : "");
  }
  return name === res.shopping.featured ? `<div class="links">${wfLink}</div>` : "";
}

// Screen 3: production deployment ---------------------------------------------------
$("btnProd").onclick = (e) => busy(e.target, async () => { show("prod"); await recommend(); });
$("btnBackApp").onclick = () => show("app");

document.querySelectorAll(".tab").forEach((t) => t.onclick = () => selectTab(t.dataset.tab));
async function selectTab(id) {
  document.querySelectorAll(".tab").forEach((x) => { const on = x.dataset.tab === id; x.classList.toggle("on", on); x.setAttribute("aria-selected", on); });
  ["tabArch", "tabEval", "tabGov"].forEach((x) => $(x).classList.toggle("hidden", x !== id));
  if (id === "tabGov") await renderGovernance();
  if (id === "tabEval") await renderEvalQuality();
}

async function renderGovernance() {
  $("tabGov").innerHTML = `<div class="card"><p class="muted">Loading…</p></div>`;
  const g = await api("/api/governance", { method: "POST", body: JSON.stringify({
    answers: answersObj(), follow_ups: state.followUps, model_key: state.modelKey, deployments: state.deployments }) });
  const icon = (st) => `<span class="sec-icon ${st}">${SEC_ICON[st]}</span>`;
  const checks = (rows) => `<table class="sec-table"><tr><th></th><th>Check</th><th>Finding</th><th>To reach green</th></tr>
    ${rows.map((c) => `<tr><td>${icon(c.status)}</td><td><b>${esc(c.check)}</b></td>
      <td>${c.href ? `<a href="${esc(c.href)}" target="_blank" rel="noopener">${esc(c.finding)}</a>` : esc(c.finding)}</td>
      <td class="muted">${esc(c.fix || (c.status === "pass" ? "Nothing needed" : "-"))}</td></tr>`).join("")}</table>`;
  const tally = (t) => `<span class="sec-row">${icon("pass")} ${t.pass}</span><span class="sec-row">${icon("warn")} ${t.warn}</span><span class="sec-row">${icon("fail")} ${t.fail}</span>`;
  const clsPill = (c) => `<span class="pill ${c === "health" ? "amber" : c === "confidential" ? "blue" : ""}">${esc(c)}</span>`;
  $("tabGov").innerHTML = `
    <div id="cpSection"><div class="card"><p class="muted">Loading control plane…</p></div></div>
    <h2 class="grc-h">Privacy &amp; governance</h2>
    <div class="card gov-summary">
      <div><div class="card-title">Privacy</div><div class="tally">${tally(g.summary.privacy)}</div></div>
      <div><div class="card-title">Governance</div><div class="tally">${tally(g.summary.governance)}</div></div>
      <p class="muted">${esc(g.note)}</p>
    </div>
    <div class="card"><div class="card-title">Data map <span class="muted">· from the contract's data-class tags</span></div>
      <table class="sec-table"><tr><th>Field</th><th>Data class</th><th>Flows to</th><th>Stored</th><th>Kept from model</th></tr>
      ${g.data_map.map((r) => `<tr><td class="comp">${esc(r.field)}</td><td>${clsPill(r.data_class)}</td><td>${r.flows_to.map(esc).join(" → ") || "-"}</td><td>${esc(r.stored)}</td><td>${r.minimised ? icon("pass") : "-"}</td></tr>`).join("")}</table></div>
    <div class="card"><div class="card-title">Third-party processors <span class="muted">· follows your "Runs on" choices</span></div>
      <table class="sec-table"><tr><th>Layer</th><th>Processor</th><th>Receives</th><th>DPA</th><th>Region</th></tr>
      ${g.processors.map((p) => `<tr><td>${esc(p.layer)}</td><td><b>${esc(p.processor)}</b></td><td>${esc(p.receives)}</td><td>${p.dpa === "verify" ? icon("warn") + " verify" : icon("pass") + " not needed"}</td><td class="muted">${esc(p.region)}</td></tr>`).join("")}</table></div>
    <div class="card"><div class="card-title">Privacy checks</div>${checks(g.privacy)}</div>
    <div class="card"><div class="card-title">Governance checks</div>${checks(g.governance)}</div>
    <div class="card"><div class="card-title">Framework mapping <span class="muted">· evidence mapping, not certification</span></div>
      <table class="sec-table"><tr><th>Framework</th><th>Evidence in this build</th></tr>
      ${g.frameworks.map((f) => `<tr><td><b>${esc(f.framework)}</b></td><td>${esc(f.evidence)}</td></tr>`).join("")}</table></div>
    <div class="card"><div class="card-title">Audit log <span class="muted">· this session, in memory</span></div>
      ${g.audit.length ? `<table class="sec-table"><tr><th>Time</th><th>Actor</th><th>Action</th><th>Detail</th></tr>
      ${g.audit.map((a) => `<tr><td class="comp">${esc(a.at)}</td><td>${esc(a.actor)}</td><td class="comp">${esc(a.action)}</td><td>${esc(a.detail)}</td></tr>`).join("")}</table>`
      : `<p class="muted">No changes yet.</p>`}</div>`;
  cpState.scaffold = null;
  await renderControlPlane();
}

async function recommend() {
  state.rec = await api("/api/recommend", { method: "POST", body: JSON.stringify({
    answers: answersObj(), follow_ups: state.followUps, model_key: state.modelKey, deployments: state.deployments }) });
  renderQuestions();
  renderCake();
  if (!$("tabGov").classList.contains("hidden")) renderGovernance();
  $("yaml").textContent = state.rec.yaml;
}

function renderQuestions() {
  const qs = state.rec.profile.follow_ups;
  $("questions").innerHTML = qs.length ? qs.map((q) => `
    <div class="q"><div><div class="q-text"><b>${esc(q.id)}.</b> ${esc(q.text)}</div>
      <div class="q-why">Changes: ${q.affects.map(esc).join(", ")}</div></div>
      <div class="seg" data-q="${q.id}" style="min-width:150px">
        <button data-v="1" class="${state.followUps[q.id] ? "on" : ""}">Yes</button><button data-v="0" class="${state.followUps[q.id] ? "" : "on"}">No</button></div></div>`).join("")
    : `<p class="muted">No questions: the defaults cover every decision.</p>`;
  $("questions").querySelectorAll(".seg").forEach((s) => s.onclick = (e) => {
    if (!e.target.dataset.v) return;
    state.followUps[s.dataset.q] = e.target.dataset.v === "1";
    recommend();
  });
}

function renderCake() {
  const rec = state.rec, c = rec.cost, per = c.per_successful_task_usd;
  $("simChip").classList.toggle("hidden", !c.simulated);
  const rows = rec.layers.map((l) => {
    if (l.state === "none") {
      return `<tr class="none-row"><td><div class="layer-name">${esc(l.friendly)}</div><div class="layer-purpose">${esc(l.purpose)}</div></td>
        <td>Not needed</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td class="note-line">${esc(l.rationale)}</td></tr>`;
    }
    const opts = l.deploymentOptions;
    const chosen = opts.find((o) => o.id === l.deployment);
    const sel = opts.length ? `<select data-layer="${l.key}" aria-label="Deployment for ${esc(l.friendly)}">${opts.map((o) => `<option value="${o.id}" ${o.id === l.deployment ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select>${l.compare ? `<div class="dep-note"><a href="#" class="compare-link" data-compare="${l.key}">Compare</a></div>` : ""}` : "-";
    const depNote = chosen ? `<div class="dep-note">Runs on ${esc(chosen.label)}: ${esc(chosen.note)}</div>` : "";
    let cost = `<small>≈ $0 per task</small>`;
    if (l.costKey === "model") cost = per ? `${usd(per.expected)}<small>${usd(per.low)}-${usd(per.high)} per success</small>` : `${usd(c.per_attempt_usd.expected)}<small>per attempt</small>`;
    else if (l.state === "managed") cost = `<small>fixed monthly</small>`;
    const comp = (l.key === "model"
      ? `<span class="comp">${esc(c.label)}</span><br><button class="link-btn" id="btnCompare">Compare models</button>`
      : `<span class="comp">${esc(l.component)}</span>`) + depNote;
    const notes = [`<div class="note-line info">${esc(l.rationale)}</div>`,
      l.key === "agent_registry" ? `<button class="link-btn" data-agents="1">Why · view the ${rec.agents.length} agents and tools</button>` : "",
      l.key === "retrieval_store" ? `<button class="link-btn" data-knowledge="1">Why · view domain, data processing and cleanup</button>` : "",
      l.key === "tooling" ? `<button class="link-btn" data-tools="1">Why · view the ${rec.tools.inventory.length} tools, params and drift</button>` : "", ...l.limits.map((x) => `<div class="note-line ${x.level}">${x.level === "warn" ? "! " : ""}${esc(x.text)}</div>`)].join("");
    const sub = l.parent ? " sub-layer" : "";
    return `<tr class="${sub}"><td><div class="layer-name">${l.parent ? '<span class="sub-mark">↳</span> ' : ""}${esc(l.friendly)}${l.parent ? ' <span class="pill">sub-layer of Tooling</span>' : ""}</div><div class="layer-purpose">${esc(l.purpose)}</div></td>
      <td>${comp}</td><td>${sel}</td><td class="cost">${cost}</td><td>${qualityCell(l)}</td><td>${guardCell(l)}</td><td>${securityCell(l)}</td><td>${provCell(l)}</td><td>${notes}</td></tr>`;
  }).join("");
  $("cake").innerHTML = `<tr><th>Layer</th><th>Current default component</th><th>Investigate Alternatives</th><th>Est. cost</th><th class="vcol">Eval &amp; Quality</th><th class="vcol">Guardrails</th><th class="vcol">Security</th><th class="vcol">Provenance &amp; Audit</th><th>Why</th></tr>${rows}`;
  $("cake").querySelectorAll("[data-compare]").forEach((a) => a.onclick = (e) => { e.preventDefault(); openCompare(a.dataset.compare); });
  $("cake").querySelectorAll("[data-prov]").forEach((a) => a.onclick = (e) => { e.preventDefault(); openProvenance(a.dataset.prov); });
  $("cake").querySelectorAll("[data-knowledge]").forEach((b) => b.onclick = openKnowledge);
  $("cake").querySelectorAll("[data-security]").forEach((a) => a.onclick = (e) => { e.preventDefault(); openSecurity(a.dataset.security); });
  $("cake").querySelectorAll("[data-agents]").forEach((b) => b.onclick = openAgents);
  $("cake").querySelectorAll("[data-tools]").forEach((b) => b.onclick = openTools);
  $("cake").querySelectorAll("[data-review]").forEach((a) => a.onclick = (e) => { e.preventDefault(); openGuardrails(a.dataset.review); });
  $("cake").querySelectorAll("select").forEach((s) => s.onchange = () => { state.deployments[s.dataset.layer] = s.value; recommend(); });
  $("btnCompare").onclick = openModal;
  $("cake").querySelectorAll("[data-info]").forEach((b) => b.onclick = (e) => { e.stopPropagation(); openInfo(b); });
  $("cake").querySelectorAll('a[href="#eval-quality"]').forEach((a) => a.onclick = (e) => { e.preventDefault(); selectTab("tabEval"); });
  const g = c.monthly.find((m) => m.scenario === "growth");
  $("total").innerHTML = per
    ? `Cost per successful recipe: <b>${usd(per.expected)}</b> <span class="muted">(${usd(per.low)}-${usd(per.high)})</span> · at ${g.tasks_per_month.toLocaleString()} recipes/month: <b>${usd(g.marginal_usd.expected, 2)}</b> + ${usd(g.fixed_usd, 0)} fixed
       <div class="assump">${c.assumptions.map(esc).join(" · ")} · prices as of ${esc(c.price_catalog_version)}</div>`
    : `Cost per recipe attempt: <b>${usd(c.per_attempt_usd.expected)}</b>. Cost per <i>successful</i> recipe needs an eval run - open Compare models.`;
}

$("btnEnhance").onclick = (e) => busy(e.target, async () => {
  const text = $("enhanceText").value.trim();
  if (!text) { $("enhanceText").focus(); return; }
  $("enhanceOut").innerHTML = `<p class="muted">Drafting…</p>`;
  const d = await api("/api/enhancements", { method: "POST", body: JSON.stringify({
    text, answers: answersObj(), follow_ups: state.followUps, model_key: state.modelKey, deployments: state.deployments }) });
  const table = (rows, cols) => `<table><tr>${cols.map((c) => `<th>${c[0]}</th>`).join("")}</tr>${rows.map((r) => `<tr>${cols.map((c) => `<td>${esc(r[c[1]])}</td>`).join("")}</tr>`).join("")}</table>`;
  $("enhanceOut").innerHTML = `<div class="prd">
    <div class="prd-head"><h3>${esc(d.title)}</h3><span class="pill ${d.drafted_by.includes("live") ? "green" : ""}">${esc(d.drafted_by)}</span></div>
    <p>${esc(d.summary)}</p>
    <div class="sub">New requirements</div>
    <ul>${d.requirements.map((r) => `<li><b>${esc(r.id)}</b> <span class="muted">(${esc(r.kind)})</span> ${esc(r.text)}</li>`).join("")}</ul>
    <div class="sub">Architecture changes</div>${table(d.layer_changes, [["Layer", "layer"], ["Change", "change"], ["Why", "why"]])}
    <div class="sub">Contract changes</div>${table(d.contract_changes, [["Contract", "contract"], ["Change", "change"], ["Version", "version"]])}
    <div class="sub">Acceptance criteria</div><ul>${d.acceptance_criteria.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
    <div class="sub">Risks and open questions</div><ul>${d.risks.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
    <div class="sub">Cost impact</div><p>${esc(d.cost_impact)}</p>
    <div class="actions"><button class="btn tonal" id="btnCopyPrd">Copy as Markdown</button></div></div>`;
  $("btnCopyPrd").onclick = async () => {
    try { await navigator.clipboard.writeText(d.markdown); $("btnCopyPrd").textContent = "Copied"; }
    catch { $("btnCopyPrd").textContent = "Copy failed - select the text instead"; }
  };
});

function qualityCell(l) {
  const q = l.quality || { status: "na", summary: "-", details: [] };
  const icon = { ok: "✓", warn: "!", na: "–" }[q.status] || "–";
  const info = q.info ? ` <button class="info-i" data-info="${l.key}" aria-label="What does this mean?" title="What does this mean?">i</button>` : "";
  return `<div class="q-cell ${q.status}"><span class="q-icon">${icon}</span><span>${esc(q.summary)}${info}${q.simulated ? ' <span class="chip-sim tiny">simulated</span>' : ""}
    ${q.details.length ? `<small>${q.details.map(esc).join(" · ")}</small>` : ""}
    ${q.link ? `<a class="tiny-link" href="${esc(q.link.href)}"${q.link.href.startsWith("#") ? "" : ' target="_blank" rel="noopener"'}>${esc(q.link.text)}</a>` : ""}</span></div>`;
}

function guardCell(l) {
  const g = l.guardrails || [], n = g.length, enforced = g.filter((x) => x.status === "enforced").length;
  return n ? `<div class="g-cell"><span class="g-count">${enforced} enforced${n > enforced ? ` <span class="muted">+ ${n - enforced} other</span>` : ""}</span><a href="#" class="review-link" data-review="${l.key}">Review</a></div>` : `<span class="muted">-</span>`;
}

function openInfo(btn) {
  closeInfo();
  const q = state.rec.layers.find((x) => x.key === btn.dataset.info).quality.info;
  const all = q.passed === q.total;
  const lead = all
    ? `<b>Dosing refused ${q.passed}/${q.total}</b> means ${q.total === 2 ? "both" : "all"} of the eval suite's safety test cases were correctly blocked: the user asked about insulin dosing, and the app refused before the AI model was ever called.`
    : `<b>Dosing refused ${q.passed}/${q.total}</b> means only ${q.passed} of the ${q.total} safety test cases were blocked. At least one dosing question reached the model, so this check fails.`;
  const pop = document.createElement("div");
  pop.className = "info-pop";
  pop.setAttribute("role", "dialog");
  pop.innerHTML = `<button class="info-x" aria-label="Close">×</button>
    <p>${lead}</p>
    <p>The ${q.total === 2 ? "two" : q.total} test cases are:</p>
    <ul>${q.cases.map((c) => `<li><b>${esc(c.id)}:</b> "${esc(c.text)}"</li>`).join("")}</ul>
    <p><b>Why it matters.</b> The app must never give insulin or medication dosing advice (requirement R5).</p>`;
  document.body.appendChild(pop);
  const r = btn.getBoundingClientRect();
  pop.style.top = `${window.scrollY + r.bottom + 6}px`;
  pop.style.left = `${Math.max(12, Math.min(window.scrollX + r.left - 20, window.scrollX + document.documentElement.clientWidth - pop.offsetWidth - 12))}px`;
  pop.querySelector(".info-x").onclick = closeInfo;
  pop.onclick = (e) => e.stopPropagation();
  setTimeout(() => document.addEventListener("click", closeInfo, { once: true }), 0);
}
function closeInfo() { document.querySelectorAll(".info-pop").forEach((p) => p.remove()); }
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeInfo(); });

function provCell(l) {
  const p = l.provenance;
  if (!p) return `<span class="muted">-</span>`;
  const src = p.source === "user" ? '<span class="pill blue">user</span>' : p.source.startsWith("decision") ? `<span class="pill amber">${esc(p.source)}</span>` : '<span class="pill">inferred</span>';
  return `<div class="g-cell"><span>${src}</span><span class="muted">${p.changes} change${p.changes === 1 ? "" : "s"} this session</span>
    <span class="muted">catalog ${esc(p.catalog_version)}</span><a href="#" class="review-link" data-prov="${l.key}">Audit</a></div>`;
}

function openProvenance(key) {
  const l = state.rec.layers.find((x) => x.key === key), p = l.provenance;
  $("modalTitle").textContent = `Provenance & audit · ${l.friendly}`;
  $("modalContent").innerHTML = `
    <table class="sec-table">
      <tr><td><b>Selection</b></td><td>${esc(l.component || "-")}${p.deployment ? ` · runs on <b>${esc(p.deployment)}</b>` : ""}</td></tr>
      <tr><td><b>Source</b></td><td>${esc(p.source)} <span class="muted">(user = you changed it; decision Qn = set by your answer; inferred = recommender default)</span></td></tr>
      <tr><td><b>Driven by</b></td><td>${p.driven_by.length ? p.driven_by.map(esc).join(", ") : "-"}</td></tr>
      <tr><td><b>Backed by</b></td><td>${p.sources.map((x) => x.href ? `<a href="${esc(x.href)}" target="_blank" rel="noopener">${esc(x.text)}</a>` : esc(x.text)).join(" · ")}</td></tr>
      <tr><td><b>Catalog version</b></td><td>${esc(p.catalog_version)}</td></tr>
    </table>
    <div class="sub">Change history this session</div>
    ${p.events.length ? `<table class="sec-table"><tr><th>Time</th><th>Actor</th><th>Action</th><th>Detail</th></tr>
      ${p.events.map((a) => `<tr><td class="comp">${esc(a.at)}</td><td>${esc(a.actor)}</td><td class="comp">${esc(a.action)}</td><td>${esc(a.detail)}</td></tr>`).join("")}</table>`
      : `<p class="muted">No changes to this layer yet.</p>`}
    <p class="muted" style="font-size:12px">Audit events are kept in memory for this session; production stores them append-only and hash-chained (PRD FR-PLT-3).</p>`;
  $("modal").classList.remove("hidden");
}

function openCompare(key) {
  const l = state.rec.layers.find((x) => x.key === key), c = l.compare;
  $("modalTitle").textContent = `Compare "Runs on" choices · ${l.friendly}`;
  $("modalContent").innerHTML = `<div class="table-scroll"><table class="sec-table compare">
    <tr><th></th>${c.options.map((o) => `<th class="${o.selected ? "sel" : ""}">${esc(o.label)}${o.selected ? ' <span class="pill blue">selected</span>' : ""}</th>`).join("")}</tr>
    ${c.groups.map((g) => `<tr class="grp"><td colspan="${c.options.length + 1}">${esc(g.name)}</td></tr>` +
      g.rows.map((r) => `<tr><td><b>${esc(r.label)}</b></td>${c.options.map((o) => `<td class="${o.selected ? "sel" : ""}">${esc(o.values[r.key])}</td>`).join("")}</tr>`).join("")).join("")}
    <tr><td></td>${c.options.map((o) => `<td class="${o.selected ? "sel" : ""}">${o.selected ? "" : `<button class="btn tonal small" data-use="${o.id}">Use this</button>`}</td>`).join("")}</tr>
  </table></div><p class="muted" style="font-size:12px">${esc(c.note)}</p>`;
  $("modalContent").querySelectorAll("[data-use]").forEach((b) => b.onclick = () => busy(b, async () => {
    state.deployments[key] = b.dataset.use;
    $("modal").classList.add("hidden");
    await recommend();
  }));
  $("modal").classList.remove("hidden");
}

function openKnowledge() {
  const k = state.rec.knowledge;
  const icon = (st) => `<span class="sec-icon ${st}">${SEC_ICON[st]}</span>`;
  $("modalTitle").textContent = "Knowledge · domain, data processing and cleanup";
  $("modalContent").innerHTML = `
    <p><b>Domain:</b> ${esc(k.domain.name)}</p>
    <div class="sub">Knowledge sources</div>
    <table class="sec-table"><tr><th>Source</th><th>Kind</th><th class="num">Records</th><th>Owner</th><th>Note</th></tr>
      ${k.domain.sources.map((x) => `<tr><td><b>${esc(x.name)}</b></td><td>${esc(x.kind)}</td><td class="num">${k.sizes[x.size_fn]}</td><td>${esc(x.owner)}</td><td class="muted">${esc(x.note || "")}</td></tr>`).join("")}</table>
    <div class="sub">Data processing pipeline</div>
    <ol class="steps-list">${k.pipeline.map((p) => `<li><b>${esc(p.step)}</b> - ${esc(p.what)}</li>`).join("")}</ol>
    <div class="sub">Cleanup and quality checks <span class="muted">(run on every analysis: ${k.passed}/${k.total} pass)</span></div>
    <table class="sec-table">${k.checks.map((c) => `<tr><td>${icon(c.status)}</td><td><b>${esc(c.check)}</b></td><td>${esc(c.detail)}</td></tr>`).join("")}</table>
    <div class="sub">Domain vocabulary</div><p>${k.domain.vocabulary.map(esc).join(" · ")}</p>`;
  $("modal").classList.remove("hidden");
}

// Meaning of each status colour, used for tooltips, screen readers and the exported plan (no colour names shown).
const ENT_LABEL = { green: "In place", mustard: "Minor gaps", orange: "Partial", red: "Missing" };
const entDot = (st) => `<span class="ent-dot ${st}" role="img" aria-label="${ENT_LABEL[st]}" title="${ENT_LABEL[st]}"></span>`;
$("btnEnterprise").onclick = (e) => busy(e.target, openEnterprise);
$("btnEnhancements").onclick = () => $("enhModal").classList.remove("hidden");
$("enhClose").onclick = () => $("enhModal").classList.add("hidden");
$("enhModal").onclick = (e) => { if (e.target === $("enhModal")) $("enhModal").classList.add("hidden"); };

const ENT_FILTERS = ["Security", "Governance", "Scalability", "High availability", "Resiliency", "Quality"];
state.entFilter = new Set();

async function openEnterprise() {
  const r = await api("/api/enterprise", { method: "POST", body: JSON.stringify({
    answers: answersObj(), follow_ups: state.followUps, model_key: state.modelKey, deployments: state.deployments }) });
  state.enterprise = r;
  $("modalTitle").textContent = "Enterprise readiness review report";
  $("modal").querySelector(".modal-body").classList.add("wide");
  $("modalContent").innerHTML = `
    <p class="ent-headline">${esc(r.headline)}</p>
    <div class="ent-filters" role="group" aria-label="Focus areas">
      ${ENT_FILTERS.map((f) => `<button class="ent-tile" data-f="${esc(f)}" aria-pressed="${state.entFilter.has(f)}">${esc(f)}</button>`).join("")}
      <span class="muted ent-filter-hint" id="entHint"></span>
    </div>
    <div id="entBoard"></div>
    <div class="actions"><button class="btn filled" id="btnEnable">Enable selected (<span id="selCount">${r.plan.length}</span>)</button>
      <button class="btn tonal" id="btnCopyPlan">Copy plan as Markdown</button></div>
    <p class="muted" style="font-size:12px">${esc(r.note)}</p>`;
  $("modalContent").querySelectorAll(".ent-tile").forEach((t) => t.onclick = () => {
    const f = t.dataset.f;
    state.entFilter.has(f) ? state.entFilter.delete(f) : state.entFilter.add(f);
    t.setAttribute("aria-pressed", state.entFilter.has(f));
    renderEntBoard();
  });
  renderEntBoard();
  $("btnEnable").onclick = () => busy($("btnEnable"), async () => {
    const ids = [...new Set([...state.enterprise.plan.filter((id) => !$("modalContent").querySelector(`[data-rec="${id}"]`)),
      ...[...$("modalContent").querySelectorAll("[data-rec]:checked")].map((c) => c.dataset.rec)])];
    await api("/api/enterprise/plan", { method: "POST", body: JSON.stringify({ ids }) });
    await openEnterprise();
    await recommend();
  });
  $("btnCopyPlan").onclick = async () => {
    const sel = new Set(state.enterprise.plan);
    const lines = ["## Enterprise enablement plan", ""];
    for (const it of r.items) {
      const picked = it.recommendations.filter((x) => sel.has(x.id));
      if (picked.length) lines.push(`### ${it.name} (${ENT_LABEL[it.status]})`, ...picked.map((x) => `- [ ] ${x.text} - effort ${x.effort}, cost ${x.cost}, ${x.phase}`), "");
    }
    if (lines.length === 2) lines.push("_No recommendations enabled yet._");
    try { await navigator.clipboard.writeText(lines.join("\n")); $("btnCopyPlan").textContent = "Copied"; }
    catch { $("btnCopyPlan").textContent = "Copy failed"; }
  };
  $("modal").classList.remove("hidden");
}

function renderEntBoard() {
  const r = state.enterprise, sel = new Set(r.plan), f = state.entFilter;
  const items = r.items.map((it, i) => ({ it, i })).filter(({ it }) => !f.size || it.pillars.some((p) => f.has(p)));
  const pts = { green: 3, mustard: 2, orange: 1, red: 0 };
  const counts = { green: 0, mustard: 0, orange: 0, red: 0 };
  items.forEach(({ it }) => counts[it.status]++);
  const score = items.length ? Math.round(100 * items.reduce((a, { it }) => a + pts[it.status], 0) / (3 * items.length)) : 0;
  $("entHint").textContent = f.size ? `Showing ${items.length} of ${r.items.length} capabilities for ${[...f].join(", ")}` : `Showing all ${r.items.length} capabilities - pick tiles to focus`;
  const rows = items.map(({ it, i }) => {
    const enabled = it.recommendations.filter((x) => x.enabled).length;
    return `<tr class="ent-row">
      <td><b>${esc(it.name)}</b><div class="pillars">${it.pillars.map((p) => `<span class="pill ${f.has(p) ? "blue" : ""}">${esc(p)}</span>`).join("")}</div></td>
      <td>${entDot(it.status)}</td>
      <td>${it.href ? `<a href="${esc(it.href)}" target="_blank" rel="noopener">${esc(it.current)}</a>` : esc(it.current)}</td>
      <td class="muted">${esc(it.gap)}</td>
      <td><a href="#" class="review-link" data-ent="${i}">Review &amp; enable select recommendations</a>${enabled ? `<div class="g-count">${enabled} in plan</div>` : ""}</td></tr>
    <tr class="ent-recs hidden" id="ent${i}"><td colspan="5"><div class="rec-list">
      ${it.recommendations.map((x) => `<label class="rec"><input type="checkbox" data-rec="${x.id}" ${sel.has(x.id) ? "checked" : ""}>
        <span><b>${esc(x.text)}</b><small>effort ${esc(x.effort)} · cost ${esc(x.cost)} · ${esc(x.phase)}</small></span></label>`).join("")}
    </div></td></tr>`;
  }).join("");
  $("entBoard").innerHTML = `
    <div class="ent-summary"><div class="ent-score"><span>${score}%</span><small>readiness${f.size ? " (selection)" : ""}</small></div>
      ${Object.entries(counts).map(([k, v]) => `<span class="ent-count" title="${ENT_LABEL[k]}">${entDot(k)}${v}</span>`).join("")}</div>
    <div class="table-scroll"><table class="sec-table ent-table">
      <tr><th>Capability</th><th>Status</th><th>In place today</th><th>Gap</th><th></th></tr>${rows}</table></div>`;
  $("entBoard").querySelectorAll("[data-ent]").forEach((a) => a.onclick = (e) => {
    e.preventDefault(); $("ent" + a.dataset.ent).classList.toggle("hidden");
  });
  const count = () => { $("selCount").textContent = new Set([...r.plan.filter((id) => !$("entBoard").querySelector(`[data-rec="${id}"]`)),
    ...[...$("entBoard").querySelectorAll("[data-rec]:checked")].map((c) => c.dataset.rec)]).size; };
  $("entBoard").querySelectorAll("[data-rec]").forEach((c) => c.onchange = count);
}

function openTools() {
  const t = state.rec.tools, inv = t.inventory;
  const drifted = inv.filter((x) => x.drift !== "ok");
  const calls = t.last_calls || [];
  const driftBadge = (d) => d === "ok" ? '<span class="sec-icon pass">✓</span>' : `<span class="sec-level fail">${esc(d)}</span>`;
  $("modalTitle").textContent = "Tooling · Fusion Fuel";
  $("modalContent").innerHTML = `
    <p class="muted">${inv.length} typed in-process tools, all invoked by the pipeline (the model never chooses a tool).
      Parameter drift: ${drifted.length ? `<b style="color:var(--red)">${drifted.length} drifted</b>` : '<b style="color:var(--green)">none</b>'} against the registered schema hashes.</p>
    <div class="sub">Tool inventory and parameters</div>
    <table class="sec-table"><tr><th>Tool</th><th>Adapter</th><th>Parameters</th><th>Schema hash</th><th>Drift</th></tr>
      ${inv.map((x) => `<tr><td><b>${esc(x.name)}</b><div class="muted">${esc(x.role)}</div></td><td>${esc(x.adapter)}</td>
        <td class="comp">${x.params.map((p) => `${esc(p.name)}: ${esc(p.type)}${p.default ? ` = ${esc(p.default)}` : ""}`).join("<br>")}</td>
        <td class="comp">${esc(x.hash)}</td><td>${driftBadge(x.drift)}</td></tr>`).join("")}</table>
    <div class="sub">Tool invocations in the last recipe run</div>
    ${calls.length ? `<table class="sec-table"><tr><th>#</th><th>Tool</th><th>Parameters</th><th class="num">ms</th><th>Status</th></tr>
      ${calls.map((c, i) => `<tr><td>${i + 1}</td><td class="comp">${esc(c.tool)}</td><td class="comp">${esc(Object.entries(c.params).map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`).join(", "))}</td><td class="num">${c.ms}</td><td>${esc(c.status)}</td></tr>`).join("")}</table>`
      : `<p class="muted">No recipe run yet - go back to the app and find a recipe.</p>`}
    <div class="sub">External tools via MCP</div>
    ${t.mcp_servers.length ? "" : `<p>None connected. Typed adapters cover every tool today. MCP is added only where third-party tools exist:</p>
      <ul>${t.mcp_candidates.map((c) => `<li><b>${esc(c.name)}</b> - ${esc(c.why)}</li>`).join("")}</ul>`}`;
  $("modal").classList.remove("hidden");
}

function openAgents() {
  const list = state.rec.agents;
  const llm = list.filter((a) => a.kind.startsWith("LLM")).length;
  $("modalTitle").textContent = "Agent registry · Fusion Fuel";
  $("modalContent").innerHTML = `
    <p class="muted">${list.length} entries: ${llm} LLM-backed agents and ${list.length - llm} deterministic tools. No supervisor agent or multi-agent orchestration - each runs as one step of the pipeline.</p>
    <div class="agent-grid">${list.map((a) => `
      <div class="agent">
        <div class="agent-head"><b>${esc(a.name)}</b><span class="pill ${a.kind.startsWith("LLM") ? "blue" : ""}">${esc(a.kind)}</span><span class="pill">${esc(a.scope)}</span></div>
        <div class="agent-role">${esc(a.role)}</div>
        ${a.model ? `<div class="agent-row"><span>Model</span>${esc(a.model)}</div>` : ""}
        <div class="agent-row"><span>Skills</span>${a.skills.map(esc).join(" · ")}</div>
        <div class="agent-row"><span>Capabilities</span>${a.capabilities.map(esc).join(" · ")}</div>
        <div class="agent-row"><span>Data</span>${esc(a.data)}</div>
        <div class="agent-row"><span>Side effects</span>${esc(a.side_effects)}</div>
        <div class="agent-row"><span>Guardrails</span>${a.guardrails.map(esc).join(" · ")}</div>
      </div>`).join("")}</div>`;
  $("modal").classList.remove("hidden");
}

const SEC_ICON = { pass: "✓", warn: "!", fail: "✕", na: "–" };
const SEC_SHORT = { "Authentication": "AuthN", "Authorization": "AuthZ", "Zero trust": "Zero trust",
  "Continuous evaluation": "Cont. eval", "Zero-trust isolation": "Isolation" };
function secBadge(c) {
  if (c.level && c.level !== "High") return `<span class="sec-level ${c.status}">${esc(c.level)}</span>`;
  return `<span class="sec-icon ${c.status}">${SEC_ICON[c.status]}</span>`;
}
function securityCell(l) {
  const checks = l.security || [];
  if (!checks.length) return `<span class="muted">-</span>`;
  return `<div class="sec-cell">${checks.map((c) => `<div class="sec-row" title="${esc(c.check)}: ${esc(c.finding)}">${secBadge(c)}<span>${esc(SEC_SHORT[c.check] || c.check)}</span></div>`).join("")}
    <a href="#" class="review-link" data-security="${l.key}">Review</a></div>`;
}
function openSecurity(key) {
  const l = state.rec.layers.find((x) => x.key === key);
  $("modalTitle").textContent = `Security · ${l.friendly}`;
  $("modalContent").innerHTML = `<table class="sec-table"><tr><th></th><th>Check</th><th>Finding</th><th>To reach green</th></tr>
    ${l.security.map((c) => `<tr><td>${secBadge(c)}</td><td><b>${esc(c.check)}</b></td>
      <td>${c.href ? `<a href="${esc(c.href)}" target="_blank" rel="noopener">${esc(c.finding)}</a>` : esc(c.finding)}</td>
      <td class="muted">${esc(c.fix || (c.status === "pass" ? "Nothing needed" : "-"))}</td></tr>`).join("")}</table>
    <p class="muted" style="font-size:12px">✓ in place · ! partial or not yet configured · ✕ missing · – not applicable. Isolation shows High (✓), Medium or Low. Scored against what this build actually does, not what is planned.</p>`;
  $("modal").classList.remove("hidden");
}

function openGuardrails(key) {
  const l = state.rec.layers.find((x) => x.key === key);
  $("modalTitle").textContent = `Guardrails · ${l.friendly}`;
  $("modalContent").innerHTML = `<ul class="guard-list">${l.guardrails.map((g) =>
    `<li><a href="${esc(g.href)}" target="_blank" rel="noopener">${esc(g.text)}</a> <span class="g-status ${g.status}">${esc(g.status)}</span></li>`).join("")}</ul>
    <p class="muted" style="font-size:12px">Each link opens the line of code or data behind it (read-only). <b>enforced</b> = checked in code · <b>prompt</b> = instruction to the model, not a hard check · <b>declared</b> = stated in the manifest, not enforced in this demo · <b>review</b> = open item.</p>`;
  $("modal").classList.remove("hidden");
}

$("btnYaml").onclick = () => $("yaml").classList.toggle("hidden");
$("btnGenerate").onclick = (e) => busy(e.target, async () => {
  const r = await fetch("/api/generate", { method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ answers: answersObj(), follow_ups: state.followUps, model_key: state.modelKey, deployments: state.deployments,
      prd_text: state.prdText || "" }) });
  if (!r.ok) throw new Error(await r.text());
  const url = URL.createObjectURL(await r.blob());
  Object.assign(document.createElement("a"), { href: url, download: "fusion-fuel.zip" }).click();
  URL.revokeObjectURL(url);
});

// Model comparison ------------------------------------------------------------------
async function openModal() {
  $("modalTitle").textContent = "Compare models";
  $("modal").classList.remove("hidden");
  $("modalContent").innerHTML = `<p class="muted">Loading…</p>`;
  const data = await api("/api/models/compare");
  const cols = data.models;
  const cell = (fn) => cols.map((m) => `<td>${fn(m)}</td>`).join("");
  const ev = (m) => m.evidence;
  $("modalContent").innerHTML = `
  <table class="compare">
    <tr><th></th>${cols.map((m) => `<th>${esc(m.cost.label)}${m.model_key === state.modelKey ? ' <span class="pill blue">selected</span>' : ""}<div class="muted">${m.mode === "live" ? "Live" : "Offline · simulated"}</div></th>`).join("")}</tr>
<tr class="grp"><td colspan="${cols.length + 1}">Cost</td></tr>
    <tr><th>List price in / out per 1M tokens</th>${cell((m) => `$${m.cost.prices.input} / $${m.cost.prices.output}`)}</tr>
    <tr><th>Cost per successful recipe</th>${cell((m) => m.cost.per_successful_task_usd ? `<b>${usd(m.cost.per_successful_task_usd.expected)}</b>` : `<span class="muted">unknown - run eval</span>`)}</tr>
    <tr><th>At 60k recipes / month</th>${cell((m) => usd(m.cost.monthly.find((x) => x.scenario === "growth").marginal_usd.expected, 2))}</tr>
<tr class="grp"><td colspan="${cols.length + 1}">Capability</td></tr>
    <tr><th>Recipes passing all checks</th>${cell((m) => ev(m) ? `${ev(m).success.passed} of ${ev(m).success.total}` : "-")}</tr>
    <tr><th>Schema · exclusions · dosing refused</th>${cell((m) => ev(m) ? `${ev(m).metrics.schema_valid.passed}/${ev(m).metrics.schema_valid.total} · ${ev(m).metrics.exclusions_respected.passed}/${ev(m).metrics.exclusions_respected.total} · ${ev(m).metrics.dosing_refused.passed}/${ev(m).metrics.dosing_refused.total}` : "-")}</tr>
    <tr><th>Model carb accuracy before tool</th>${cell((m) => ev(m) ? `${Math.round(ev(m).metrics.draft_within_15pct.rate * 100)}% within 15%` : "-")}</tr>
    <tr><th>Features used</th>${cell((m) => m.mode && m.cost.prices.cache_read != null ? "structured output · prompt caching" : "structured output · caching discount unverified")}</tr>
<tr class="grp"><td colspan="${cols.length + 1}">Performance</td></tr>
    <tr><th>Latency p50 / p95</th>${cell((m) => ev(m) ? `${(ev(m).latency_ms.p50 / 1000).toFixed(1)} s / ${(ev(m).latency_ms.p95 / 1000).toFixed(1)} s` : "unverified")}</tr>
<tr class="grp"><td colspan="${cols.length + 1}">Compatibility</td></tr>
    <tr><th>Safe to swap in?</th>${cell((m) => `<span class="verdict ${m.compat.verdict}">${esc(m.compat.verdict)}</span>${m.compat.simulated ? ' <span class="chip-sim">simulated</span>' : ""}<ul class="reasons">${(m.compat.reasons || []).slice(0, 2).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>`)}</tr>
    <tr><th></th>${cell((m) => `<button class="btn tonal" data-eval="${m.model_key}">Run eval</button> <button class="btn filled" data-select="${m.model_key}">Use</button>`)}</tr>
  </table>
  <p class="muted" style="font-size:12px">Demo-grade: 10 test cases. A real verdict needs at least 25 cases and confidence intervals.</p>`;
  $("modalContent").querySelectorAll("[data-eval]").forEach((b) => b.onclick = () => busy(b, async () => {
    b.textContent = "Running…";
    await api(`/api/evals/${b.dataset.eval}`, { method: "POST" });
    await openModal(); await recommend();
  }));
  $("modalContent").querySelectorAll("[data-select]").forEach((b) => b.onclick = () => busy(b, async () => {
    state.modelKey = b.dataset.select;
    delete state.deployments.model;
    $("modal").classList.add("hidden");
    await loadStatus(); await recommend();
  }));
}
$("modalClose").onclick = () => $("modal").classList.add("hidden");
new MutationObserver(() => { if ($("modal").classList.contains("hidden")) $("modal").querySelector(".modal-body").classList.remove("wide"); })
  .observe($("modal"), { attributes: true, attributeFilter: ["class"] });
$("modal").onclick = (e) => { if (e.target === $("modal")) $("modal").classList.add("hidden"); };
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { $("modal").classList.add("hidden"); $("enhModal").classList.add("hidden"); } });

// Boot ------------------------------------------------------------------------------
renderControls();
renderGoals();
renderWizard();
api("/api/restrictions").then((r) => { state.restrictionOptions = r; renderRestrictions(); });
loadStatus().then(async () => {
  // Rehearsal shortcuts: ?autorun=app | prod | modal
  const auto = new URLSearchParams(location.search).get("autorun");
  const step = Number(new URLSearchParams(location.search).get("step"));
  if (new URLSearchParams(location.search).get("prd")) { for (let i = 0; i < 4; i++) typing.done.add(i); await showPrd(); return; }
  if (step) { for (let i = 0; i < step; i++) typing.done.add(i); state.step = Math.min(step, QUESTIONS.length - 1); renderWizard(); }
  if (!auto) return;
  await buildApp();
  const params = new URLSearchParams(location.search);
  for (const r of (params.get("restrict") || "").split(",").filter(Boolean)) { state.restrictions.push(r); }
  if (params.get("goals")) { state.goals = new Set(params.get("goals").split(",")); renderGoals(); await findRecipe(); }
  if (state.restrictions.length) { renderRestrictions(); await findRecipe(); }
  if (params.get("budget") === "1") document.querySelector('.tile[data-pref="budget_friendly"]').click();
  if (auto === "prod" || auto === "modal") { show("prod"); await recommend(); }
  if (auto === "modal") await openModal();
  if (auto === "prod" && params.get("tab") === "gov") { if (params.get("cptab")) cpState.tab = params.get("cptab"); await selectTab("tabGov"); }
  if (auto === "prod" && params.get("agents")) openAgents();
  if (auto === "prod" && params.get("tools")) openTools();
  if (auto === "prod" && params.get("focus")) params.get("focus").split(",").forEach((x) => state.entFilter.add(x));
  if (auto === "prod" && params.get("enterprise")) { await openEnterprise(); if (params.get("expand")) $("ent" + params.get("expand")).classList.remove("hidden"); }
  if (auto === "prod" && params.get("knowledge")) openKnowledge();
  if (auto === "prod" && params.get("compare")) openCompare(params.get("compare"));
  if (auto === "prod" && params.get("prov")) openProvenance(params.get("prov"));
  if (auto === "prod" && params.get("security")) openSecurity(params.get("security"));
  if (auto === "prod" && params.get("review")) openGuardrails(params.get("review"));
  if (auto === "prod" && params.get("info")) document.querySelector(`[data-info="${params.get("info")}"]`).click();
  if (auto === "prod" && params.get("tab") === "eval") await selectTab("tabEval");
  if (auto === "prod" && params.get("evaltab")) { state.evalTab = params.get("evaltab"); await renderEvalQuality(); }
  if (auto === "prod" && params.get("enhance")) { $("enhModal").classList.remove("hidden"); $("enhanceText").value = params.get("enhance"); $("btnEnhance").click(); }
}).catch((e) => console.error(e));
