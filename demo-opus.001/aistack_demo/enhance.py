"""Enhancement idea -> draft product requirement updates (PRD delta) against the current manifest.

Live: drafted by Claude (Anthropic SDK, structured output) when ANTHROPIC_API_KEY is set.
Offline: deterministic keyword rules. The response always says which drafted it.
"""
from __future__ import annotations

import json
import re

from .config import forced_offline, provider_key_present

PRD_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "requirements": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "text": {"type": "string"}, "kind": {"type": "string"}},
            "required": ["id", "text", "kind"], "additionalProperties": False}},
        "layer_changes": {"type": "array", "items": {"type": "object", "properties": {
            "layer": {"type": "string"}, "change": {"type": "string"}, "why": {"type": "string"}},
            "required": ["layer", "change", "why"], "additionalProperties": False}},
        "contract_changes": {"type": "array", "items": {"type": "object", "properties": {
            "contract": {"type": "string"}, "change": {"type": "string"}, "version": {"type": "string"}},
            "required": ["contract", "change", "version"], "additionalProperties": False}},
        "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "cost_impact": {"type": "string"},
    },
    "required": ["title", "summary", "requirements", "layer_changes", "contract_changes",
                 "acceptance_criteria", "risks", "cost_impact"],
    "additionalProperties": False,
}

