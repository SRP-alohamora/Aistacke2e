# Aistacke2e

AiStackE2E: start with what you want to build, get the simplest production-ready AI stack, with the evidence to prove it and the cost visible before you commit.

## Contents

| Path | What it is |
| --- | --- |
| `AiStackE2E-PRD.md` | Product requirements document (latest export; includes the platform capability model, progressive architecture stages and demo-accepted requirements FR-DMO-1..41) |
| `demo-opus.001/` | One-day demo: Builder Mode wizard → PRD → Fusion Fuel app preview → production deployment analysis (architecture, Eval Quality, GRC). See its README. |
| `follow-ups-on-ClaudePRD-Oct8.md` | Open follow-ups and items to verify |
| `Aistacke2e-Claudeopus5.5-PRD.md`, `Aistacke2e-Gemini3.8Flash-PRD.md` | Earlier PRD drafts |
| `demo-gemini-001/`, `demo-mvp-gemini.md`, `gemini-mvp.md` | Gemini-built demo and notes |

## Live demo

https://srp-alohamora.github.io/Aistacke2e/ - runs fully in your browser (the Python backend runs on Pyodide), offline/simulated model only. First load takes about 10-20 s.

## Run the demo locally

```bash
cd demo-opus.001
uv sync
uv run pytest -q
uv run uvicorn aistack_demo.server:app --port 8000   # http://127.0.0.1:8000
```

Without API keys the demo runs an offline fixture model; its results are labelled SIMULATED. Set `ANTHROPIC_API_KEY` (and optionally `OPENAI_API_KEY`) for live runs.
