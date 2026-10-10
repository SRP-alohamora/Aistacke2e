# AiStackE2E — 1-Page MVP Specification (`gemini-mvp`)
**Author:** Founding Engineering & Product Leadership Team  
**Architecture Base:** Gemini 3.8 / Google GenAI Native Ecosystem  
**Document Type:** 1-Page Product & Engineering MVP Blueprint  
**Status:** Approved for Implementation · Target Sprint: P0 (Weeks 1–12)  

---

## 1. Product Thesis & Core Promise

> **"Start with what you want to build. AiStackE2E recommends the simplest viable architecture, explains every decision, enforces reliable contracts, and lets you replace components as your requirements evolve."**

AiStackE2E is a **software-only SaaS and developer toolkit** that solves the AI reliability and cost crisis. It replaces ad-hoc prompt chaining and unvalidated JSON dictionaries with **declarative, versioned Architecture Manifests** and **strict Pydantic v2 contracts**.

```
+----------------------------------------------------------------------------------------------------+
|                                    DUAL-LIFECYCLE ENGINE                                           |
|                                                                                                    |
|  [BUILDER MODE]   3 Intent Questions  --> Layered-Cake Stack --> Scaffolding --> Contract QA      |
|  [ARCHITECT MODE] Legacy Repo AST Scan --> Inferred Manifest --> Cost/Gap Audit --> Safe Migration|
+----------------------------------------------------------------------------------------------------+
```

---

## 2. The P0 MVP Scope: What Ships in 12 Weeks

The MVP delivers a defensible, end-to-end slice proving that typed architecture contracts eliminate hallucinations, lower inference costs, and enable safe component swaps.

| System Component | MVP Implementation (P0) | What It Explicitly Excludes (Non-Goals) |
|:---|:---|:---|
| **Discovery Engine** | **3-Question Intent Prompt:** What to build? Who uses it? What must it achieve? Classifies into 1 of 3 templates. | Open-ended chat; arbitrary prompt playgrounds; multi-turn brainstorming. |
| **Supported Templates** | **1. Structured Output** (FastAPI + Pydantic + LLM + Postgres).<br>**2. RAG Application** (FastAPI + Hybrid BM25/Pgvector).<br>**3. Tool-Using Workflow** (FastAPI + State Machine + Tools). | Multi-agent autonomous swarms (CrewAI/AutoGen); unconstrained looping agents. |
| **Model & Routing Layer** | **Default Models:** Google Gemini 1.5 Flash (high-speed, $0.075/M in, $0.30/M out) & Gemini 1.5 Pro (complex reasoning).<br>**Normalized Adapters:** Anthropic & OpenAI.<br>**System-1 Router:** TypeSafe AI JEV ($0.042/M tokens, free output) for deterministic classification & triage. | Self-hosted GPU infrastructure (vLLM/SGLang); fine-tuning pipelines; custom LoRAs. |
| **Contract System** | **Pydantic v2 + JSON Schema 2020-12.** Strict input/output validation, field constraints, and error normalization. | Protobuf/gRPC; dynamic unvalidated dicts; unstructured strings. |
| **FinOps Engine** | **USD per 1,000 Successful Tasks ($/1kST).** Real-time calculation factoring in token rates, prompt caching, and retries. | Blended cost per token; opaque cloud hosting estimates; unverified point figures. |
| **Code Factory** | **Standalone Python 3.12 / FastAPI Scaffolding.** Exports clean repo with Pydantic models, Dockerfile, tests, and CI/CD. | Proprietary hosted runtime; vendor lock-in SDKs; AiStack in the production request path. |
| **Brownfield Scanner** | **CLI Tool (`aistack scan .`).** Ingests local Python AST, extracts LLM calls/prompts, outputs Inferred Manifest & 1-page gap audit. | Cloud execution of customer source code; live database credential access. |
| **Model Swap QA** | **1 Verified Swap Workflow:** Automated regression suite running 20 synthetic boundary cases to prove equivalence. | Arbitrary untested provider claims; 100% universal compatibility guarantees. |

---

## 3. High-Level Platform Architecture

AiStackE2E is engineered as a **Python Modular Monolith** with an asynchronous worker pool, eliminating distributed systems tax during early development.

