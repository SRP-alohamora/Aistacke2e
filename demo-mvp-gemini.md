# AiStackE2E: 1-Day Minimum Viable Demo Specification (`demo-mvp-gemini`)
**Document ID:** `SPEC-DEMO-GEMINI-001`  
**Target Release:** `demo-gemini.001`  
**Purpose:** 1-Day Demo Architecture, Market Analysis, and Minimum Feature Set  
**Date:** October 2026  

---

## 1. Market Analysis for a 1-Day Demo

### The Goal of a 1-Day Demo
In a fast-paced market (investors, design partners, enterprise prospects), demoing a 28-week multi-agent backend or 50 static vendor cards fails to resonate. Audiences don't buy vendor catalogs; they buy the resolution of their acute pain points:
1. **"AI is too unpredictable and breaks our APIs."** (Solved by strict Pydantic contracts).
2. **"AI is bankrupting our margins."** (Solved by the $/1,000 tasks FinOps calculator and Gemini/JEV routing).
3. **"We are trapped in LangChain / OpenAI lock-in."** (Solved by component substitution and clean FastAPI export).

### Minimum Feature Set (The "3-Minute WOW" Arc)
To deliver a jaw-dropping demo in 1 day, we strictly avoid building all 16 layers with 50 live API connections. Instead, we select an **opinionated, high-fidelity core slice**:

```
+----------------------------------------------------------------------------------------------------+
|                                    1-DAY DEMO CORE FEATURE SLICE                                   |
+--------------------+---------------------------------------------------+---------------------------+
| Feature Area       | What Works in `demo-gemini.001`                   | What is Deferred          |
+--------------------+---------------------------------------------------+---------------------------+
| 1. Intent Capture  | 3-Question form + 2 instant 1-click presets:       | Free-form chatbot;        |
|                    | - Diabetic Fusion Recipe Generator (Consumer)     | complex multi-turn audio/ |
|                    | - Enterprise Support Ticket Modernization (B2B)   | video inputs.             |
+--------------------+---------------------------------------------------+---------------------------+
| 2. Layered-Cake    | 5 essential layers visualized dynamically:        | All 16 layers; complex    |
|    Canvas          | API -> Decision Router -> Model -> Contract -> DB | Kubernetes topology.      |
+--------------------+---------------------------------------------------+---------------------------+
| 3. Dynamic FinOps  | Real-time USD per 1,000 tasks ($/1kST) calculation| Historical invoice CSV    |
|    Recalculation   | that updates instantly when swapping components!  | billing ingestion.        |
+--------------------+---------------------------------------------------+---------------------------+
| 4. Component Modal | Interactive modal to swap GPT-4o -> Gemini Flash  | 50 vendor cards;          |
|    & Model Swap    | or add TypeSafe JEV System-1 router.              | live credit card billing. |
+--------------------+---------------------------------------------------+---------------------------+
| 5. Contract Viewer | Syntax-highlighted Pydantic v2 schema inspection. | Complex inheritance trees.|
+--------------------+---------------------------------------------------+---------------------------+
| 6. Test Runner     | Interactive simulation running 20 synthetic tests | 10,000-case cloud batch   |
|                    | showing schema pass rates and latency bars.       | cluster execution.        |
+--------------------+---------------------------------------------------+---------------------------+
| 7. Code Export     | 1-click tabbed viewer for generated `main.py`,     | Direct GitHub PR webhook  |
|                    | `contracts.py`, `adapters.py`, and `Dockerfile`.  | push automation.          |
+--------------------+---------------------------------------------------+---------------------------+
```

---

## 2. The 3-Minute Demo Pitch & Live Script

```
[0:00 - 0:30] THE HOOK & INTENT
"Every developer wants to build reliable AI, but today they're duct-taping raw prompts 
and hoping JSON doesn't break. With AiStackE2E, you start with your intent. 
Let's select 'Diabetic Fusion Recipe Engine'. With one click, our engine infers 
glycemic index constraints, low-latency requirements, and safety boundaries."

[0:30 - 1:15] THE LAYERED-CAKE ARCHITECTURE & THE FINOPS SHOCK
"Instantly, AiStackE2E generates the simplest viable architecture. 
Look at the baseline with GPT-4: it costs $25.00 per 1,000 recipes.
Let's click on the Model Layer: we swap GPT-4 for Google Gemini 1.5 Flash.
Next, we enable TypeSafe AI JEV for dietary triage ($0.042/M tokens).
Watch the economics: our cost plunges from $25.00 down to $0.77 per 1,000 recipes—a 96.9% savings!"

[1:15 - 2:00] STRICT PYDANTIC CONTRACTS
"How do we know it won't hallucinate sugar into a diabetic meal?
Look at the Contract Rail. AiStackE2E compiled strict Pydantic v2 schemas:
glycemic_index_estimate <= 55, net_carbs, and clinical safety verification."

[2:00 - 2:40] LIVE SYNTHETIC REGRESSION TEST
"Let's click 'Run Synthetic Verification'. AiStackE2E evaluates 20 boundary cases
against Gemini Flash. Notice: 100% schema pass rate, average latency 340ms, zero crashes."

[2:40 - 3:00] ZERO LOCK-IN CODE EXPORT
"Finally, we click 'Export Scaffolding'. We don't lock you into a proprietary SDK. 
Here is clean, production-grade FastAPI, Pydantic, and Docker code ready to deploy today."
```

---

## 3. Implementation Details: `demo-gemini.001`

The implementation is packaged inside `demo-gemini-001/`:
1. `index.html`: A modern, dark-mode, reactive single-page application with glassmorphism UI, interactive canvas, real-time math, and tabbed code viewer.
2. `app.py`: An optional lightweight FastAPI server providing backend REST endpoints (`/api/synthesize`, `/api/simulate-swap`, `/api/export`).
3. `README.md`: 10-second setup guide.
