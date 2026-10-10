# aistack: managed - Input -> Retrieve -> Model -> Decision -> Action -> Validate -> Result.
"""Fusion Fuel recipe pipeline (RAG template).

Retrieval is a small keyword-matched pattern corpus that stands in for pgvector in this demo.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field

from pydantic import ValidationError

from .contracts import (DRAFT_SCHEMA, BlockedResponse, Ingredient, RecipeCard,
                        RecipeRequest)
from .guards import BLOCK_MESSAGE, check_request_text
from .goals import GOALS, evaluate, exclusions_for_goals
from .restrictions import exclusions_for, labels_for
from .models import ModelError, ModelResult
from .nutrition import (CARBS_PER_100G, PREMIUM, TOLERANCE_G, adjust_to_target, boost_for_goals, carbs_for,
                        meal_nutrients,
                        normalise, total_carbs)

RECIPE_PATTERNS = [
    {"cuisines": ["korean", "mexican"], "idea": "Kimchi and black-bean tacos with gochujang crema"},
    {"cuisines": ["japanese", "italian"], "idea": "Miso-butter soba tossed like aglio e olio"},
    {"cuisines": ["indian", "mexican"], "idea": "Paneer tikka burrito bowl with chickpeas"},
    {"cuisines": ["thai", "american"], "idea": "Peanut-lime turkey lettuce cups with sweet potato"},
    {"cuisines": ["mediterranean", "korean"], "idea": "Gochujang chickpea pita with cucumber kimchi"},
    {"cuisines": ["japanese", "mexican"], "idea": "Salmon teriyaki tostadas with edamame salsa"},
    {"cuisines": ["indian", "italian"], "idea": "Spinach-paneer quinoa 'risotto' with ginger"},
    {"cuisines": ["thai", "mediterranean"], "idea": "Coconut-lime shrimp over herbed quinoa"},
    {"cuisines": ["korean", "american"], "idea": "Bulgogi-style turkey with roasted sweet potato"},
    {"cuisines": ["mexican", "mediterranean"], "idea": "Black-bean falafel tacos with feta salsa"},
]

ACTIVITY_GUIDANCE = {
    "pre_workout": "Favour easily digested carbohydrate and moderate protein; keep fat and fibre lower.",
    "post_workout": "Pair carbohydrate with 25-35 g protein for recovery.",
    "rest_day": "Favour fibre-rich carbohydrate and vegetables.",
}

SYSTEM_PROMPT = (
    "You design quick fusion recipes for a physically active person managing diabetes.\n"
    "Rules:\n"
    "1. Use ONLY ingredient names copied exactly from the ALLOWED INGREDIENTS list.\n"
    "2. Give each ingredient a quantity in grams.\n"
    "3. Total prep time must not exceed the request's max_prep_minutes.\n"
    "4. Never use an ingredient that matches any exclusion.\n"
    "5. Aim for total carbohydrate close to carb_target_g. A deterministic nutrition tool "
    "recomputes and adjusts carbs afterwards, so do not state carb numbers.\n"
    "6. Give 2 to 10 short steps and at least 3 ingredients.\n"
    "7. Never give medication or insulin advice.\n"
    "8. When available_ingredients are given, build the recipe around them where they fit.\n"
    "9. When budget_friendly is true, avoid premium items: " + ", ".join(sorted(PREMIUM)) + ".\n"
    "10. Follow nutrition_goals: high_protein >= 35 g protein; keto <= 25 g carbs with >= 30 g protein and "
    ">= 30 g fat; high_fiber >= 10 g fiber; low_sodium <= 600 mg sodium.\n\n"
    "ALLOWED INGREDIENTS (grams of carbohydrate per 100 g):\n"
    + "\n".join(f"- {name}: {c}" for name, c in sorted(CARBS_PER_100G.items()))
)


@dataclass
class RunResult:
    status: str  # ok | blocked | invalid | error
    card: dict | None = None
    blocked: dict | None = None
    error: dict | None = None
    draft_carbs_g: float | None = None
    adjusted_by_tool: bool = False
    unknown_ingredients: list[str] = field(default_factory=list)
    pantry_unknown: list[str] = field(default_factory=list)
    exclusion_violations: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    retrieved: list[str] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def retrieve(cuisines: list[str], k: int = 3) -> list[str]:
    wanted = {c.lower() for c in cuisines}
    scored = sorted(RECIPE_PATTERNS, key=lambda p: -len(wanted & set(p["cuisines"])))
    return [p["idea"] for p in scored[:k] if wanted & set(p["cuisines"])]


def all_exclusions(req: RecipeRequest) -> list[str]:
    return list(dict.fromkeys([*req.exclusions, *exclusions_for(list(req.restrictions)),
                               *exclusions_for_goals(list(req.nutrition_goals))]))


def _minimum(goals: list[str], field: str) -> float | None:
    vals = [t for g in goals for f, op, t in GOALS[g]["checks"] if f == field and op == ">="]
    return max(vals) if vals else None


def build_user_message(req: RecipeRequest, ideas: list[str]) -> str:
    payload = req.model_dump(mode="json", exclude={"request_id", "note"})
    payload["exclusions"] = all_exclusions(req)
    return (
        f"Activity guidance: {ACTIVITY_GUIDANCE[req.activity.value]}\n"
        f"Inspiration from the recipe corpus: {'; '.join(ideas) or 'none'}\n"
        f"REQUEST_JSON: {json.dumps(payload)}"
    )


def _timed(log: list[dict], name: str, params: dict, fn, *args):
    """Invoke a tool and record name, params and duration (tool invocation log)."""
    t0 = time.perf_counter()
    out = fn(*args)
    log.append({"tool": name, "params": {k: (v if len(str(v)) <= 80 else str(v)[:77] + "...") for k, v in params.items()},
                "ms": round((time.perf_counter() - t0) * 1000, 2), "status": "ok"})
    return out


def run_recipe(req: RecipeRequest, model) -> RunResult:
    calls: list[dict] = []
    # Input guard (R5): dosing questions never reach the model.
    reason = _timed(calls, "safety.check_request_text", {"texts": 1 + len(req.exclusions) + len(req.available_ingredients)},
                    check_request_text, req.note, *req.exclusions, *req.available_ingredients)
    if reason:
        return RunResult(status="blocked", tool_calls=calls,
                         blocked=BlockedResponse(reason=reason, message=BLOCK_MESSAGE).model_dump())

    ideas = _timed(calls, "retrieval.retrieve", {"cuisines": req.cuisines, "k": 3}, retrieve, req.cuisines)
    try:
        mr: ModelResult = model.generate_json(SYSTEM_PROMPT, build_user_message(req, ideas), DRAFT_SCHEMA)
    except ModelError as e:
        return RunResult(status="error", error={"code": e.code, "retryable": e.retryable,
                                                "detail": e.detail}, retrieved=ideas)
    usage = {"input_tokens": mr.input_tokens, "output_tokens": mr.output_tokens,
             "cache_read_tokens": mr.cache_read_tokens, "cache_write_tokens": mr.cache_write_tokens,
             "latency_ms": mr.latency_ms, "model": mr.model, "provider": mr.provider,
             "simulated": mr.simulated, "mapping_losses": mr.mapping_losses}
    try:
        draft = json.loads(mr.text)
    except json.JSONDecodeError:
        return RunResult(status="invalid", validation_errors=["model output is not JSON"],
                         retrieved=ideas, usage=usage)

    items: list[tuple[str, float]] = []
    unknown: list[str] = []
    for ing in draft.get("ingredients", []):
        key = normalise(str(ing.get("name", "")))
        grams = float(ing.get("grams", 0) or 0)
        if key and grams > 0:
            items.append((key, grams))
        else:
            unknown.append(str(ing.get("name", "")))

    draft_carbs = total_carbs(items) if items else None
    # Decision: within target? Action: adjust with the deterministic tool.
    excluded = all_exclusions(req)
    goals = list(req.nutrition_goals)
    boosted, boost_changed = _timed(calls, "nutrition.boost_for_goals",
                                    {"min_protein": _minimum(goals, "protein_g"), "min_fat": _minimum(goals, "fat_g")},
                                    boost_for_goals, items, _minimum(goals, "protein_g"), _minimum(goals, "fat_g"),
                                    excluded) if items else (items, False)
    adjusted_items, changed = _timed(calls, "nutrition.adjust_to_target", {"target_g": req.carb_target_g,
                                     "items": len(boosted)}, adjust_to_target, boosted,
                                     req.carb_target_g) if boosted else (boosted, False)
    changed = changed or boost_changed
    violations = [n for n, _ in adjusted_items if any(e.lower() in n for e in excluded)]

    pantry = {k for k in (normalise(a) for a in req.available_ingredients) if k}
    pantry_unknown = [a for a in req.available_ingredients if not normalise(a)]
    tags = (["organic"] if req.organic else []) + (["budget-friendly"] if req.budget_friendly else []) \
        + labels_for(list(req.restrictions))
    if req.budget_friendly and any(n in PREMIUM for n, _ in adjusted_items):
        tags = [t for t in tags if t != "budget-friendly"]
        violations += [f"{n} (premium)" for n, _ in adjusted_items if n in PREMIUM]

    result = RunResult(status="ok", draft_carbs_g=draft_carbs, adjusted_by_tool=changed,
                       unknown_ingredients=unknown, pantry_unknown=pantry_unknown,
                       exclusion_violations=violations, retrieved=ideas, usage=usage, tool_calls=calls)
    try:
        card = RecipeCard(
            title=str(draft.get("title", ""))[:80],
            prep_minutes=int(draft.get("prep_minutes", 0)),
            ingredients=[Ingredient(name=n, grams=g, carbs_g=carbs_for(n, g)) for n, g in adjusted_items],
            steps=[str(s) for s in draft.get("steps", [])],
            carbs_g=total_carbs(adjusted_items),
            carb_target_g=req.carb_target_g,
            nutrients=_timed(calls, "nutrition.meal_nutrients", {"items": len(adjusted_items)}, meal_nutrients,
                             adjusted_items) if adjusted_items else None,
            goals=evaluate(goals, meal_nutrients(adjusted_items)) if adjusted_items else [],
            tags=tags,
            pantry_used=sorted(n for n, _ in adjusted_items if n in pantry),
        )
        if card.prep_minutes > req.max_prep_minutes:
            result.validation_errors.append(
                f"prep_minutes {card.prep_minutes} exceeds max {req.max_prep_minutes}")
        result.card = card.model_dump()
    except ValidationError as e:
        result.status = "invalid"
        result.validation_errors = [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
    return result


def within_tolerance(card: dict | None) -> bool:
    return bool(card) and abs(card["carbs_g"] - card["carb_target_g"]) <= TOLERANCE_G