```
+----------------------------------------------------------------------------------------------------+
|                                    AiStackE2E PLATFORM TOPOLOGY                                    |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|    +-----------------------------+               +----------------------------------+              |
|    |   WEB STUDIO (React 19)     |               |     AiStack CLI (Python / uv)    |              |
|    |   Layered-Cake Canvas & UX  |               |  `aistack scan` / `aistack init` |              |
|    +--------------+--------------+               +-----------------+----------------+              |
|                   |                                                |                               |
|                   +-----------------------+------------------------+                               |
|                                           v                                                        |
|                         +-----------------------------------+                                      |
|                         |    FastAPI MODULAR MONOLITH API   |                                      |
|                         +-----------------+-----------------+                                      |
|                                           |                                                        |
|        +----------------------------------+----------------------------------+                     |
|        |                                  |                                  |                     |
|        v                                  v                                  v                     |
|  +--------------------+         +--------------------+             +--------------------+          |
|  | Manifest & Contract|         | Component Catalog  |             |  Background Worker |          |
|  | Registry (Postgres)|         | & Capability Store |             |  Pool (ARQ/Redis)  |          |
|  +--------------------+         +--------------------+             +---------+----------+          |
|                                                                              |                     |
|                                         +------------------------------------+                     |
|                                         v                                                          |
|                       +-----------------------------------+                                        |
|                       |  Synthetic Eval & AST Scan Runner |                                        |
|                       |  (Isolated, Read-Only Sandboxes)  |                                        |
|                       +-----------------------------------+                                        |
+----------------------------------------------------------------------------------------------------+
```

---

## 4. Canonical Model Stack & Economics

AiStackE2E leverages **Google Gemini 1.5 Flash + Pro** and **TypeSafe AI JEV** to deliver industry-leading unit economics.

```
+----------------------------------------------------------------------------------------------------+
|                                    NORMALIZED COST BREAKDOWN ($/1kST)                              |
+-------------------------------------+-----------------------+---------------------+----------------+
| Architectural Tier                  | Component Chosen      | Pricing / Metric    | Cost / 1k Tasks|
+-------------------------------------+-----------------------+---------------------+----------------+
| Tier 1: System-1 Decision / Triage  | TypeSafe AI JEV       | $0.042/M in, $0 out | $0.03          |
| Tier 2: Primary Generation Engine   | Gemini 1.5 Flash      | $0.075/M in, $0.30 out| $0.38        |
| Tier 3: Complex Reasoning Fallback  | Gemini 1.5 Pro        | $1.25/M in, $5.00 out | $2.40 (10% use)|
| Tier 4: Knowledge / Retrieval Index | PostgreSQL (pgvector) | Relational instance | $0.12          |
| Tier 5: Operational & Eval Overhead | Pydantic + Otel Spans | In-process execution| $0.00          |
+-------------------------------------+-----------------------+---------------------+----------------+
| TOTAL NORMALIZED BASELINE           |                       |                     | $0.77 / 1kST   |
+-------------------------------------+-----------------------+---------------------+----------------+
```
*(Savings: Switching from an un-routed GPT-4 baseline at $25.00/1kST to AiStackE2E's Gemini/JEV stack yields a **96.9% cost reduction**).*

---

## 5. First 6 Sprint Implementation Milestones (12 Weeks)

| Sprint | Weeks | Primary Focus | Concrete Engineering Deliverable |
|:---:|:---:|:---|:---|
| **S1** | W1–W2 | **Manifest & Contract Core** | JSON Schema Draft 2020-12 spec; Pydantic v2 canonical models and validators. |
| **S2** | W3–W4 | **Model Adapters & Routing** | Google GenAI SDK adapter (Gemini Flash/Pro); TypeSafe JEV decision router; OpenAI/Anthropic fallback. |
| **S3** | W5–W6 | **Intent & Template Engine** | 3-Question discovery parser; 3 Reference Templates (Structured, RAG, Workflow). |
| **S4** | W7–W8 | **Code Scaffolding Factory** | Jinja2 templates generating runnable FastAPI, Pydantic, Dockerfile, and GitHub Actions CI. |
| **S5** | W9–W10| **Regression Harness & FinOps**| 20-case synthetic test generator; model swap compatibility scoring; $/1kST calculator. |
| **S6** | W11–W12| **Brownfield CLI & Launch** | `aistack scan` AST parser; markdown gap & cost leak report; end-to-end dogfooding & Alpha release. |

---

## 6. Success Criteria & Target KPIs

- **Developer Activation Rate:** $\ge 35\%$ of unique visitors complete the 3 questions and export working code within 10 minutes.
- **Contract Reliability SLA:** $\ge 99.5\%$ schema conformance across all synthetic test runs on scaffolded applications.
- **CLI Performance:** `aistack scan .` analyzes a 100,000 LOC Python repository in $< 15$ seconds on local CPU.
- **Modernization Impact:** Identify $\ge \$1,000,000$ in annualized enterprise inference waste during private alpha audits.
