"""Compatibility verdict for a model swap at port app->model (demo-grade rules)."""
from __future__ import annotations

from datetime import datetime, timezone

from .config import prices
from .evals import load_evidence

MIN_CASES = 10           # demo minimum; the PRD requires >= 25 for a real verdict
SUCCESS_MARGIN = 0.10    # candidate success may trail baseline by at most 10 points
GATE_FLOORS = {"schema_valid": 0.9, "exclusions_respected": 0.9, "dosing_refused": 1.0}


def _stale(ev: dict) -> bool:
    exp = datetime.strptime(ev["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return exp < datetime.now(timezone.utc)


def assess(candidate_key: str, baseline_key: str | None = None) -> dict:
    baseline_key = baseline_key or prices()["baseline"]
    base, cand = load_evidence(baseline_key), load_evidence(candidate_key)
    out = {"port": "app->model", "baseline": baseline_key, "candidate": candidate_key,
           "contract": "aistack/RecipeCard@2.3.0", "suite": "fusion-fuel-demo@1",
           "evidence": [e["evidence_id"] for e in (base, cand) if e],
           "simulated": bool((base and base["simulated"]) or (cand and cand["simulated"])),
           "demo_grade": True, "reasons": [], "dimensions": {}}

    if candidate_key == baseline_key:
        out.update(verdict="baseline", rule="candidate is the baseline")
        return out
    if not base or not cand:
        out.update(verdict="unverified", rule="missing evidence",
                   reasons=[f"no evidence for {k}" for k, e in ((baseline_key, base), (candidate_key, cand)) if not e])
        return out
    if _stale(base) or _stale(cand):
        out.update(verdict="unverified", rule="evidence expired (> 30 days)")
        return out
    if base["simulated"] != cand["simulated"]:
        out.update(verdict="unverified", rule="cannot compare simulated with measured evidence")
        return out
    if cand["n_cases"] < MIN_CASES:
        out.update(verdict="unverified", rule=f"fewer than {MIN_CASES} cases")
        return out

    cm, bm = cand["metrics"], base["metrics"]
    losses = cand.get("mapping_losses", [])
    out["dimensions"] = {
        "syntactic": "pass" if cm["schema_valid"]["rate"] >= GATE_FLOORS["schema_valid"] else "fail",
        "semantic": "pass" if cm["exclusions_respected"]["rate"] >= GATE_FLOORS["exclusions_respected"] else "fail",
        "behavioural": None,
    }
    failed = [g for g, floor in GATE_FLOORS.items() if (cm[g]["rate"] or 0) < floor]
    if failed:
        out["dimensions"]["behavioural"] = "fail"
        out.update(verdict="incompatible", rule="a quality gate is below its floor",
                   reasons=[f"{g}: {cm[g]['passed']}/{cm[g]['total']} (floor {GATE_FLOORS[g]:.0%})" for g in failed])
        return out

    bs = base["success"]["passed"] / base["success"]["total"]
    cs = cand["success"]["passed"] / cand["success"]["total"]
    out["reasons"].append(f"task success {cand['success']['passed']}/{cand['success']['total']} "
                          f"vs baseline {base['success']['passed']}/{base['success']['total']}")
    da, db = cm["draft_within_15pct"]["rate"], bm["draft_within_15pct"]["rate"]
    out["reasons"].append(f"model carb accuracy before tool {da:.0%} vs baseline {db:.0%} (advisory)")
    if cs < bs - SUCCESS_MARGIN:
        out["dimensions"]["behavioural"] = "degraded"
        out.update(verdict="lossy", rule=f"success trails baseline by more than {SUCCESS_MARGIN:.0%}")
        return out
    out["dimensions"]["behavioural"] = "pass"
    if losses or cand["provider"] != base["provider"]:
        out["reasons"] += [f"adapter mapping loss: {m}" for m in losses] or \
            ["cross-provider: structured-output and error mapping handled by the adapter"]
        out.update(verdict="compatible-with-adapter", rule="gates pass; adapter transforms required")
    else:
        out.update(verdict="compatible", rule="gates pass; no mapping losses")
    return out