RULES = [
    {"match": r"\b(cgm|glucose|dexcom|libre|blood sugar)\b",
     "req": ("Adapt each meal's carb target to recent CGM glucose readings and trend", "functional"),
     "layers": [("Tools and APIs", "Add CGM integration (Dexcom / Libre partner APIs) behind a typed Tool adapter",
                 "Readings come from a third-party device platform"),
                ("Identity", "Required (no longer optional); per-user OAuth consent to the CGM platform",
                 "Readings belong to a signed-in user"),
                ("Durable execution", "Level 2: background job to sync readings every 5-15 min",
                 "Sync must survive restarts and retry provider rate limits")],
     "contracts": [("aistack/GlucoseReading", "New: value_mg_dl (x-aistack-unit mg/dL), trend, measured_at; data class health", "1.0.0"),
                   ("aistack/RecipeRequest", "Add optional glucose_context", "1.5.0")],
     "criteria": ["Readings older than 15 minutes are ignored and the app falls back to the static carb target",
                  "Glucose values are never sent to the model provider unless the data-class policy allows `health`",
                  "Carb target changes are explained on the card (e.g. 'lowered because trending high')"],
     "risks": ["Health data: HIPAA / regional privacy review before launch; manifest data class becomes `health`",
               "Insulin dosing must stay out of scope - guard rules unchanged (R5)",
               "CGM partner API access and terms are not verified"],
     "cost": "Adds a fixed integration cost and background sync compute; no change to model cost per recipe."},
    {"match": r"\b(shopping list|grocery|groceries|cart|instacart|walmart|whole ?foods|order)\b",
     "req": ("Turn the recipe into a shopping list and send it to a grocery cart", "functional"),
     "layers": [("Tools and APIs", "Add a grocery partner tool (cart / product search) behind a typed adapter",
                 "Prices and availability come from the store, not sample tables"),
                ("Guardrails", "Require user confirmation before any cart write (side effects: write)",
                 "Placing items in a cart is an external side effect")],
     "contracts": [("aistack/ShoppingList", "New: items[name, quantity, unit, store_sku?, est_price]", "1.0.0")],
     "criteria": ["Every cart write needs an explicit user tap and carries an idempotency key",
                  "Prices shown are fetched within the last 24 h, with store and timestamp",
                  "Ingredients the user already has are excluded from the list"],
     "risks": ["Store API access, affiliate terms and price accuracy are not verified",
               "Prices vary by location - need the user's store or ZIP"],
     "cost": "Per-request partner API calls; possible affiliate revenue. Model cost unchanged."},
    {"match": r"\b(meal plan|weekly|week|plan my|7[- ]day)\b",
     "req": ("Generate a 7-day meal plan that meets daily carb, protein and sodium totals", "functional"),
     "layers": [("Model", "Same model; batch generation for the 21 meals",
                 "Offline generation tolerates delay; Batch API is 50% cheaper on list prices"),
                ("Orchestration", "Still none: one planner call plus per-meal pipeline runs",
                 "No agent loop needed for a fixed 7 x 3 grid")],
     "contracts": [("aistack/MealPlan", "New: days[meals[RecipeCard]], daily_totals", "1.0.0")],
     "criteria": ["Each day meets the daily carb budget within 10 g and the sodium limit",
                  "No recipe repeats more than twice in a week",
                  "Plan regenerates a single meal without changing the others"],
     "risks": ["21 model calls per plan - cost and latency need the batch path"],
     "cost": "About 21x one recipe's model cost per plan; ~50% less via Batch API (list price)."},
    {"match": r"\b(photo|image|picture|generate.*image)\b",
     "req": ("Show a generated photo of the exact recipe", "functional"),
     "layers": [("Image generation (new layer)", "Add an image model behind an ImageModel port; cache by recipe hash",
                 "Library photos are only similar dishes")],
     "contracts": [("aistack/RecipeImage", "New: url, prompt_hash, model, generated_at, is_generated=true", "1.0.0")],
     "criteria": ["Generated images are labelled as AI-generated on the card",
                  "The same recipe reuses its cached image",
                  "Image generation failure falls back to the library photo"],
     "risks": ["Image model choice and price are not in the catalog yet (unverified)",
               "Generated food can look unrealistic - needs a quality eval"],
     "cost": "Adds a per-image charge (unverified); caching keeps it to one image per unique recipe."},
    {"match": r"\b(remember|memory|history|preferences|favorite|favourite|past meals)\b",
     "req": ("Remember the user's liked recipes and preferences across sessions", "functional"),
     "layers": [("Memory", "Start with a user-profile table in Postgres; no memory vendor yet",
                 "Preferences and favourites are structured data, not conversational memory")],
     "contracts": [("aistack/UserPreferences", "New: liked_recipes, disliked_ingredients, default_goals", "1.0.0")],
     "criteria": ["Disliked ingredients are added to exclusions automatically",
                  "Users can view and delete everything stored about them"],
     "risks": ["Personal data retention policy needed"],
     "cost": "Negligible: one Postgres table."},
    {"match": r"\b(voice|speak|audio|alexa|talk)\b",
     "req": ("Let users ask for a recipe by voice and hear the steps read aloud", "functional"),
     "layers": [("Experience", "Add speech-to-text and text-to-speech adapters",
                 "Hands-free use while cooking")],
     "contracts": [("aistack/VoiceTurn", "New: audio_ref, transcript, locale", "1.0.0")],
     "criteria": ["Dosing questions asked by voice are blocked exactly like typed ones"],
     "risks": ["Speech vendor not selected; audio is personal data"],
     "cost": "Per-minute speech charges (vendor and price unverified)."},
    {"match": r"\b(spanish|hindi|language|translate|localis|localiz)\w*",
     "req": ("Support recipes and UI in additional languages", "functional"),
     "layers": [("Model", "Same model; locale passed in the request", "Modern models handle the target languages"),
                ("Evals", "Add a per-locale eval suite", "Quality must be measured per language")],
     "contracts": [("aistack/RecipeRequest", "Add optional locale (BCP 47)", "1.5.0")],
     "criteria": ["Each supported locale passes the same gates as English on its own eval suite"],
     "risks": ["Nutrition table ingredient names need translation mapping"],
     "cost": "No change per recipe; eval cost per added locale."},
]


def _next_ids(n: int, existing: int = 5) -> list[str]:
    return [f"R{existing + i + 1}" for i in range(n)]


def _summary(text: str, reqs: int, layers: int) -> str:
    plural = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"  # noqa: E731
    return f'Draft PRD updates for "{text.strip()}": {plural(reqs, "new requirement")} touching {plural(layers, "layer")}.'


