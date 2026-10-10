# demo-opus.001 - AiStackE2E one-day demo

Builder Mode slice for the **Fusion Fuel** example: a quick fusion-recipe app for a physically active person
managing diabetes. Spec: the *demo-mvp-opus* doc; product context: `../AiStackE2E-PRD.md`.

## Run

```bash
cd demo-opus.001
uv sync
uv run pytest -q                                   # 11 tests, offline
uv run python -m aistack_demo.evals --offline      # writes SIMULATED evidence for all 3 models
uv run uvicorn aistack_demo.server:app --port 8000 # open http://127.0.0.1:8000
```

Flow: three one-at-a-time questions → the generated **Fusion Fuel** app preview (recipe illustration + recipe card,
left panel with Organic / Budget-friendly tiles and an "ingredients available" box) → **Analyze in prod deployment**
(Q4/Q5 on top, then each layer with its component, where it runs, cost and rationale; Compare models opens the swap view).

Rehearsal shortcuts: `?autorun=app`, `?autorun=prod`, `?autorun=modal`.

### Live mode

Set `ANTHROPIC_API_KEY` (Sonnet 5.5, Haiku 5.5) and/or `OPENAI_API_KEY` (GPT-6.1 Sol), then re-run evals without
`--offline` or press **Run eval** in the Model modal. Models without a key stay in offline mode; the header shows
each model's mode. `AISTACK_DEMO_OFFLINE=1` forces offline for everything (stage fallback).

Delete `evidence/*.json` before a live demo so no simulated evidence is mixed in. The verdict engine refuses to
compare simulated with measured evidence (`unverified`).

## What is real vs simulated vs mocked

| Area | Status |
| --- | --- |
| Three questions → profile → follow-ups that change decisions | Real (rule-based, deterministic) |
| Recommender → manifest (`aistack.yaml`), rationale for every layer, None states | Real (RAG template only) |
| Cost per attempt / per successful task / monthly, ranges | Real math; list prices verified 2026-10-08 (`data/prices.yaml`) |
| Eval harness (10 cases, deterministic gates) and verdict rules | Real; demo-grade (PRD needs ≥ 25 cases) |
| Model calls | Live with keys (Anthropic SDK; OpenAI adapter **untested against the live API**); otherwise the offline fixture |
| Offline fixture behaviour per model | **SIMULATED** - illustrative error rates in `data/simulation.yaml`, not measured |
| Generated app zip (contracts, tool, guard, adapters, FastAPI, tests) | Real; its tests pass offline |
| Nutrition table (carbs, protein, fat, sodium, fiber) | Approximate demo values; % Daily Value uses FDA reference amounts - replace with a verified source before real use |
| Retrieval | Keyword stand-in for pgvector |
| Architect Mode | **MOCK** - static JSON for a fictional repo |
| Recipe photo | Real photo of a **similar** dish from 11 CC-licensed / public-domain Wikimedia Commons images (`static/photos/`, attribution shown); not generated for the exact recipe |
| Whole Foods / Walmart costs | **Sample prices** (USD/kg in `aistack_demo/grocery.py`), not live quotes; links open each store's search page |
| Health conditions / restrictions | Real, simplified rule mappings to ingredient exclusions (`restrictions.py`) |

## GitHub Pages build

`pages/build_pages.py` builds a static site; `pages/pyodide-bridge.js` loads Pyodide, installs FastAPI and routes every
`fetch("/api/...")` to the same `aistack_demo.server` app running in the browser. Offline fixture mode only (no keys in the
browser). Deployed by `.github/workflows/pages.yml` on push to `main`.

```bash
python pages/build_pages.py --out _site && python -m http.server -d _site 8090
```

## Layout

```
aistack_demo/   contracts, nutrition, guards, models, pipeline   (copied into the generated app)
                profile, recommender, cost, evals, compat, generator, server, config (demo platform)
data/           prices.yaml, simulation.yaml, eval_cases.yaml, architect_mock.json
static/         index.html, app.js, style.css (single page; Mermaid from jsDelivr)
evidence/       eval evidence JSON (generated)
tests/          test_demo.py
```

Not medical advice. The generated app blocks insulin and medication dosing questions and never lets the model
state carbohydrate numbers.
