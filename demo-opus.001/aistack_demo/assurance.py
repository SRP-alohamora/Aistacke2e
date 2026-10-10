"""Per-layer Eval & Quality status and established guardrails, each linked to the code that enforces it."""
from __future__ import annotations

from functools import lru_cache

from .config import DATA, PACKAGE

SOURCE_FILES = {p.name: p for p in [*PACKAGE.glob("*.py"), *DATA.glob("*.yaml")]}  # includes tool_registry.yaml


@lru_cache
def _lines(name: str) -> list[str]:
    return SOURCE_FILES[name].read_text().splitlines()


def src(name: str, marker: str) -> str:
    """Link to the first line containing `marker` in a demo source file."""
    for i, line in enumerate(_lines(name), 1):
        if marker in line:
            return f"source/{name}.html#L{i}"
    return f"source/{name}.html"


def _g(text: str, file: str, marker: str, status: str = "enforced") -> dict:
    """status: enforced (code checks it), prompt (model instruction only), declared (manifest only), review."""
    return {"text": text, "href": src(file, marker), "status": status}


def guardrails_for(layer: dict, answers: dict) -> list[dict]:
    key = layer["key"]
    if layer["state"] == "none":
        return []
    table = {
        "experience": [
            _g("Input contract rejects unknown fields and out-of-range values", "contracts.py", "class RecipeRequest"),
            _g("Free-text note capped at 500 characters", "contracts.py", "note: str = Field"),
            _g("Insulin and medication dosing questions blocked before any model call", "guards.py", "_DOSING = re.compile"),
            _g("Typed errors returned (422) instead of raw exceptions", "server.py", "raise HTTPException(422"),
        ],
        "model": [
            _g("Output must match the draft JSON schema (structured output)", "contracts.py", "DRAFT_SCHEMA"),
            _g("Only ingredients from the allowed list; no carb numbers from the model", "pipeline.py", "Use ONLY ingredient names"),
            _g("Instructed never to give medication or insulin advice (backed by the input guard)", "pipeline.py", "Never give medication", "prompt"),
            _g("Refusals map to CONTENT_BLOCKED and are never shown as a recipe", "models.py", 'resp.stop_reason == "refusal"'),
            _g("Timeout 60 s, at most 2 retries on retryable errors", "models.py", "max_retries=2"),
            _g("Truncated output (max_tokens) treated as invalid, not shown", "models.py", '"max_tokens"'),
        ],
        "nutrition_tool": [
            _g("Carbs are computed by the tool, never by the model (computed_by)", "contracts.py", 'computed_by: Literal["nutrition_tool"]'),
            _g("Portions bounded to 10-600 g when re-balancing carbs", "nutrition.py", "max(10.0, min(600.0"),
            _g("Nutrition goals checked per meal (protein, fat, fiber, sodium)", "goals.py", "def evaluate"),
            _g("Health restrictions enforced as ingredient exclusions", "restrictions.py", "def exclusions_for"),
            _g("Excluded or premium ingredients flagged on the card", "pipeline.py", "violations = ["),
        ],
        "retrieval_store": [
            _g("Corpus text screened for dosing content before indexing", "knowledge.py", "Safety screen (no dosing text)"),
            _g("Only CC / public-domain photos with attribution are kept", "knowledge.py", "Photo licences and attribution"),
            _g("Ingredient names normalised to the nutrition table", "knowledge.py", "Ingredient names normalised"),
            _g("Retrieved text is passed as labelled inspiration, after the request rules", "pipeline.py", "Inspiration from the recipe corpus"),
            _g("Curated, internal corpus (no user-supplied documents)", "pipeline.py", "RECIPE_PATTERNS = ["),
        ],
        "observability": [
            _g("Prompt and response capture off by default", "recommender.py", "prompt capture off by default", "declared"),
            _g("Health data classes tagged on contract fields for log redaction", "contracts.py", '"x-aistack-data-class"', "declared"),
        ],
        "tooling": [
            _g("Tools are invoked by the pipeline, never chosen by the model (no model tool calls)", "pipeline.py", "def run_recipe"),
            _g("Every invocation logged with tool name, parameters and duration", "pipeline.py", "def _timed"),
            _g("Parameter schemas hashed and checked against the registry (drift detection)", "tools.py", "def drift_summary"),
            _g("Registered schema hashes change only by an explicit, reviewed re-register", "tool_registry.yaml", "note:"),
            _g("No tool has write side effects; store links are read-only search pages", "grocery.py", "def walmart_url"),
            _g("External MCP servers would be version-pinned and allow-listed (none connected)", "tools.py", "MCP_SERVERS", "declared"),
        ],
        "agent_registry": [
            _g("Every agent declares role, side effects and data access", "agents.py", '"side_effects"', "declared"),
            _g("Only the Safety guard and Nutrition calculator can block or change a recipe", "pipeline.py", "def run_recipe"),
            _g("No agent has write side effects at runtime", "agents.py", '"side_effects": "none"', "declared"),
        ],
        "identity": [
            _g("Sign-in required when glucose readings are stored (Q4)", "recommender.py", "Required because glucose readings are stored", "declared"),
            _g("Provider keys read from the environment only, never stored in code", "config.py", "def provider_key_present"),
        ],
    }
    out = list(table.get(key, []))
    dep = next((o for o in layer.get("deploymentOptions", []) if o["id"] == layer.get("deployment")), None)
    if dep and key == "model" and not dep["id"].endswith("-api"):
        out.append(_g(f"{dep['label']}: platform data-retention and region terms need review", "recommender.py", '"bedrock"', "review"))
    return out


