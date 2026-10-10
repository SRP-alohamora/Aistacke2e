"""Side-by-side comparison of "Runs on" deployment choices per layer, grouped by
Cost, Capability and Performance (then Operations & risk).

Qualitative and vendor-neutral by design; relative cost tiers ($ / $$ / $$$) are indicative only.
Verify vendor specifics, regions and prices before choosing.
"""
from __future__ import annotations

GROUPS = [
    ("Cost", [("relative_cost", "Relative cost"), ("cost_model", "Cost model")]),
    ("Capability", [("capability", "Capability"), ("best_for", "Best for")]),
    ("Performance", [("performance", "Performance"), ("scaling", "Scaling")]),
    ("Operations & risk", [("operated_by", "Operated by"), ("data", "Where data lives"), ("ops", "Ops effort"),
                           ("lock_in", "Lock-in")]),
]


def _o(relative_cost, cost_model, capability, best_for, performance, scaling, operated_by, data, ops, lock_in):
    return locals()


C = {
    # Experience (API)
    "cloud-run": _o("$ (scales to zero)", "Per request / CPU-second", "Containers, HTTPS, IAM service identity", "Spiky traffic; pairs with Cloud SQL and Cloud Trace",
                    "Cold starts possible when scaled to zero; min instances avoid them", "Autoscale, incl. to zero", "Google (managed)", "Google Cloud, region you choose", "Low", "Low-medium (container)"),
    "fly": _o("$", "Per machine-second", "Containers in many regions, private networking", "Low latency for users in many regions",
              "Low latency close to users", "Autoscale per region", "Fly.io (managed)", "Fly regions you choose", "Low", "Low (container)"),
    "render": _o("$-$$", "Per instance per month", "Managed web service, previews, cron", "Simplest managed web service",
                 "Steady; no scale-to-zero on paid always-on plans", "Autoscale on paid plans", "Render (managed)", "Render regions", "Low", "Low (container)"),
    "self-hosted": _o("$-$$$ (your infra + staff time)", "Your infrastructure cost", "Whatever you build", "Strict control or existing infra",
                      "Depends on your hardware and tuning", "You manage it", "You", "Your servers", "High", "None"),
    # Model (Anthropic) - cost tiers here are about the platform; token prices are in the model comparison
    "claude-api": _o("List price (in catalog)", "Per token; batch 50% off; prompt caching", "Newest Claude features first (e.g. fast mode, fallbacks)", "Earliest access to new Claude models",
                     "Same model; latency measured by the eval runner", "Managed; rate limits per tier", "Anthropic", "Anthropic; US-only inference option at 1.1x", "Low", "Medium (behind the ChatModel port)"),
    "bedrock": _o("Platform pricing (not in catalog)", "Per token, AWS billing", "Claude via AWS; some features arrive later", "AWS-standardised teams; private networking",
                  "Same model family; platform latency not measured here", "Managed; AWS quotas", "Amazon Web Services", "Your AWS account and region", "Low", "Medium"),
    "vertex": _o("Platform pricing (not in catalog)", "Per token, Google Cloud billing", "Claude via Google Cloud; some features differ", "GCP-standardised teams",
                 "Same model family; platform latency not measured here", "Managed; GCP quotas", "Google Cloud", "Your GCP project and region", "Low", "Medium"),
    "foundry": _o("Standard API rates", "Billed via Microsoft Marketplace", "Claude via Microsoft Foundry", "Azure-standardised teams",
                  "Same model family; platform latency not measured here", "Managed", "Microsoft", "Azure", "Low", "Medium"),
    # Model (OpenAI)
    "openai-api": _o("List price (in catalog)", "Per token; batch 50% off", "Newest OpenAI features first", "Direct access to OpenAI models",
                     "Latency measured by the eval runner", "Managed; rate limits per tier", "OpenAI", "OpenAI", "Low", "Medium"),
    "azure-openai": _o("Platform pricing (not in catalog)", "Azure billing", "OpenAI models in Azure", "Azure-standardised teams",
                       "Platform latency not measured here", "Managed; Azure quotas", "Microsoft", "Azure region you choose", "Low", "Medium"),
    # Guardrails (shown as a column; still selectable in the manifest)
    "in-process:guardrails": _o("Free", "None", "Rule-based dosing guard and contract checks", "Known, narrow risks",
                                "Microseconds; no network hop", "Scales with the app", "You (in the app)", "In the app", "Low", "None"),
    "lakera": _o("$$ (vendor plans)", "Per request / plan", "Prompt-injection and content detection models", "Open-ended user text and tool output",
                 "Adds a network hop per check", "Managed", "Lakera (Check Point)", "Vendor cloud", "Low", "Medium"),
    "cisco-ai-defense": _o("$$$ (enterprise contract)", "Enterprise licence", "Runtime guardrails, red-teaming, model scanning", "Enterprises standardising AI security",
                           "Adds a network hop per check", "Managed", "Cisco", "Vendor cloud", "Low", "Medium-high"),
    # Nutrition tool
    "in-process:nutrition_tool": _o("Free", "None", "62 ingredients, approximate values", "Demo",
                                    "Microseconds (in memory)", "Scales with the app", "You (in the app)", "In the app", "Low", "None"),
    "usda-fdc": _o("Free (API key)", "None; terms to review", "Hundreds of thousands of foods, verified values", "Production nutrition values",
                   "Network call per lookup; cache results", "Rate-limited public API", "USDA (public API)", "Public reference data; no user data sent", "Low", "Low"),
    # Knowledge / retrieval
    "supabase": _o("$ (plan per month)", "Plan + usage", "Postgres + pgvector + auth + storage", "One project for DB and auth",
                   "Good for ~8k recipes; dedicated compute on larger plans", "Plan-based", "Supabase (managed)", "Supabase project region", "Low", "Low (Postgres)"),
    "neon": _o("$ (usage-based)", "Usage-based compute + storage", "Serverless Postgres + pgvector, branching", "Spiky or dev/test workloads",
               "Cold start after scale-to-zero", "Serverless, scales to zero", "Neon (managed)", "Neon region", "Low", "Low (Postgres)"),
    "cloud-sql": _o("$$ (always-on instance)", "Per instance-hour", "Managed Postgres + pgvector, HA option", "Pairs with Cloud Run in one cloud",
                    "Steady low latency inside GCP", "Vertical; read replicas", "Google Cloud (managed)", "Your GCP project region", "Low-medium", "Low (Postgres)"),
    "self-hosted:retrieval_store": _o("$-$$$ (infra + staff time)", "Your infrastructure cost", "Full Postgres control", "Data must stay on your servers",
                                      "Depends on your hardware", "You manage it", "You", "Your servers", "High", "None"),
    # Observability
    "langfuse-cloud": _o("$ (usage tiers)", "Per event / usage tiers", "LLM traces, evals, prompt management", "LLM traces and evals, fast setup",
                         "Async export; no request-path latency", "Managed", "Langfuse (ClickHouse)", "Langfuse cloud region", "Low", "Low (OpenTelemetry)"),
    "langfuse-self": _o("$-$$ (infra + staff time)", "Your infrastructure cost", "Same features, self-run", "Traces must stay in your account",
                        "Async export; you size the backend", "You manage it", "You", "Your account", "Medium", "Low (open source, OTel)"),
    "cloud-trace": _o("$ (usage-based)", "Usage-based", "Distributed tracing; fewer LLM-specific views", "Teams already on Google Cloud",
                      "Async export", "Managed", "Google Cloud", "Your GCP project", "Low", "Low-medium"),
    "datadog": _o("$$-$$$", "Per host / usage", "Full APM; LLM observability add-on", "Teams already using Datadog APM",
                  "Async export", "Managed", "Datadog", "Datadog region", "Low", "Medium"),
    # Tooling
    "in-process:tooling": _o("Free", "None", "Typed tools this app owns", "Tools only this app uses",
                             "In-process calls (microseconds to ms)", "Scales with the app", "You (in the app)", "In the app", "Low", "None"),
    "mcp-self": _o("$ (a small service)", "Your infrastructure cost", "Tools shared with other agents and IDEs via MCP", "Tools shared across agents",
                   "Adds a network hop per tool call", "You manage it", "You", "Your servers", "Medium", "Low (open protocol)"),
    "managed-tools": _o("$$ (vendor plans)", "Vendor plans / per action", "Hundreds of SaaS integrations with per-user OAuth", "Many third-party SaaS tools",
                        "Adds a network hop and vendor latency", "Managed", "Composio / Arcade", "Vendor cloud; per-user tokens", "Low", "Medium"),
    # Agent registry
    "manifest": _o("Free", "None", "Inventory with roles, skills, guardrails", "Under ~10 agents, one team",
                   "n/a (read at build time)", "n/a", "You (in git)", "Your repo", "Low", "None"),
    "backstage": _o("$ (infra + staff time)", "Your infrastructure cost", "Org-wide catalog, ownership, docs", "Orgs already running Backstage",
                    "n/a", "n/a", "You (open source)", "Your servers", "Medium", "Low"),
    "registry-service": _o("$$", "Varies", "Discovery, versioning, policy across teams", "~10+ agents across many teams",
                           "Runtime lookups add latency", "Service-dependent", "You or a vendor", "Depends on vendor", "Medium-high", "Medium"),
    # Identity
    "supabase-auth": _o("$ (in Supabase plan)", "Plan-based", "Email, OAuth, magic links, RLS integration", "Same project as the database",
                        "Managed; low latency in-region", "Managed", "Supabase", "Supabase project region", "Low", "Medium"),
    "firebase-auth": _o("$ (usage-based)", "Usage-based", "Email, phone, social sign-in", "Mobile apps; Google sign-in",
                        "Managed", "Managed", "Google", "Google Cloud", "Low", "Medium"),
    "clerk": _o("$$ (per active user)", "Per monthly active user", "Prebuilt sign-in UI, orgs", "Prebuilt sign-in UI",
                "Managed", "Managed", "Clerk", "Clerk cloud", "Low", "Medium"),
    "auth0": _o("$$-$$$ (per active user)", "Per monthly active user", "Enterprise SSO, MFA, rules", "Enterprise SSO path",
                "Managed", "Managed", "Okta", "Okta cloud", "Low", "Medium-high"),
}


def compare(layer_key: str, options: list[dict], selected: str | None) -> dict:
    cols = []
    for o in options:
        vals = C.get(f"{o['id']}:{layer_key}") or C.get(o["id"]) or {}
        cols.append({"id": o["id"], "label": o["label"], "note": o["note"], "selected": o["id"] == selected,
                     "values": {k: vals.get(k, "-") for _, rows in GROUPS for k, _ in rows}})
    return {"groups": [{"name": g, "rows": [{"key": k, "label": lbl} for k, lbl in rows]} for g, rows in GROUPS],
            "options": cols,
            "note": "Qualitative comparison; $ tiers are indicative, not quotes. Model token prices and measured "
                    "latency are in Compare models. Verify vendor specifics and prices before choosing."}
