"""Privacy & governance report for the current manifest, plus an in-memory audit log of this session.

Checks score what the build does today (pass / warn / fail / na), like the Security column.
Framework mapping is evidence mapping, not certification.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .assurance import src
from .contracts import RecipeRequest

AUDIT: list[dict] = []
_LAST: dict = {}

PRD_URL = "https://claude.ai/code/artifact/64ee7cae-5412-4e19-a472-baa9e06a424e"

# Which third party processes data for each deployment choice (qualitative; DPAs not verified).
PROCESSORS = {
    "experience": {"cloud-run": "Google Cloud", "fly": "Fly.io", "render": "Render", "self-hosted": None},
    "model": {"claude-api": "Anthropic", "bedrock": "Amazon Web Services", "vertex": "Google Cloud",
              "foundry": "Microsoft", "openai-api": "OpenAI", "azure-openai": "Microsoft"},
    "retrieval_store": {"supabase": "Supabase", "neon": "Neon", "cloud-sql": "Google Cloud", "self-hosted": None},
    "observability": {"langfuse-cloud": "Langfuse (ClickHouse)", "langfuse-self": None, "cloud-trace": "Google Cloud",
                      "datadog": "Datadog"},
    "identity": {"supabase-auth": "Supabase", "firebase-auth": "Google Cloud", "clerk": "Clerk", "auth0": "Okta"},
}
SENT_TO = {"experience": "all request fields", "model": "request fields except note and request_id",
           "retrieval_store": "cuisines only", "observability": "trace metadata (content capture off)",
           "identity": "account identity only"}


def audit(action: str, detail: str) -> None:
    AUDIT.append({"at": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"), "actor": "demo user",
                  "action": action, "detail": detail})
    del AUDIT[:-200]


def record_recommendation(model_key: str, follow_ups: dict, deployments: dict) -> None:
    """Log what changed since the previous recommendation."""
    prev = dict(_LAST)
    _LAST.update(model_key=model_key, follow_ups=dict(follow_ups), deployments=dict(deployments))
    if not prev:
        audit("manifest.created", f"model {model_key}")
        return
    if prev["model_key"] != model_key:
        audit("model.selected", f"{prev['model_key']} -> {model_key}")
    for k, v in follow_ups.items():
        if prev["follow_ups"].get(k) != v:
            audit("decision.answered", f"{k} = {'Yes' if v else 'No'}")
    for k, v in deployments.items():
        if prev["deployments"].get(k) != v:
            audit("deployment.changed", f"{k} -> {v}")


def _c(name: str, status: str, finding: str, fix: str = "", href: str | None = None) -> dict:
    return {"check": name, "status": status, "finding": finding, "fix": fix, "href": href}


def data_map(follow_ups: dict) -> list[dict]:
    props = RecipeRequest.model_json_schema()["properties"]
    rows = []
    for name, spec in props.items():
        if name == "request_id":
            continue
        cls = spec.get("x-aistack-data-class", "internal")
        to_model = name not in ("note",)
        rows.append({"field": f"RecipeRequest.{name}", "data_class": cls,
                     "flows_to": ["API"] + (["Model provider"] if to_model else []) + (["Retrieval"] if name == "cuisines" else []),
                     "stored": "no (request-scoped)", "minimised": not to_model})
    rows.append({"field": "glucose_readings", "data_class": "health" if follow_ups.get("Q4") else "not collected",
                 "flows_to": ["API", "Database", "Identity-scoped"] if follow_ups.get("Q4") else [],
                 "stored": "yes (per user)" if follow_ups.get("Q4") else "no", "minimised": not follow_ups.get("Q4")})
    return rows


def processors(layers: list[dict]) -> list[dict]:
    out = []
    for l in layers:
        table = PROCESSORS.get(l["key"])
        if not table or l["state"] == "none":
            continue
        who = table.get(l.get("deployment"))
        out.append({"layer": l["friendly"], "deployment": l.get("deployment"),
                    "processor": who or "you (self-hosted)", "receives": SENT_TO.get(l["key"], "-"),
                    "dpa": "not needed" if who is None else "verify", "region": "us (policy) - pinning to verify"})
    return out


def report(rec: dict, follow_ups: dict, evidence: dict | None) -> dict:
    glucose = bool(follow_ups.get("Q4"))
    procs = processors(rec["layers"])
    third = [p for p in procs if p["dpa"] == "verify"]
    model_dep = next((l.get("deployment") for l in rec["layers"] if l["key"] == "model"), None)
    privacy = [
        _c("Data minimisation", "pass", "The free-text note and request ID are never sent to the model provider",
           href=src("pipeline.py", 'exclude={"request_id", "note"}')),
        _c("Health data classification", "warn" if glucose else "pass",
           "Glucose readings stored per user: health data" if glucose else
           "Health-adjacent fields tagged on the contract; no glucose readings collected",
           "HIPAA / state health-privacy review; consent; retention limits" if glucose else "",
           src("contracts.py", 'data_class="health"')),
        _c("Consent and privacy notice", "fail", "No consent step or privacy notice in the app yet",
           "Add a privacy notice and consent before the first recipe"),
        _c("Retention and deletion", "warn", "Nothing is stored server-side in the demo; no production retention policy",
           "Define retention per data class (e.g. 30 days for request logs)"),
        _c("User rights (access, export, delete)", "fail", "Not implemented", "Self-serve export and delete (P1)"),
        _c("Third-party processors", "warn" if third else "pass",
           f"{len(third)} processors receive data; data processing agreements not verified" if third else "All self-hosted",
           "Sign DPAs; list processors in the privacy notice"),
        _c("Model provider data use", "warn",
           "Training and retention terms depend on the provider plan" + (" and platform" if model_dep and not model_dep.endswith("-api") else ""),
           "Confirm zero-data-retention or no-training terms in writing"),
        _c("Region and cross-border", "warn", "Policy says US; per-vendor region pinning not configured",
           "Pin regions per vendor (e.g. US-only inference)"),
        _c("Personal data in logs", "warn", "Prompt and response capture off by default (declared, not enforced in demo)",
           "Enforce redaction of health-class fields in the trace exporter", src("recommender.py", "prompt capture off by default")),
    ]
    ev_status = "fail" if not evidence else ("warn" if evidence.get("simulated") else "pass")
    governance = [
        _c("Architecture decisions recorded", "pass", "Every layer has a rationale and the requirements that drove it",
           href=src("recommender.py", "driven_by=")),
        _c("Model governance (evaluation evidence)", ev_status,
           "No eval evidence" if not evidence else ("Evidence is simulated" if evidence.get("simulated") else "Measured evidence on file"),
           "Run live evals before release", src("compat.py", "def assess")),
        _c("Policy as code", "warn", "Allowed providers, regions and data classes declared in the manifest; enforced only by the recommender",
           "Enforce in CI and at merge (P2)", src("recommender.py", '"allowedProviders"')),
        _c("Change approval", "warn", "Single-user changes; no reviewer sign-off", "Multi-approver workflow (P1)"),
        _c("Audit trail", "warn", f"{len(AUDIT)} event{'' if len(AUDIT) == 1 else 's'} this session (in memory, not persisted)",
           "Append-only, hash-chained audit store (PRD FR-PLT-3)"),
        _c("Agent and tool inventory", "pass", "8 agents/tools and 8 tool schemas registered with drift checks",
           href=src("tools.py", "def drift_summary")),
        _c("Safety for health content", "pass", "Dosing questions blocked; disclaimer on every card; carbs never from the model",
           href=src("guards.py", "_DOSING = re.compile")),
        _c("Risk register", "pass", "Risks R1-R17 tracked in the PRD", href=PRD_URL),
        _c("Supply chain (SBOM, pinned dependencies)", "warn", "Dependencies pinned via uv.lock; no SBOM in the generated app yet",
           "Generate a CycloneDX SBOM per build"),
    ]
    frameworks = [
        {"framework": "NIST AI RMF - Govern", "evidence": "Manifest rationale, policies, audit log, risk register"},
        {"framework": "NIST AI RMF - Map", "evidence": "Data map, processors, agent registry, tool registry"},
        {"framework": "NIST AI RMF - Measure", "evidence": "Eval evidence, guardrail status, security checks, drift checks"},
        {"framework": "NIST AI RMF - Manage", "evidence": "Deployment choices, enhancement drafts, manifest rollback"},
        {"framework": "ISO/IEC 42001 (AI management system)", "evidence": "This evidence pack can support an assessment; clause mapping not done"},
    ]
    def count(rows):
        return {s: sum(1 for r in rows if r["status"] == s) for s in ("pass", "warn", "fail")}
    return {"data_map": data_map(follow_ups), "processors": procs, "privacy": privacy, "governance": governance,
            "frameworks": frameworks, "audit": list(reversed(AUDIT[-30:])),
            "summary": {"privacy": count(privacy), "governance": count(governance)},
            "note": "Scored against what this build does today. Framework rows are evidence mapping, not certification."}


def provenance_for(layer: dict, model_key: str, baseline: str, deployments: dict, follow_ups: dict,
                   evidence: dict | None, catalog_version: str, price_source: str | None) -> dict:
    """Where this layer's selection came from, what backs it, and its change history this session."""
    key = layer["key"]
    user_set = (key == "model" and model_key != baseline) or key in deployments
    affected_by_q = {"identity": "Q4", "experience": "Q4", "nutrition_tool": "Q5"}.get(key)
    source = "user" if user_set else ("decision " + affected_by_q if affected_by_q and affected_by_q in follow_ups else "inferred")
    sources = []
    if key == "model" and price_source:
        sources.append({"text": f"price list ({catalog_version})", "href": price_source})
    sources.append({"text": "recommender rule", "href": src("recommender.py", f'_layer("{key}"')})
    if key in ("model", "nutrition_tool", "experience") and evidence:
        sources.append({"text": f"evidence {evidence['evidence_id']}" + (" (simulated)" if evidence.get("simulated") else ""),
                        "href": None})
    words = {key, key.replace("_", " "), layer["friendly"].lower()}
    if key == "model":
        words |= {"model.selected", "eval.run"}
    if affected_by_q:
        words.add(affected_by_q)
    events = [a for a in AUDIT if a["action"] in words or any(w in a["detail"] for w in words)
              or (key == "model" and a["action"] in ("model.selected", "eval.run"))]
    return {"source": source, "driven_by": layer.get("drivenBy", []), "catalog_version": catalog_version,
            "deployment": layer.get("deployment"), "sources": sources,
            "changes": len(events), "last_change": events[-1]["at"] if events else None, "events": events[-10:]}
