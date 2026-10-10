"""Cost per successful task, as low / expected / high ranges with provenance."""
from __future__ import annotations

import math

from .config import prices


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def attempt_cost(entry: dict, cached_in: float, uncached_in: float, out: float) -> float:
    cache_rate = entry["cache_read"] if entry.get("cache_read") is not None else entry["input"]
    return (cached_in * cache_rate + uncached_in * entry["input"] + out * entry["output"]) / 1e6


def estimate(model_key: str, evidence: dict | None = None,
             success_rate_override: float | None = None) -> dict:
    p = prices()
    entry = p["models"][model_key]
    prof = p["template_token_profile"]
    assumptions = []

    if evidence and evidence.get("avg_tokens"):
        t = evidence["avg_tokens"]
        cached, uncached, out = t["cache_read"], t["input"], t["output"]
        token_source = ("simulated eval run (token counts approximated)" if evidence.get("simulated")
                        else "measured in eval run") + f" {evidence['evidence_id']}"
    else:
        cached, uncached, out = prof["cached_input"], prof["uncached_input"], prof["output"]
        token_source = "template token profile rag@1.2.0 (illustrative)"
    assumptions.append(f"tokens per attempt: {int(cached)} cached + {int(uncached)} uncached input, "
                       f"{int(out)} output - {token_source}; range +/-30%")
    if entry.get("cache_read") is None:
        assumptions.append("cache discount not verified for this model: cached tokens priced at full input rate")

    overhead = prof["retry_overhead"]
    if evidence and evidence.get("n_task_cases"):
        s = evidence["success"]["passed"] / evidence["n_task_cases"]
        lo_s, hi_s = wilson(evidence["success"]["passed"], evidence["n_task_cases"])
        sr_source = ("SIMULATED" if evidence.get("simulated") else "measured") + \
            f" success {evidence['success']['passed']}/{evidence['n_task_cases']} (Wilson 95% CI)"
    elif success_rate_override is not None:
        s, lo_s, hi_s = success_rate_override, success_rate_override, success_rate_override
        sr_source = "user-supplied success rate"
    else:
        s, lo_s, hi_s = None, None, None
        sr_source = "no evidence: success rate unknown"
    assumptions.append(sr_source)
    assumptions.append(f"retry/repair overhead {int(overhead * 100)}%")

    per_attempt = {
        "low": attempt_cost(entry, cached * 0.7, uncached * 0.7, out * 0.7),
        "expected": attempt_cost(entry, cached, uncached, out),
        "high": attempt_cost(entry, cached * 1.3, uncached * 1.3, out * 1.3),
    }
    per_success = None
    if s:
        per_success = {
            "low": per_attempt["low"] * (1 + overhead) / max(hi_s, 1e-9),
            "expected": per_attempt["expected"] * (1 + overhead) / s,
            "high": per_attempt["high"] * (1 + overhead) / max(lo_s, 0.05),
        }
    fixed = sum(p["fixed_monthly_usd"].values())
    monthly = []
    for name, tasks in p["scenarios"].items():
        basis = per_success or per_attempt
        monthly.append({"scenario": name, "tasks_per_month": tasks,
                        "marginal_usd": {k: round(v * tasks, 2) for k, v in basis.items()},
                        "basis": "per successful task" if per_success else "per attempt (success unknown)",
                        "fixed_usd": fixed})
    return {
        "model_key": model_key, "label": entry["label"],
        "price_catalog_version": p["catalog_version"],
        "prices": {k: entry[k] for k in ("input", "output", "cache_read", "cache_write")},
        "per_attempt_usd": {k: round(v, 6) for k, v in per_attempt.items()},
        "per_successful_task_usd": {k: round(v, 6) for k, v in per_success.items()} if per_success else None,
        "success_rate": round(s, 3) if s is not None else None,
        "monthly": monthly,
        "fixed_items": p["fixed_monthly_usd"],
        "assumptions": assumptions,
        "sources": [{"url": entry["source"], "verified_at": entry["verified_at"]}],
        "simulated": bool(evidence and evidence.get("simulated")),
    }
