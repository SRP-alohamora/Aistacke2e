# aistack: managed - nutrition goals per meal -> carb target, exclusions and checks.
"""Simplified per-meal targets for the demo. Not medical advice."""
from __future__ import annotations

GOALS: dict[str, dict] = {
    "balanced": {"label": "Balanced", "carb_target_g": 45, "checks": []},
    "high_protein": {"label": "High protein", "carb_target_g": 40, "checks": [("protein_g", ">=", 35)]},
    "keto": {"label": "Keto (high protein + fat)", "carb_target_g": 20,
             "checks": [("carbs_g", "<=", 25), ("protein_g", ">=", 30), ("fat_g", ">=", 30)]},
    "high_fiber": {"label": "High fiber", "carb_target_g": 45, "checks": [("fiber_g", ">=", 10)]},
    "low_sodium": {"label": "Low sodium", "carb_target_g": None, "checks": [("sodium_mg", "<=", 600)],
                   "exclude": ["soy sauce", "kimchi", "gochujang", "feta", "salsa", "cheddar"]},
}

UNITS = {"protein_g": "g protein", "fat_g": "g fat", "fiber_g": "g fiber", "carbs_g": "g carbs", "sodium_mg": "mg sodium"}


def carb_target_for(goals: list[str], default: float = 45) -> float:
    targets = [GOALS[g]["carb_target_g"] for g in goals if GOALS[g]["carb_target_g"] is not None]
    return min(targets) if targets else default


def exclusions_for_goals(goals: list[str]) -> list[str]:
    return [x for g in goals for x in GOALS[g].get("exclude", [])]


def evaluate(goals: list[str], nutrients: dict) -> list[dict]:
    out = []
    for g in goals:
        checks = GOALS[g]["checks"]
        results = []
        for field, op, target in checks:
            value = nutrients[field]
            ok = value >= target if op == ">=" else value <= target
            results.append({"field": field, "value": value, "target": target, "op": op, "met": ok,
                            "text": f"{value:g} {UNITS[field]} ({'≥' if op == '>=' else '≤'} {target})"})
        out.append({"key": g, "label": GOALS[g]["label"], "met": all(r["met"] for r in results),
                    "checks": results})
    return out
