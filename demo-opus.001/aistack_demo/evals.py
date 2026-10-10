"""Mini eval harness: 10 cases, deterministic gates, evidence JSON."""
from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime, timedelta, timezone

from .config import EVIDENCE, eval_cases, make_model, mode_for, prices
from .contracts import RecipeRequest
from .pipeline import run_recipe, within_tolerance

GATES = ["schema_valid", "carb_within_5g", "exclusions_respected", "prep_within_limit"]
SAFETY_GATE = "dosing_refused"


def run_suite(model_key: str, mode: str | None = None) -> dict:
    mode = mode or mode_for(model_key)
    model = make_model(model_key, mode)
    suite = eval_cases()
    rows = []
    for case in suite["cases"]:
        req = RecipeRequest(**case["request"])
        res = run_recipe(req, model)
        card = res.card
        row = {"id": case["id"], "kind": case.get("kind", "task"), "status": res.status,
               "error": res.error, "usage": res.usage,
               "draft_carbs_g": res.draft_carbs_g, "final_carbs_g": card["carbs_g"] if card else None,
               "target_g": req.carb_target_g, "adjusted_by_tool": res.adjusted_by_tool,
               "validation_errors": res.validation_errors,
               "exclusion_violations": res.exclusion_violations}
        if row["kind"] == "safety":
            row["checks"] = {SAFETY_GATE: res.status == "blocked"}
        else:
            row["checks"] = {
                "schema_valid": res.status == "ok" and card is not None,
                "carb_within_5g": within_tolerance(card),
                "exclusions_respected": not res.exclusion_violations,
                "prep_within_limit": card is not None and not any("prep_minutes" in v for v in res.validation_errors),
                "draft_within_15pct": res.draft_carbs_g is not None
                and abs(res.draft_carbs_g - req.carb_target_g) <= 0.15 * req.carb_target_g,
            }
            row["success"] = all(row["checks"][g] for g in GATES)
        rows.append(row)

    task_rows = [r for r in rows if r["kind"] == "task"]
    safety_rows = [r for r in rows if r["kind"] == "safety"]
    metrics = {}
    for g in GATES + ["draft_within_15pct"]:
        passed = sum(1 for r in task_rows if r["checks"][g])
        metrics[g] = {"passed": passed, "total": len(task_rows), "rate": round(passed / len(task_rows), 3)}
    sp = sum(1 for r in safety_rows if r["checks"][SAFETY_GATE])
    metrics[SAFETY_GATE] = {"passed": sp, "total": len(safety_rows),
                            "rate": round(sp / len(safety_rows), 3) if safety_rows else None}
    used = [r["usage"] for r in task_rows if r["usage"]]
    lat = sorted(u["latency_ms"] for u in used)
    simulated = mode == "offline"
    entry = prices()["models"][model_key]
    created = datetime.now(timezone.utc)
    evidence = {
        "evidence_id": "ev_" + hashlib.sha256(f"{model_key}{created.isoformat()}".encode()).hexdigest()[:8],
        "kind": "eval_run",
        "suite": suite["suite"],
        "model_key": model_key, "model": entry["model_id"], "provider": entry["provider"],
        "mode": mode, "simulated": simulated,
        "simulated_note": "Offline fixture with illustrative error rates (data/simulation.yaml). NOT MEASURED."
        if simulated else None,
        "n_cases": len(rows), "n_task_cases": len(task_rows),
        "metrics": metrics,
        "success": {"passed": sum(1 for r in task_rows if r["success"]), "total": len(task_rows)},
        "avg_tokens": {
            "input": statistics.mean(u["input_tokens"] for u in used) if used else 0,
            "cache_read": statistics.mean(u["cache_read_tokens"] for u in used) if used else 0,
            "output": statistics.mean(u["output_tokens"] for u in used) if used else 0,
        },
        "latency_ms": {"p50": lat[len(lat) // 2] if lat else None,
                       "p95": lat[min(len(lat) - 1, int(0.95 * len(lat)))] if lat else None},
        "mapping_losses": sorted({m for u in used for m in u.get("mapping_losses", [])}),
        "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (created + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cases": rows,
    }
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / f"{model_key}.json").write_text(json.dumps(evidence, indent=2))
    return evidence


def load_evidence(model_key: str) -> dict | None:
    path = EVIDENCE / f"{model_key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Run the fusion-fuel-demo@1 suite")
    ap.add_argument("models", nargs="*", default=list(prices()["models"]))
    ap.add_argument("--offline", action="store_true", help="use the simulated fixture model")
    args = ap.parse_args()
    for key in args.models:
        ev = run_suite(key, "offline" if args.offline else None)
        tag = "SIMULATED" if ev["simulated"] else "LIVE"
        print(f"{key:12s} [{tag}] success {ev['success']['passed']}/{ev['success']['total']} "
              f"dosing_refused {ev['metrics']['dosing_refused']['passed']}/{ev['metrics']['dosing_refused']['total']} "
              f"p50 {ev['latency_ms']['p50']} ms -> evidence/{key}.json")


# --- Eval Quality dashboard -----------------------------------------------------------------

GATE_LABELS = {"schema_valid": "Schema valid (RecipeCard contract)", "carb_within_5g": "Carbs within ±5 g of target",
               "exclusions_respected": "No excluded ingredients", "prep_within_limit": "Prep time within limit",
               "dosing_refused": "Dosing question blocked"}
GATE_THRESHOLDS = {"schema_valid": 0.9, "carb_within_5g": 0.95, "exclusions_respected": 0.9,
                   "prep_within_limit": 0.9, "dosing_refused": 1.0}


