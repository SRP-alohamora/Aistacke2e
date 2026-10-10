"""Rule-based recommender for the RAG template -> Architecture Manifest (aistack.yaml)."""
from __future__ import annotations

from datetime import datetime, timezone

import yaml

from .agents import inventory as _agents
from .config import prices


def _plan() -> set[str]:
    from .enterprise import PLAN
    return PLAN

REQUIREMENTS = [
    {"id": "R1", "text": "Suggest quick (<=30 min) fusion recipes"},
    {"id": "R2", "text": "Respect carbohydrate targets per meal for a person with diabetes"},
    {"id": "R3", "text": "Account for activity level (pre/post workout)"},
    {"id": "R4", "text": "Ground nutrition facts in a trusted database, not model memory"},
    {"id": "R5", "text": "Do not give insulin or medication dosing advice", "kind": "safety"},
]


# Where each layer runs in production. Notes are qualitative; no platform prices are claimed.
DEPLOYMENTS = {
    "experience": [
        {"id": "cloud-run", "label": "Google Cloud Run", "note": "Serverless containers; scales to zero"},
        {"id": "fly", "label": "Fly.io", "note": "Containers close to users"},
        {"id": "render", "label": "Render", "note": "Managed web service"},
        {"id": "self-hosted", "label": "Self-hosted (Docker on a VM)", "note": "You run patching and scaling"},
    ],
    "guardrails": [
        {"id": "in-process", "label": "In-process rules", "note": "Runs inside the app; no extra service"},
        {"id": "lakera", "label": "Lakera Guard API", "note": "Managed; extra network hop and vendor review"},
        {"id": "cisco-ai-defense", "label": "Cisco AI Defense", "note": "Managed; enterprise contract"},
    ],
    "model:anthropic": [
        {"id": "claude-api", "label": "Claude API (direct)", "note": "List prices in the catalog apply"},
        {"id": "bedrock", "label": "Amazon Bedrock", "note": "Partner-operated; separate pricing, not in catalog"},
        {"id": "vertex", "label": "Google Vertex AI", "note": "Partner-operated; separate pricing, not in catalog"},
        {"id": "foundry", "label": "Microsoft Foundry", "note": "Billed via Microsoft Marketplace"},
    ],
    "model:openai": [
        {"id": "openai-api", "label": "OpenAI API (direct)", "note": "List prices in the catalog apply"},
        {"id": "azure-openai", "label": "Azure OpenAI (Microsoft Foundry)", "note": "Separate pricing, not in catalog"},
    ],
    "nutrition_tool": [
        {"id": "in-process", "label": "In-process table (demo)", "note": "Approximate values; demo only"},
        {"id": "usda-fdc", "label": "USDA FoodData Central API", "note": "Verified source; terms not yet reviewed"},
    ],
    "retrieval_store": [
        {"id": "supabase", "label": "Supabase Postgres + pgvector", "note": "Managed; shares DB with identity"},
        {"id": "neon", "label": "Neon Postgres + pgvector", "note": "Serverless Postgres"},
        {"id": "cloud-sql", "label": "Cloud SQL for PostgreSQL", "note": "Pairs with Cloud Run"},
        {"id": "self-hosted", "label": "Self-hosted Postgres", "note": "You run backups and upgrades"},
    ],
    "observability": [
        {"id": "langfuse-cloud", "label": "OTel -> Langfuse Cloud", "note": "Managed LLM tracing"},
        {"id": "langfuse-self", "label": "OTel -> Langfuse self-hosted", "note": "Data stays in your account"},
        {"id": "cloud-trace", "label": "OTel -> Google Cloud Trace", "note": "Pairs with Cloud Run"},
        {"id": "datadog", "label": "OTel -> Datadog", "note": "If already your APM"},
    ],
    "tooling": [
        {"id": "in-process", "label": "Typed in-process adapters", "note": "Tools run inside the app; no network hop"},
        {"id": "mcp-self", "label": "MCP server (self-hosted)", "note": "For tools shared with other agents or IDEs"},
        {"id": "managed-tools", "label": "Managed tool platform (Composio / Arcade)", "note": "Per-user OAuth for SaaS tools"},
    ],
    "agent_registry": [
        {"id": "manifest", "label": "Inventory in aistack.yaml", "note": "Versioned with the code; no extra service"},
        {"id": "backstage", "label": "Backstage software catalog", "note": "If the org already runs Backstage"},
        {"id": "registry-service", "label": "Dedicated agent registry service", "note": "Worth it at ~10+ agents or many teams"},
    ],
    "identity": [
        {"id": "supabase-auth", "label": "Supabase Auth", "note": "Same project as the database"},
        {"id": "firebase-auth", "label": "Firebase Auth", "note": "Google-managed"},
        {"id": "clerk", "label": "Clerk", "note": "Hosted UI components"},
        {"id": "auth0", "label": "Auth0 (Okta)", "note": "Enterprise SSO path"},
    ],
}


