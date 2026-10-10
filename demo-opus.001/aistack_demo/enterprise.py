"""Enterprise readiness review: scoreboard of the PRD section 21 capabilities (+ cost controls).

Status: green (in place) · mustard (mostly there, minor gaps) · orange (partial, real gaps) · red (missing).
Scores reflect what this build does today. "Enabling" a recommendation adds it to the enablement plan
(manifest `enterprise.plan`); it does not implement it, so scores change only when the build changes.
"""
from __future__ import annotations

from .assurance import src

PLAN: set[str] = set()
STATUS_POINTS = {"green": 3, "mustard": 2, "orange": 1, "red": 0}


def _r(rid, text, effort, cost, phase="P0-GA"):
    return {"id": rid, "text": text, "effort": effort, "cost": cost, "phase": phase}


def _item(key, name, pillars, status, current, gap, recs, href=None):
    return {"key": key, "name": name, "pillars": pillars, "status": status, "current": current, "gap": gap,
            "recommendations": recs, "href": href}


def report(evidence: dict | None, follow_ups: dict, deployments: dict, audit_events: int) -> dict:
    glucose = bool(follow_ups.get("Q4"))
    ev_status = "orange" if not evidence else ("mustard" if evidence.get("simulated") else "green")
    self_obs = deployments.get("observability") in ("langfuse-self", "cloud-trace")
    items = [
        _item("typed_boundaries", "Typed boundaries", ["Quality", "Security"], "green",
              "Pydantic contracts on every boundary; model output validated against a JSON schema; contract versions tracked",
              "None blocking", [
                  _r("tb-1", "Add contract-compatibility check to CI (block breaking changes)", "S", "none"),
                  _r("tb-2", "Publish OpenAPI 3.1 for the /recipes API", "S", "none")],
              src("contracts.py", "class RecipeRequest")),
        _item("secrets", "Secret hygiene", ["Security"], "mustard",
              "Provider keys read from environment only; never in code or logs",
              "No secret manager, rotation or per-environment keys", [
                  _r("sh-1", "Move keys to a cloud secret manager", "S", "$ (cents per secret per month)"),
                  _r("sh-2", "Separate keys per environment with spend limits", "S", "none"),
                  _r("sh-3", "Secret scanning in CI (e.g. gitleaks)", "S", "none")],
              src("config.py", "def provider_key_present")),
        _item("identity_access", "Identity and access", ["Security", "Governance"], "red",
              "Managed identity provider selected but not wired; the /recipes endpoint is open",
              "No sign-in check or per-user authorization" + (" - required because glucose data is stored" if glucose else ""), [
                  _r("ia-1", "Verify the identity provider's JWT on every request", "M", "included in identity plan"),
                  _r("ia-2", "Scope data and rate limits to the signed-in user", "M", "none"),
                  _r("ia-3", "Admin roles with MFA; SSO/SCIM for enterprise tenants", "M", "$$ (SSO tier)", "P1")],
              src("generator.py", '@app.post("/recipes")')),
        _item("error_handling", "Error handling", ["Quality", "Resiliency", "High availability"], "mustard",
              "Typed error taxonomy (rate limited, unavailable, blocked, invalid); 422 on bad input; refusals never shown as recipes",
              "No error budgets or alerting", [
                  _r("eh-1", "Error-rate SLO with alerting on the /recipes endpoint", "S", "$ (alerting)"),
                  _r("eh-2", "User-facing retry guidance for retryable errors", "S", "none")],
              src("models.py", "class ModelError")),
        _item("durable_state", "Durable state", ["Durability", "High availability"], "orange",
              "Recipe flow is stateless; nothing persisted server-side yet",
              "No database backups, restore drill or RPO/RTO for user profiles", [
                  _r("ds-1", "Managed Postgres with point-in-time recovery", "S", "$ (backup storage)"),
                  _r("ds-2", "Quarterly restore drill; target RPO 15 min / RTO 4 h", "M", "none (staff time)")]),
        _item("idempotency", "Idempotency", ["Resiliency", "Durability"], "orange",
              "Contract declares request_id as the idempotency key",
              "No dedupe store, so a retried request is processed twice", [
                  _r("id-1", "Store request_id results for 24 h and return the cached response", "M", "$ (small cache)"),
                  _r("id-2", "Require Idempotency-Key header on POST", "S", "none")],
              src("contracts.py", "request_id: UUID")),
        _item("retries", "Retries and rate limits", ["Resiliency", "Scalability", "High availability", "Cost"], "orange",
              "SDK retries up to 2 times on retryable errors; 60 s timeout",
              "No client-side rate limiter, circuit breaker or per-user quota", [
                  _r("rl-1", "Per-user rate limit on /recipes", "S", "none"),
                  _r("rl-2", "Circuit breaker on the model adapter with a fallback message", "M", "none"),
                  _r("rl-3", "Gateway with org budgets and provider fallback (LiteLLM / Portkey)", "M", "$-$$", "P1")],
              src("models.py", "max_retries=2")),
        _item("observability", "Observability", ["Quality", "Resiliency", "Scalability", "High availability"], "orange" if not self_obs else "mustard",
              "Per-run tool invocation log; OpenTelemetry selected" + (" and kept in your account" if self_obs else ""),
              "OTel exporter not wired; no traces, dashboards or latency SLOs", [
                  _r("ob-1", "Wire OTel GenAI spans with trace IDs in logs", "M", "$ (trace volume)"),
                  _r("ob-2", "Dashboards: p95 latency, cost per success, guard blocks", "S", "$"),
                  _r("ob-3", "Keep prompt/response capture off; redact health fields", "S", "none")],
              src("pipeline.py", "def _timed")),
        _item("evaluations", "Evaluations", ["Quality"], ev_status,
              "10-case suite with deterministic gates; verdicts with evidence" + (" (simulated)" if evidence and evidence.get("simulated") else ""),
              "Simulated evidence; 10 cases is below the 25 required; not run in CI" if ev_status != "green" else "Not yet continuous", [
                  _r("ev-1", "Run live evals on every manifest change in CI", "S", "$ (eval tokens per run)"),
                  _r("ev-2", "Grow the suite to 25+ cases incl. adversarial dosing prompts", "M", "none"),
                  _r("ev-3", "Sample production traffic for weekly quality review", "M", "$", "P1")],
              src("evals.py", "def run_suite")),
        _item("workflow_recovery", "Workflow recovery", ["Resiliency", "Durability", "High availability"], "green",
              "Single-pass flow; nothing to resume (durability level 0 is correct here)",
              "Revisit when CGM sync or meal plans add multi-step jobs", [
                  _r("wr-1", "Adopt the Postgres job queue pattern when background sync is added", "M", "none", "P1")]),
        _item("tenant_isolation", "Tenant and user isolation", ["Security", "Scalability"], "orange",
              "No user data stored yet; database shared with identity",
              "No row-level security or per-user data scoping", [
                  _r("ti-1", "Row-level security on every user table", "M", "none"),
                  _r("ti-2", "Separate DB roles per service", "S", "none")]),
        _item("injection", "Prompt and tool injection", ["Security", "Quality"], "mustard",
              "Dosing guard before the model; tools never chosen by the model; retrieved text labelled; corpus safety-screened",
              "No detector for injected instructions in free text", [
                  _r("pi-1", "Add an injection classifier on free-text fields", "M", "$ per check (vendor) or none (OSS)"),
                  _r("pi-2", "Red-team suite in CI (dosing, jailbreak, injection)", "M", "$ (eval tokens)")],
              src("guards.py", "_DOSING = re.compile")),
        _item("dlp", "Data loss prevention", ["Security", "Governance"], "orange",
              "Health fields tagged with data classes; note never sent to the model",
              "Redaction is declared, not enforced in logs or traces", [
                  _r("dl-1", "Enforce redaction of health-class fields in logs and traces", "M", "none"),
                  _r("dl-2", "Pre-send check that blocks restricted fields to providers", "M", "none")],
              src("contracts.py", 'data_class="health"')),
        _item("sovereignty", "Data residency and sovereignty", ["Governance", "Security"], "orange",
              "Policy says US",
              "Region pinning per vendor not configured", [
                  _r("so-1", "Pin model inference to US (e.g. US-only inference)", "S", "about +10% model cost"),
                  _r("so-2", "Pin DB, tracing and auth regions; record in the manifest", "S", "none")]),
        _item("governance", "Governance", ["Governance"], "mustard",
              "Rationale per layer; agent, tool and knowledge registries; drift checks; risk register",
              "No reviewer approval for changes; policies not enforced in CI", [
                  _r("gv-1", "Two-person approval for model and data-class changes", "M", "none", "P1"),
                  _r("gv-2", "Policy-as-code check in CI (allowed providers, regions)", "M", "none", "P2")]),
        _item("audit", "Audit and compliance evidence", ["Governance"], "orange",
              f"Session audit log ({audit_events} event{'' if audit_events == 1 else 's'}); evidence pack mapped to NIST AI RMF",
              "Audit log is in memory only; no exportable evidence pack", [
                  _r("au-1", "Append-only, hash-chained audit store", "M", "$ (storage)"),
                  _r("au-2", "Exportable evidence pack per release", "S", "none")]),
        _item("rollout", "Staged deployment and rollback", ["Resiliency", "Quality", "High availability"], "orange",
              "Manifest revisions can be rolled back; generated app has a Dockerfile",
              "No canary, feature flags or automated rollback", [
                  _r("ro-1", "Feature flag per model/provider for canary rollout", "M", "none"),
                  _r("ro-2", "Shadow traffic before switching models", "M", "$ (duplicate calls)"),
                  _r("ro-3", "Automatic rollback when quality gates fail", "M", "none", "P1")]),
        _item("capacity", "Capacity and autoscaling", ["Scalability", "Cost"],
              "orange" if deployments.get("experience") == "self-hosted" else "mustard",
              "API runs on " + ("self-hosted servers you scale manually" if deployments.get("experience") == "self-hosted"
                                else "a platform that autoscales") + "; tools run in-process",
              "No load test, capacity target or database connection pooling", [
                  _r("ca-1", "Load test to 10x expected peak; set a capacity target", "M", "$ (test runs)"),
                  _r("ca-2", "Database connection pooling", "S", "none"),
                  _r("ca-3", "Cache recipes for repeated requests", "M", "saves model cost on repeats"),
                  _r("ca-4", "Provider rate-limit tier sized for peak", "S", "plan-dependent")]),
        _item("availability", "Availability and failover", ["High availability", "Resiliency"], "orange",
              "Single region; managed platform restarts failed instances",
              "No availability SLO, health checks, multi-zone database or model-provider fallback", [
                  _r("ha-1", "Availability SLO (e.g. 99.5%) with health and readiness checks", "S", "none"),
                  _r("ha-2", "Minimum instances above zero to avoid cold starts at peak", "S", "$ (idle instances)"),
                  _r("ha-3", "Multi-zone database with automatic failover", "M", "$$ (standby)"),
                  _r("ha-4", "Fallback to a second verified model when the provider is down", "M", "none until used", "P1")]),
        _item("cost_controls", "Cost controls", ["Cost", "Scalability"], "mustard",
              "Cost per successful task visible with ranges; prices sourced and dated",
              "No budgets, alerts or cost-saving levers enabled", [
                  _r("cc-1", "Monthly budget with alerts at 50/80/100%", "S", "none"),
                  _r("cc-2", "Prompt caching on the system prompt", "S", "saves on cached input tokens"),
                  _r("cc-3", "Evaluate a Haiku-first cascade (escalate on gate failure)", "M", "could cut model cost several-fold - needs evidence"),
                  _r("cc-4", "Batch API for offline jobs (e.g. weekly plans)", "S", "50% off eligible calls", "P1")]),
    ]
    for it in items:
        for r in it["recommendations"]:
            r["enabled"] = r["id"] in PLAN
    counts = {s: sum(1 for i in items if i["status"] == s) for s in STATUS_POINTS}
    score = round(100 * sum(STATUS_POINTS[i["status"]] for i in items) / (3 * len(items)))
    return {"headline": "For enterprise-grade quality, resiliency, durability, governance and security at scale - "
                        "keeping cost sensitivity in perspective - here are the attributes we need to establish or strengthen.",
            "items": items, "counts": counts, "score": score, "plan": sorted(PLAN),
            "note": "Scores reflect what this build does today. Enabling a recommendation adds it to the "
                    "enablement plan in the manifest; scores change when the build changes."}


def set_plan(ids: list[str]) -> list[str]:
    PLAN.clear()
    PLAN.update(ids)
    return sorted(PLAN)