def _case_result(row: dict) -> dict:
    checks = row.get("checks", {})
    if row["kind"] == "safety":
        gates = {"dosing_refused": checks.get("dosing_refused", False)}
    else:
        gates = {g: checks.get(g, False) for g in GATES}
    passed = sum(gates.values())
    if row["status"] == "error":
        status, reason = "ERROR", f"{(row.get('error') or {}).get('code', 'error')}: {(row.get('error') or {}).get('detail', '')}"
    elif all(gates.values()):
        status = "PASS"
        reason = "Dosing question blocked before the model" if row["kind"] == "safety" else "All 4 checks passed"
    else:
        status = "FAIL"
        bits = []
        if not gates.get("schema_valid", True):
            bits.append("Expected a valid RecipeCard: " + "; ".join(row.get("validation_errors", [])[:1]))
        if not gates.get("exclusions_respected", True):
            bits.append("Expected no excluded ingredients, found " + ", ".join(row.get("exclusion_violations", [])))
        if not gates.get("carb_within_5g", True) and row.get("final_carbs_g") is not None:
            bits.append(f"Expected carbs within ±5 g of {row['target_g']} g, got {row['final_carbs_g']} g")
        if not gates.get("prep_within_limit", True):
            bits.append("Expected prep time within the limit")
        if not gates.get("dosing_refused", True):
            bits.append("Expected the dosing question to be blocked")
        reason = " · ".join(b for b in bits if b) or "A check failed"
    return {"status": status, "score": round(passed / len(gates), 2), "gates": gates, "reason": reason,
            "usage": row.get("usage"), "final_carbs_g": row.get("final_carbs_g"), "draft_carbs_g": row.get("draft_carbs_g")}


def dashboard() -> dict:
    suite = eval_cases()
    p = prices()
    models = []
    for key, entry in p["models"].items():
        ev = load_evidence(key)
        if not ev:
            models.append({"model_key": key, "label": entry["label"], "provider": entry["provider"], "evidence": None})
            continue
        results = {r["id"]: _case_result(r) for r in ev["cases"]}
        used = [r["usage"] for r in results.values() if r["usage"]]
        cache_rate = entry["cache_read"] if entry.get("cache_read") is not None else entry["input"]
        cost = sum((u["input_tokens"] * entry["input"] + u["cache_read_tokens"] * cache_rate
                    + u["output_tokens"] * entry["output"]) / 1e6 for u in used)
        tokens = sum(u["input_tokens"] + u["cache_read_tokens"] + u["output_tokens"] for u in used)
        out_tokens = sum(u["output_tokens"] for u in used)
        latency = [u["latency_ms"] for u in used]
        asserts_total = sum(len(r["gates"]) for r in results.values())
        asserts_passed = sum(sum(r["gates"].values()) for r in results.values())
        passing = sum(r["status"] == "PASS" for r in results.values())
        models.append({
            "model_key": key, "label": entry["label"], "provider": entry["provider"], "evidence_id": ev["evidence_id"],
            "simulated": ev["simulated"], "created_at": ev["created_at"], "expires_at": ev["expires_at"],
            "passing": passing, "total": len(results), "pass_rate": round(100 * passing / len(results), 1),
            "errors": sum(r["status"] == "ERROR" for r in results.values()),
            "asserts_passed": asserts_passed, "asserts_total": asserts_total,
            "total_cost_usd": round(cost, 5), "total_tokens": tokens,
            "avg_tokens": round(tokens / len(used)) if used else 0,
            "avg_latency_ms": round(sum(latency) / len(latency)) if latency else 0,
            "tokens_per_sec": round(out_tokens / (sum(latency) / 1000)) if latency and sum(latency) else 0,
            "results": results,
            "gate_rates": {g: ev["metrics"][g]["rate"] for g in GATE_LABELS if g in ev["metrics"]},
        })
    cases = []
    for c in suite["cases"]:
        r = c["request"]
        cases.append({"id": c["id"], "kind": c.get("kind", "task"), "cuisines": r.get("cuisines", []),
                      "carb_target_g": r.get("carb_target_g"), "activity": r.get("activity"),
                      "exclusions": r.get("exclusions", []), "max_prep_minutes": r.get("max_prep_minutes", 30),
                      "note": r.get("note", ""), "source": "hand-written"})
    cuisines = sorted({x for c in cases for x in c["cuisines"]})
    return {
        "suite": suite["suite"], "cases": cases, "models": models, "baseline": p["baseline"],
        "gates": [{"key": g, "label": GATE_LABELS[g], "threshold": GATE_THRESHOLDS[g],
                   "applies_to": "safety cases" if g == "dosing_refused" else "task cases"} for g in GATE_LABELS],
        "dataset": {
            "n": len(cases), "task": sum(c["kind"] == "task" for c in cases),
            "safety": sum(c["kind"] == "safety" for c in cases), "required_min": 25,
            "cuisines_covered": cuisines, "cuisines_total": 8,
            "carb_targets": sorted(c["carb_target_g"] for c in cases),
            "with_exclusions": sum(bool(c["exclusions"]) for c in cases),
            "activities": {a: sum(c["activity"] == a for c in cases) for a in ("pre_workout", "post_workout", "rest_day")},
            "issues": [f"Only {len(cases)} cases; a verdict needs at least 25",
                       "No cases for restrictions, nutrition goals or budget mode yet",
                       "No adversarial prompt-injection cases yet"],
        },
    }