def _deployment_options(layer: dict) -> list[dict]:
    if layer["state"] == "none":
        return []
    if layer["key"] == "model":
        provider = layer["component"].split("/")[0]
        return DEPLOYMENTS[f"model:{provider}"]
    return DEPLOYMENTS.get(layer["key"], [])


def _layer(key, friendly, analogy, purpose, state, component, rationale, *, driven_by=(),
           alternatives=(), limits=(), rails=None, cost_key=None, clickable=False, config=None):
    return {
        "key": key, "friendly": friendly, "analogy": analogy, "purpose": purpose,
        "state": state, "component": component, "drivenBy": list(driven_by),
        "rationale": rationale, "alternatives": list(alternatives), "limits": list(limits),
        "rails": rails or {"contracts": "ok", "economics": "ok", "observability": "ok", "security": "ok"},
        "costKey": cost_key, "clickable": clickable, "config": config or {},
    }


def recommend(profile: dict, answers: dict | None = None, model_key: str | None = None,
              deployments: dict | None = None) -> dict:
    answers = answers or {}
    deployments = deployments or {}
    stores_glucose = bool(answers.get("Q4", False))
    verified_db = answers.get("Q5", True)
    p = prices()
    model_key = model_key or p["baseline"]
    model = p["models"][model_key]
    alt_models = [k for k in p["models"] if k != model_key]

    layers = [
        _layer("experience", "Experience", "the plate", "How users send requests and get recipe cards",
               "selected", "fastapi+sse", "One HTTP endpoint with server-sent events is enough for a single-screen app.",
               driven_by=["R1"], alternatives=["AG-UI (CopilotKit)", "Vercel AI SDK stream"]),
        _layer("guardrails", "Guardrails", "food-safety inspector", "Block unsafe requests and validate output",
               "selected", "builtin/rules", "Rule-based guard blocks dosing questions before any model call (gate: 100% refusal).",
               driven_by=["R5"], alternatives=["Lakera (Check Point)", "Cisco AI Defense", "LLM-Guard (OSS)"],
               limits=[{"level": "info", "text": "Rules catch known phrasings only; vendor guards add recall at extra cost."}]),
        _layer("model", "Model", "the chef", "Drafts the recipe as structured JSON",
               "selected", f"{model['provider']}/{model['model_id']}",
               "Mid-tier model balances recipe quality with reliable structured output." if model_key == "sonnet-5-5"
               else f"User-selected {model['label']}; see compatibility evidence.",
               driven_by=["R1", "R2"], alternatives=[p["models"][k]["label"] for k in alt_models],
               cost_key="model", clickable=True, config={"modelKey": model_key, "effort": "low", "timeoutMs": 30000}),
        _layer("nutrition_tool", "Nutrition tool", "kitchen scale", "Computes and adjusts carbohydrate grams deterministically",
               "selected", "custom/carb-table (demo); USDA FoodData Central (production)",
               "Carb numbers come from a table, never from the model." if verified_db
               else "You chose no verified database; safety policy R4 keeps the deterministic tool on.",
               driven_by=["R2", "R4"],
               limits=[] if verified_db else [{"level": "warn", "text": "Overridden by policy: model-estimated carbs are unsafe for this user."}],
               rails={"contracts": "ok", "economics": "ok", "observability": "ok", "security": "ok"}),
        _layer("retrieval_store", "Knowledge", "the pantry",
               "Domain knowledge (recipe corpus, nutrition reference, prices, photos): ingestion, cleanup, indexing",
               "selected", "postgres/pgvector (keyword stand-in in demo)",
               "Domain: fusion recipes for an active person with diabetes. Data is cleaned (names normalised to the "
               "nutrition table, units in grams, dosing text and unlicensed photos rejected) before indexing. "
               "About 8k recipes fit in one Postgres; no separate vector DB to run.",
               driven_by=["R4"], alternatives=["Qdrant", "Pinecone", "Chroma"],
               limits=[{"level": "info", "text": "Demo uses keyword matching in place of pgvector embeddings."}]),
        _layer("tooling", "Tooling", "the kitchen tools", "Tool invocation, tool parameters and drift, external tools via MCP and adapters",
               "selected", "typed in-process adapters (8 tools) · MCP: none connected",
               "The pipeline calls 8 typed tools directly; the model never chooses tools. Parameter schemas are hashed "
               "and checked for drift. MCP is added only for third-party tools (grocery cart, CGM) in P1.",
               driven_by=["R2", "R4"], alternatives=["MCP server", "Composio", "Arcade"]),
        _layer("memory", "Memory", None, "Long-term conversational memory",
               "none", None, "Preferences fit in a user-profile row; no long-term conversational memory needed.",
               alternatives=["Mem0", "Zep (Graphiti)", "Letta"]),
        _layer("orchestration", "Orchestration", None, "Multi-step agent loop or workflow engine",
               "none", None, "Single retrieve-generate-validate pass with one deterministic adjustment; no agent loop.",
               alternatives=["LangGraph", "PydanticAI agent", "Temporal"]),
        _layer("agent_registry", "Agent registry", "the kitchen roster", "Inventory of agents and tools: roles, skills, capabilities",
               "selected", "manifest/agents (8 entries, 2 LLM-backed)",
               "Two LLM agents and six deterministic tools: an inventory in the manifest is enough. "
               "No supervisor or multi-agent orchestration; revisit a registry service at ~10 agents.",
               driven_by=["R2", "R5"], alternatives=["Backstage catalog", "Registry service"]),
        _layer("gateway", "Gateway", None, "One API across providers, budgets, fallbacks",
               "none", None, "Two providers via typed adapters; revisit at more than 3 providers or org budgets.",
               alternatives=["LiteLLM", "Portkey", "OpenRouter"]),
        _layer("observability", "Observability", "tasting notes", "Traces, tokens, latency",
               "selected", "opentelemetry/sdk", "OTel spans with GenAI attributes; prompt capture off by default.",
               driven_by=["R2"], alternatives=["Langfuse", "LangSmith", "Arize Phoenix"]),
        _layer("identity", "Identity", "front door", "User sign-in",
               "managed", "supabase/auth" if stores_glucose else "supabase/auth (optional)",
               "Required because glucose readings are stored." if stores_glucose
               else "Managed auth so profiles persist; no health readings stored.",
               driven_by=["R2"], alternatives=["Clerk", "Auth0", "Okta"],
               rails={"contracts": "ok", "economics": "ok", "observability": "ok",
                      "security": "warn" if stores_glucose else "ok"},
               limits=[{"level": "warn", "text": "Storing glucose readings makes this health data: review retention and region."}]
               if stores_glucose else []),
    ]

    # Nutrition tool is a sub-layer of Tooling: place it directly under its parent.
    nt = next(l for l in layers if l["key"] == "nutrition_tool")
    layers.remove(nt)
    nt["parent"] = "tooling"
    layers.insert(next(i for i, l in enumerate(layers) if l["key"] == "tooling") + 1, nt)
    for l in layers:
        opts = _deployment_options(l)
        chosen = deployments.get(l["key"])
        l["deploymentOptions"] = opts
        l["deployment"] = chosen if chosen in {o["id"] for o in opts} else (opts[0]["id"] if opts else None)
        if l["key"] == "model" and l["deployment"] and not l["deployment"].endswith("-api"):
            l["limits"] = l["limits"] + [{"level": "warn", "text": "Platform pricing differs from direct list prices; cost shown is for the direct API."}]

    manifest = {
        "schemaVersion": "1.0",
        "metadata": {"name": "fusion-fuel", "template": "rag@1.2.0", "revision": 1,
                     "generatedBy": "demo-opus.001",
                     "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "requirements": REQUIREMENTS,
        "layers": {
            l["key"]: {k: v for k, v in {
                "state": l["state"], "component": l["component"], "deployment": l["deployment"],
                "drivenBy": l["drivenBy"] or None,
                "config": l["config"] or None, "rationale": l["rationale"],
            }.items() if v is not None}
            for l in layers
        },
        "agents": [{k: a[k] for k in ("id", "kind", "scope", "role", "side_effects")} for a in _agents(model_key)],
        "contracts": [
            {"port": "app->model", "contract": "aistack/RecipeRequest@1.4.0", "response": "aistack/RecipeCard@2.3.0"},
            {"port": "app->nutrition_tool", "contract": "aistack/NutritionLookup@1.0.0"},
        ],
        "policies": {
            "dataClasses": {"user_profile": "confidential",
                            "glucose_readings": "health" if stores_glucose else "not_collected"},
            "allowedProviders": ["anthropic", "openai"], "regions": ["us"],
        },
        "enterprise": {"plan": sorted(_plan())},
        "evaluation": {"suites": ["fusion-fuel-demo@1"],
                       "gates": [{"metric": "schema_valid", "min": 0.9},
                                 {"metric": "carb_within_5g", "min": 0.95},
                                 {"metric": "exclusions_respected", "min": 0.9},
                                 {"metric": "dosing_refused", "min": 1.0}]},
        "economics": {"scenarios": [{"name": k, "tasksPerMonth": v} for k, v in p["scenarios"].items()]},
        "provenance": {
            "layers.model": {"source": "user" if model_key != p["baseline"] else "inferred"},
            "layers.memory": {"source": "inferred", "confidence": "high"},
            "policies.dataClasses.glucose_readings": {"source": "user" if "Q4" in answers else "default"},
        },
    }
    return {"manifest": manifest, "layers": layers,
            "yaml": yaml.safe_dump(manifest, sort_keys=False, width=100)}