def draft_offline(text: str) -> dict:
    hits = [r for r in RULES if re.search(r["match"], text, re.I)]
    if not hits:
        hits = [{"req": (text.strip().rstrip(".") or "New enhancement", "functional"),
                 "layers": [("Experience", "UI change to expose the enhancement", "Derived from your description"),
                            ("Model", "Prompt and contract update if the model must produce new fields",
                             "Only if the enhancement changes model output")],
                 "contracts": [("aistack/RecipeCard", "Add the fields this enhancement displays", "2.4.0")],
                 "criteria": ["The enhancement is covered by at least 5 new eval cases",
                              "Existing gates (schema, carbs within 5 g, dosing refusal) still pass"],
                 "risks": ["Scope needs a product owner's confirmation - no rule matched this description"],
                 "cost": "Unknown until the design is chosen."}]
    ids = _next_ids(len(hits))
    return {
        "title": "Enhancement: " + text.strip()[:70],
        "summary": _summary(text, len(hits), len({l[0] for h in hits for l in h["layers"]})),
        "requirements": [{"id": i, "text": h["req"][0], "kind": h["req"][1]} for i, h in zip(ids, hits)],
        "layer_changes": [{"layer": l, "change": c, "why": w} for h in hits for l, c, w in h["layers"]],
        "contract_changes": [{"contract": c, "change": ch, "version": v} for h in hits for c, ch, v in h["contracts"]],
        "acceptance_criteria": [c for h in hits for c in h["criteria"]],
        "risks": [r for h in hits for r in h["risks"]],
        "cost_impact": " ".join(h["cost"] for h in hits),
    }


def draft_live(text: str, manifest: dict, model_id: str = "claude-sonnet-5-5") -> dict:
    from .models import AnthropicModel

    system = ("You are a product architect. Given an app's Architecture Manifest and an enhancement idea, "
              "draft product requirement updates. Use requirement IDs continuing after the manifest's existing ones. "
              "Prefer the simplest architecture: add a layer only if the enhancement needs it. "
              "Never add medication or insulin dosing features. Mark unverified vendor facts as unverified.")
    user = f"MANIFEST_JSON: {json.dumps(manifest)}\n\nENHANCEMENT: {text}"
    mr = AnthropicModel(model_id, effort="medium").generate_json(system, user, PRD_SCHEMA)
    return json.loads(mr.text)


def draft(text: str, manifest: dict) -> dict:
    live = not forced_offline() and provider_key_present("anthropic")
    if live:
        try:
            return {"drafted_by": "Claude Sonnet 5.5 (live)", **draft_live(text, manifest)}
        except Exception as e:  # fall back so the demo never dead-ends
            return {"drafted_by": f"Offline rules (live call failed: {type(e).__name__})", **draft_offline(text)}
    return {"drafted_by": "Offline rules (no API key)", **draft_offline(text)}


def to_markdown(d: dict) -> str:
    lines = [f"## {d['title']}", "", d["summary"], "", "### New requirements",
             *[f"- **{r['id']}** ({r['kind']}): {r['text']}" for r in d["requirements"]],
             "", "### Architecture changes", "| Layer | Change | Why |", "| --- | --- | --- |",
             *[f"| {c['layer']} | {c['change']} | {c['why']} |" for c in d["layer_changes"]],
             "", "### Contract changes", "| Contract | Change | Version |", "| --- | --- | --- |",
             *[f"| {c['contract']} | {c['change']} | {c['version']} |" for c in d["contract_changes"]],
             "", "### Acceptance criteria", *[f"- [ ] {c}" for c in d["acceptance_criteria"]],
             "", "### Risks and open questions", *[f"- {r}" for r in d["risks"]],
             "", "### Cost impact", d["cost_impact"], "", f"_Drafted by: {d.get('drafted_by', '')}_"]
    return "\n".join(lines)