def quality_for(layer: dict, evidence: dict | None) -> dict:
    key, m = layer["key"], (evidence or {}).get("metrics", {})
    sim = bool(evidence and evidence.get("simulated"))
    ev_link = {"text": "eval dashboard", "href": "#eval-quality"}
    if layer["state"] == "none":
        return {"status": "na", "summary": "-", "details": []}
    if key == "model":
        if not evidence:
            return {"status": "warn", "summary": "No eval run yet", "details": ["Open Compare models → Run eval"], "link": ev_link}
        s = evidence["success"]
        return {"status": "ok" if s["passed"] == s["total"] else "warn", "simulated": sim,
                "summary": f"{s['passed']}/{s['total']} recipes pass all gates",
                "details": [f"schema valid {m['schema_valid']['passed']}/{m['schema_valid']['total']}",
                            f"exclusions respected {m['exclusions_respected']['passed']}/{m['exclusions_respected']['total']}",
                            f"latency p50 {evidence['latency_ms']['p50'] / 1000:.1f} s"], "link": ev_link}
    if key == "nutrition_tool":
        if not evidence:
            return {"status": "ok", "summary": "Unit-tested", "details": ["carb re-balancing and goal checks have unit tests"]}
        c = m["carb_within_5g"]
        return {"status": "ok" if c["passed"] == c["total"] else "warn", "simulated": sim,
                "summary": f"carbs within ±5 g: {c['passed']}/{c['total']}",
                "details": ["gate ≥ 95%", "goal checks unit-tested"], "link": ev_link}
    if key == "experience":
        from .config import eval_cases
        d = m.get("dosing_refused")
        safety = [{"id": c["id"], "text": c["request"].get("note", "")}
                  for c in eval_cases()["cases"] if c.get("kind") == "safety"]
        return {"status": "ok", "simulated": sim and bool(d),
                "summary": f"dosing refused {d['passed']}/{d['total']}" if d else "Contract-validated",
                "details": ["gate 100%", "invalid input returns 422"], "link": ev_link,
                "info": {"kind": "dosing", "passed": d["passed"], "total": d["total"], "cases": safety} if d else None}
    if key == "retrieval_store":
        from .knowledge import run_checks
        c = run_checks()
        ok = sum(x["status"] == "pass" for x in c)
        return {"status": "warn", "summary": f"data checks {ok}/{len(c)} pass",
                "details": ["no retrieval recall eval yet", "nutrition values unverified"],
                "link": {"text": "cleanup checks", "href": src("knowledge.py", "def run_checks")}}
    if key == "observability":
        return {"status": "warn", "summary": "Not tested in demo", "details": ["planned: trace-propagation test"]}
    if key == "tooling":
        from .tools import drift_summary
        d = drift_summary()
        return {"status": "ok" if not d["drifted"] else "warn",
                "summary": f"param schemas match registry: {d['ok']}/{d['total']}" + ("" if not d["drifted"] else " - drift"),
                "details": (["no drift"] if not d["drifted"] else [f"drift: {', '.join(d['drifted'])}"]) + ["invocations logged per run"],
                "link": {"text": "tool registry", "href": src("tool_registry.yaml", "tools:")}}
    if key == "agent_registry":
        return {"status": "ok", "summary": "Inventory unit-tested", "details": ["8 entries; each has role, skills, guardrails"]}
    if key == "identity":
        return {"status": "na", "summary": "Not exercised in demo", "details": ["managed provider; auth tests in P1"]}
    return {"status": "na", "summary": "-", "details": []}


