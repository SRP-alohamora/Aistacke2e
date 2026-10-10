# aistack: managed - health conditions and dietary restrictions -> ingredient exclusions.
"""Simplified, rule-based mappings for the demo ingredient table. Not medical advice."""
from __future__ import annotations

_VEGETARIAN = ["chicken breast", "salmon", "shrimp", "ground turkey", "lean beef"]
_DAIRY = ["paneer", "cheddar", "feta", "greek yogurt (plain)"]

RESTRICTIONS: dict[str, dict] = {
    "gluten_free": {"label": "Celiac / gluten-free",
                    "exclude": ["whole wheat tortilla", "naan", "whole wheat pita", "udon noodles (cooked)",
                                "soba noodles (cooked)", "whole wheat bread", "soy sauce", "rolled oats (dry)"]},
    "dairy_free": {"label": "Lactose intolerance / dairy-free", "exclude": _DAIRY},
    "nut_free": {"label": "Nut allergy", "exclude": ["peanuts", "cashews", "peanut butter"]},
    "shellfish_free": {"label": "Shellfish allergy", "exclude": ["shrimp"]},
    "low_sodium": {"label": "High blood pressure / low sodium",
                   "exclude": ["soy sauce", "kimchi", "gochujang", "feta", "salsa", "cheddar"]},
    "vegetarian": {"label": "Vegetarian", "exclude": _VEGETARIAN},
    "vegan": {"label": "Vegan", "exclude": _VEGETARIAN + _DAIRY + ["eggs", "honey"]},
}


def exclusions_for(keys: list[str]) -> list[str]:
    out: list[str] = []
    for k in keys:
        for item in RESTRICTIONS[k]["exclude"]:
            if item not in out:
                out.append(item)
    return out


def labels_for(keys: list[str]) -> list[str]:
    return [RESTRICTIONS[k]["label"] for k in keys]
