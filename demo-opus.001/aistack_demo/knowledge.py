"""Knowledge layer: domain, data processing pipeline and cleanup checks (the checks really run)."""
from __future__ import annotations

from collections import Counter

from .grocery import DISCLAIMER as PRICE_DISCLAIMER, SAMPLE_PRICE_PER_KG
from .guards import check_request_text
from .nutrition import CARBS_PER_100G, OTHER_PER_100G
from .photos import library

DOMAIN = {
    "name": "Fusion recipes for an active person managing diabetes",
    "sources": [
        {"name": "Recipe pattern corpus", "kind": "curated text", "size_fn": "patterns", "owner": "Product (recipes)"},
        {"name": "Nutrition reference table", "kind": "structured data", "size_fn": "nutrition", "owner": "Nutrition lead",
         "note": "approximate demo values; USDA FoodData Central in production"},
        {"name": "Store price table", "kind": "structured data", "size_fn": "prices", "owner": "Product (budget)",
         "note": "sample prices, not live quotes"},
        {"name": "Photo library", "kind": "images + licence metadata", "size_fn": "photos", "owner": "Design",
         "note": "Wikimedia Commons, CC / public domain"},
    ],
    "vocabulary": ["cuisine", "ingredient (normalised name)", "grams", "carbohydrate / protein / fat / sodium / fiber per 100 g",
                   "activity timing", "restriction", "nutrition goal"],
}

PIPELINE = [
    {"step": "Ingest", "what": "Load recipe patterns, nutrition rows, prices and photo metadata from versioned files"},
    {"step": "Clean", "what": "Normalise ingredient names to the nutrition table; drop duplicates; reject unknown cuisines"},
    {"step": "Normalise units", "what": "All nutrients per 100 g, quantities in grams, sodium in mg"},
    {"step": "Safety screen", "what": "Reject corpus text that mentions insulin or medication dosing (same rules as the input guard)"},
    {"step": "Licence screen", "what": "Keep only photos with CC BY / CC BY-SA / CC0 / public-domain licences and attribution"},
    {"step": "Tag", "what": "Cuisine tags, allergen and premium flags, data-class tags"},
    {"step": "Index", "what": "Demo: keyword match on cuisine tags. Production: embed and store in pgvector"},
    {"step": "Refresh", "what": "Re-run checks on every data change; nutrition and prices re-verified before GA"},
]


def _patterns() -> list[dict]:
    from .pipeline import RECIPE_PATTERNS
    return RECIPE_PATTERNS


def sizes() -> dict:
    return {"patterns": len(_patterns()), "nutrition": len(CARBS_PER_100G), "prices": len(SAMPLE_PRICE_PER_KG),
            "photos": len(library())}


def run_checks() -> list[dict]:
    from .models import _CUISINE_INGREDIENTS

    pats = _patterns()
    known_cuisines = set(_CUISINE_INGREDIENTS)
    checks = []

    def add(name, ok, detail, warn=False):
        checks.append({"check": name, "status": "pass" if ok else ("warn" if warn else "fail"), "detail": detail})

    missing = set(CARBS_PER_100G) ^ set(OTHER_PER_100G)
    add("Nutrition coverage", not missing, f"{len(CARBS_PER_100G)} ingredients have carbs, protein, fat, sodium and fiber"
        if not missing else f"missing nutrients for {sorted(missing)}")
    dupes = [i for i, n in Counter(p["idea"].lower() for p in pats).items() if n > 1]
    add("Duplicate patterns removed", not dupes, "no duplicates" if not dupes else f"duplicates: {dupes}")
    bad_cuisine = sorted({c for p in pats for c in p["cuisines"] if c not in known_cuisines})
    add("Cuisine tags valid", not bad_cuisine, f"{len(pats)} patterns, all tags known" if not bad_cuisine else f"unknown: {bad_cuisine}")
    unknown_ing = sorted({i for lst in _CUISINE_INGREDIENTS.values() for i in lst if i not in CARBS_PER_100G})
    add("Ingredient names normalised", not unknown_ing, "every cuisine ingredient maps to the nutrition table"
        if not unknown_ing else f"not in table: {unknown_ing}")
    unsafe = [p["idea"] for p in pats if check_request_text(p["idea"])]
    add("Safety screen (no dosing text)", not unsafe, "0 patterns mention dosing" if not unsafe else f"flagged: {unsafe}")
    lic_ok = all(ph["license"].startswith(("CC BY", "CC0", "Public domain")) and ph.get("artist") for ph in library())
    add("Photo licences and attribution", lic_ok and bool(library()), f"{len(library())} photos, all CC / public domain with attribution"
        if lic_ok else "a photo lacks an allowed licence or attribution")
    price_gap = sorted(set(CARBS_PER_100G) - set(SAMPLE_PRICE_PER_KG))
    add("Price table coverage", not price_gap, f"{len(SAMPLE_PRICE_PER_KG)} items; {PRICE_DISCLAIMER.split('.')[0].lower()}"
        if not price_gap else f"no price for {price_gap}", warn=True)
    add("Nutrition values verified", False, "approximate demo values - verify against USDA FoodData Central", warn=True)
    add("Retrieval recall evaluated", False, "no labelled queries yet (planned recall@3)")
    return checks


def summary() -> dict:
    c = run_checks()
    return {"passed": sum(x["status"] == "pass" for x in c), "total": len(c), "checks": c, "sizes": sizes(),
            "domain": DOMAIN, "pipeline": PIPELINE}