# --- Security checks per layer --------------------------------------------------------------
# status: pass (green check) | warn (orange !) | fail (red cross) | na. Isolation also carries a level.
CHECKS = ["Authentication", "Authorization", "Zero trust", "Continuous evaluation", "Zero-trust isolation"]
_LEVEL_STATUS = {"High": "pass", "Medium": "warn", "Low": "fail"}


def _c(name: str, status: str, finding: str, fix: str = "", href: str | None = None, level: str | None = None) -> dict:
    if level:
        status = _LEVEL_STATUS[level]
    return {"check": name, "status": status, "level": level, "finding": finding, "fix": fix, "href": href}


def _eval_check(evidence: dict | None) -> dict:
    if not evidence:
        return _c("Continuous evaluation", "fail", "No eval evidence for this model", "Run the eval suite; add it to CI")
    if evidence.get("simulated"):
        return _c("Continuous evaluation", "warn", "Evidence is simulated (offline fixture), expires in 30 days",
                  "Run live evals in CI on every manifest change", src("compat.py", "def _stale"))
    return _c("Continuous evaluation", "warn", "Measured on demand; not yet run continuously",
              "Schedule the suite in CI and sample production traffic", src("compat.py", "def _stale"))


def security_for(layer: dict, evidence: dict | None, follow_ups: dict) -> list[dict]:
    key, dep = layer["key"], layer.get("deployment")
    glucose = bool(follow_ups.get("Q4"))
    if layer["state"] == "none":
        return []
    if key == "experience":
        return [
            _c("Authentication", "fail" if glucose else "warn",
               "The generated /recipes endpoint has no sign-in check" + (" - required because glucose readings are stored" if glucose else ""),
               "Verify the Identity provider's JWT on every request", src("generator.py", '@app.post("/recipes")')),
            _c("Authorization", "fail", "No per-user scoping: any caller can request any recipe",
               "Scope requests to the signed-in user; add rate limits per user"),
            _c("Zero trust", "warn", "TLS is terminated by the platform; no service identity or request signing",
               "Use platform service identity (e.g. Cloud Run IAM) between services"),
            _c("Continuous evaluation", "warn", "Input contract and dosing guard are tested; not monitored in production",
               "Alert on guard blocks and 4xx spikes", src("guards.py", "_DOSING = re.compile")),
            _c("Zero-trust isolation", "", "One container per service; database shared with other layers",
               "Separate DB roles per service", level="Low" if dep == "self-hosted" else "Medium"),
        ]
    if key == "model":
        platform = dep and not dep.endswith("-api")
        return [
            _c("Authentication", "pass", "Provider API key read from the environment, never from code",
               "Rotate keys; use a secret manager in production", src("config.py", "def provider_key_present")),
            _c("Authorization", "warn", "One org-wide key; no per-environment or per-tenant key or budget",
               "Separate keys per environment; spend limits"),
            _c("Zero trust", "pass" if platform else "warn",
               "Calls stay inside your cloud account" if platform else "Outbound HTTPS to a vendor API over the public internet",
               "" if platform else "Consider a private endpoint via your cloud provider"),
            _eval_check(evidence),
            _c("Zero-trust isolation", "", "Vendor-hosted multi-tenant inference; data retention depends on your plan",
               "Confirm zero-data-retention terms", level="Medium"),
        ]
    if key == "nutrition_tool":
        return [
            _c("Authentication", "na", "In-process code; no network boundary"),
            _c("Authorization", "na", "In-process code; no network boundary"),
            _c("Zero trust", "pass", "No network calls and no credentials", href=src("nutrition.py", "def meal_nutrients")),
            _c("Continuous evaluation", "pass", "Carb gate and goal checks run in every test run",
               href=src("goals.py", "def evaluate")),
            _c("Zero-trust isolation", "", "Runs inside the app with no external data", level="High"),
        ]
    if key == "retrieval_store":
        return [
            _c("Authentication", "warn", "Database credentials planned via environment; not wired in the demo",
               "Use a dedicated read-only DB role for retrieval"),
            _c("Authorization", "warn", "Shared read-only corpus today; no row-level security",
               "Add RLS before any user data is stored in the same database"),
            _c("Zero trust", "warn", "Managed Postgres reached over the network with a static password",
               "Use private networking or short-lived credentials"),
            _c("Continuous evaluation", "fail", "No retrieval eval (recall) yet", "Add recall@3 on labelled queries"),
            _c("Zero-trust isolation", "", "Same database as Identity",
               "Separate schema and roles", level="High" if dep == "self-hosted" else "Medium"),
        ]
    if key == "tooling":
        from .tools import MCP_SERVERS, drift_summary
        d = drift_summary()
        mcp = dep in ("mcp-self", "managed-tools")
        return [
            _c("Authentication", "warn" if mcp else "na",
               "MCP/managed tools need per-user OAuth - not configured" if mcp else "In-process tools; no network boundary",
               "Per-user tokens via the MCP authorization flow" if mcp else ""),
            _c("Authorization", "pass", "Read-only tools; no write side effects", href=src("tools.py", '"side_effects": "none"')),
            _c("Zero trust", "warn" if mcp or MCP_SERVERS else "pass",
               "External tool servers would be reached over the network" if mcp else "No external tool calls",
               "Allow-list servers; pin versions; treat tool output as untrusted" if mcp else ""),
            _c("Continuous evaluation", "pass" if not d["drifted"] else "fail",
               f"Drift check on every analysis: {d['ok']}/{d['total']} schemas match" if not d["drifted"]
               else f"Parameter drift in {', '.join(d['drifted'])}", "Review the change, then re-register",
               src("tools.py", "def drift_summary")),
            _c("Zero-trust isolation", "", "Tools run in-process with no credentials" if not mcp
               else "Separate tool server process", level="High" if not mcp else "Medium"),
        ]
    if key == "agent_registry":
        return [
            _c("Authentication", "na", "Inventory only; agents are not separately addressable"),
            _c("Authorization", "pass", "No agent has tools or write permissions at runtime",
               href=src("agents.py", '"side_effects": "none"')),
            _c("Zero trust", "pass", "Agents receive no credentials; the pipeline calls them"),
            _c("Continuous evaluation", "warn", "Recipe drafter is evaluated; the requirements drafter is not",
               "Add an eval set for requirements drafts"),
            _c("Zero-trust isolation", "", "Each agent runs as one pipeline step with no shared memory", level="High"),
        ]
    if key == "observability":
        self_hosted = dep in ("langfuse-self", "cloud-trace")
        return [
            _c("Authentication", "warn", "Exporter API keys not configured in the demo", "Store exporter keys in a secret manager"),
            _c("Authorization", "warn", "Who can read traces is not defined", "Restrict trace access to on-call roles"),
            _c("Zero trust", "pass" if self_hosted else "warn",
               "Traces stay in your account" if self_hosted else "Traces go to a third-party SaaS",
               "" if self_hosted else "Self-host Langfuse or keep content capture off"),
            _c("Continuous evaluation", "na", "Not applicable to tracing itself"),
            _c("Zero-trust isolation", "", "Vendor multi-tenant" if not self_hosted else "Runs in your account",
               level="High" if self_hosted else "Medium"),
        ]
    if key == "identity":
        return [
            _c("Authentication", "warn", "Managed provider selected but not integrated in the demo",
               "Integrate sign-in; require MFA for admin roles"),
            _c("Authorization", "warn", "Roles are not defined yet", "Define user and admin roles"),
            _c("Zero trust", "warn", "MFA and session-lifetime policy not configured", "Short sessions; MFA"),
            _c("Continuous evaluation", "na", "Auth tests planned for P1"),
            _c("Zero-trust isolation", "", "Shares the Supabase project with the database",
               level="Medium" if dep == "supabase-auth" else "High"),
        ]
    return []
