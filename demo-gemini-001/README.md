# AiStackE2E Interactive Demo (`demo-gemini.001`)

This is the standalone, working implementation of the **AiStackE2E 1-Day Minimum Viable Demo**.

---

## Quickstart Guide

### Option 1: Direct In-Browser Inspection (Instant)
Simply open `demo-gemini-001/index.html` in any modern web browser (Chrome, Safari, Edge, Firefox):
```bash
open demo-gemini-001/index.html
```

### Option 2: Run via Local Python Server
To run the interactive web studio:
```bash
cd demo-gemini-001
python3 -m http.server 8080
```
Then navigate to: **`http://localhost:8080`**

### Option 3: Run with the FastAPI Backend Service
If you have FastAPI and Uvicorn installed:
```bash
cd demo-gemini-001
python3 app.py
```
Then access:
- **Interactive UI:** `http://localhost:8080/`
- **Interactive Swagger Docs:** `http://localhost:8080/docs`

---

## Key Features Demonstrated in `demo-gemini.001`
1. **Guided 3-Question Intent Discovery:** With 1-click presets for *Diabetic Fusion Recipes* and *Enterprise Support Triage*.
2. **Layered-Cake Architecture Visualizer:** 5 core horizontal layers with live component pills and status badges.
3. **Interactive FinOps Recalculation:** Click to swap GPT-4o with Google Gemini 1.5 Flash and TypeSafe JEV; watch the estimated cost plummet from **$25.00/1kST to $0.77/1kST** (96.9% savings).
4. **Canonical Pydantic v2 Contract Explorer:** View compiled schema with strict type and boundary validations.
5. **Interactive Synthetic Test Runner:** Run 20 simulated boundary test cases with animated progress and latency indicators.
6. **Zero-Lock-in Scaffolding Viewer:** Inspect and copy standalone, production-ready FastAPI backend code.
