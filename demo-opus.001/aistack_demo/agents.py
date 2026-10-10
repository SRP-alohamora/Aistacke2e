"""Agent registry: inventory of every agent and tool in Fusion Fuel, with role, skills and capabilities.

Only two entries are LLM-backed. The rest are deterministic tools; listing them makes the inventory
complete for review (data access, side effects, guardrails) without implying a multi-agent system.
"""
from __future__ import annotations

from .config import prices


def inventory(model_key: str) -> list[dict]:
    model = prices()["models"][model_key]
    return [
        {"id": "recipe-drafter", "name": "Recipe drafter", "kind": "LLM agent", "scope": "runtime",
         "model": model["label"],
         "role": "Drafts a fusion recipe as structured JSON from the request and retrieved patterns",
         "skills": ["Fusion recipe design", "Ingredient choice from the allowed list", "Follows nutrition goals"],
         "capabilities": ["Structured JSON output", "Respects exclusions and budget rules", "Single call, no tool use"],
         "side_effects": "none", "data": "Request incl. health-adjacent preferences (confidential)",
         "guardrails": ["Input guard runs first", "Schema validation", "Unknown ingredients dropped"]},
        {"id": "nutrition-calculator", "name": "Nutrition calculator", "kind": "Deterministic tool", "scope": "runtime",
         "model": None,
         "role": "Computes carbs, protein, fat, sodium and fiber; re-balances portions to targets",
         "skills": ["Carb re-balancing", "Protein / fat boosting for goals", "Goal checks"],
         "capabilities": ["Per-meal totals and % Daily Value", "Bounded portions (10-600 g)"],
         "side_effects": "none", "data": "Ingredient list", "guardrails": ["Carbs never come from the model"]},
        {"id": "safety-guard", "name": "Safety guard", "kind": "Rules", "scope": "runtime", "model": None,
         "role": "Blocks insulin and medication dosing questions before any model call",
         "skills": ["Dosing-intent detection (regex rules)"], "capabilities": ["Hard block with safe message"],
         "side_effects": "none", "data": "User note, exclusions, pantry text", "guardrails": ["Gate: 100% refusal"]},
        {"id": "recipe-retriever", "name": "Recipe retriever", "kind": "Retrieval tool", "scope": "runtime",
         "model": None, "role": "Finds fusion patterns that match the chosen cuisines",
         "skills": ["Cuisine matching (keyword stand-in for pgvector)"], "capabilities": ["Top-3 patterns"],
         "side_effects": "none", "data": "Curated internal corpus", "guardrails": ["Corpus is curated, not user-supplied"]},
        {"id": "budget-advisor", "name": "Budget advisor", "kind": "Deterministic tool", "scope": "runtime",
         "model": None, "role": "Compares Walmart vs Whole Foods sample prices and suggests cheaper swaps",
         "skills": ["Store cost estimate", "Same-role substitutions"],
         "capabilities": ["Savings per serving", "Respects restrictions"], "side_effects": "none (links only)",
         "data": "Ingredient list", "guardrails": ["Sample prices labelled as not live quotes"]},
        {"id": "photo-matcher", "name": "Photo matcher", "kind": "Deterministic tool", "scope": "runtime",
         "model": None, "role": "Picks the closest licensed photo of a similar dish",
         "skills": ["Tag matching on main ingredient and cuisine"], "capabilities": ["Attribution and licence shown"],
         "side_effects": "none", "data": "Ingredient names", "guardrails": ["Labelled 'similar dish', not generated"]},
        {"id": "requirements-drafter", "name": "Requirements drafter", "kind": "LLM agent (rules offline)",
         "scope": "build-time", "model": "Claude Sonnet 5.5 when a key is set; keyword rules otherwise",
         "role": "Drafts product requirement updates for an enhancement against the manifest",
         "skills": ["Requirement writing", "Layer and contract impact analysis", "Acceptance criteria"],
         "capabilities": ["Structured PRD delta", "Copy as Markdown"], "side_effects": "none",
         "data": "Manifest and enhancement text", "guardrails": ["Never adds dosing features", "Shows who drafted it"]},
        {"id": "eval-runner", "name": "Eval runner", "kind": "Deterministic tool", "scope": "build-time",
         "model": "Calls the model under test", "role": "Runs the 10-case suite and writes evidence for verdicts",
         "skills": ["Gate scoring", "Evidence records"], "capabilities": ["Simulated vs measured stamping"],
         "side_effects": "writes evidence files", "data": "Eval cases", "guardrails": ["Never mixes simulated and measured"]},
    ]
