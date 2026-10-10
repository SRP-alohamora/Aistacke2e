"""Three answers -> requirements profile (rule-based, deterministic)."""
from __future__ import annotations

import re

HEALTH = re.compile(r"\b(diabet\w*|glucose|insulin|blood sugar|cgm|health|medical|patient)\b", re.I)
RETRIEVAL = re.compile(r"\b(recipe|recipes|meal|meals|nutrition|knowledge|docs?|documents?|catalog|faq)\b", re.I)
ACTIONS = re.compile(r"\b(book|send|schedule|order|update|create ticket|email|purchase|pay)\b", re.I)
CONSUMER = re.compile(r"\b(person|people|consumer|user|athlete|individual|someone)\b", re.I)
INTERNAL = re.compile(r"\b(employee|staff|team|agent|analyst|internal)\b", re.I)
ACTIVE = re.compile(r"\b(active|workout|training|athlete|run|gym|exercise)\b", re.I)
QUICK = re.compile(r"\b(quick|fast|<=?\s*\d+\s*-?\s*min|\d+\s*-?\s*minute)\b", re.I)


def _field(value, source: str, confidence: str = "high", why: str = "") -> dict:
    return {"value": value, "source": source, "confidence": confidence, "why": why}


UX_HINTS = {
    "photo": re.compile(r"\b(picture|photo|image)\b", re.I),
    "recipe card": re.compile(r"\bcard\b", re.I),
    "tunable tiles": re.compile(r"\btiles?\b", re.I),
    "organic": re.compile(r"\borganic\b", re.I),
    "budget friendly": re.compile(r"\bbudget\b", re.I),
    "ingredients box": re.compile(r"\bingredients? available\b", re.I),
    "restrictions": re.compile(r"\brestrictions?\b", re.I),
}


def extract_profile(build: str, user: str, goal: str, guidance: str = "") -> dict:
    text = " ".join([build, user, goal])
    health = bool(HEALTH.search(text))
    retrieval = bool(RETRIEVAL.search(text))
    actions = bool(ACTIONS.search(text))

    if actions:
        template, conf = "tool-workflow", "medium"
    elif retrieval:
        template, conf = "rag", "high"
    else:
        template, conf = "simple-llm", "medium"

    audience = "internal" if INTERNAL.search(user) else "consumer" if CONSUMER.search(user) else "consumer"
    profile = {
        "template": _field(template, "inferred", conf,
                           "answers mention recipes/nutrition data to ground answers in" if template == "rag" else ""),
        "audience": _field(audience, "inferred", "high" if CONSUMER.search(user) or INTERNAL.search(user) else "low"),
        "data_sensitivity": _field("health_adjacent" if health else "standard", "inferred",
                                   "medium" if health else "low",
                                   "mentions diabetes; preferences are health-related" if health else ""),
        "activity_aware": _field(bool(ACTIVE.search(text)), "inferred", "high"),
        "latency_budget_ms": _field(8000, "template"),
        "region": _field("us", "template"),
        "quick_prep": _field(bool(QUICK.search(text)), "inferred", "high"),
    }
    if guidance.strip():
        hints = [k for k, rx in UX_HINTS.items() if rx.search(guidance)]
        profile["ux_guidance"] = _field(", ".join(hints) or "free text", "user", "high",
                                        "from your tips; shapes the generated app's screens")
    supported = template == "rag"
    return {
        "answers": {"build": build, "user": user, "goal": goal, "guidance": guidance},
        "fields": profile,
        "supported_in_demo": supported,
        "demo_note": None if supported else
        f"Template '{template}' is out of demo scope; the demo continues with the RAG template.",
        "follow_ups": follow_ups(profile),
    }


def follow_ups(profile: dict) -> list[dict]:
    """Only questions whose answer changes a layer selection or contract field."""
    qs = []
    if profile["data_sensitivity"]["value"] == "health_adjacent":
        qs.append({"id": "Q4", "text": "Will the app store glucose readings or connect to a CGM?",
                   "affects": ["policies.dataClasses", "layers.identity", "policies.regions"],
                   "default": False})
        qs.append({"id": "Q5", "text": "Should nutrition numbers come from a verified database?",
                   "affects": ["layers.nutrition_tool", "contracts.RecipeCard.carbs_g"],
                   "default": True})
    return qs
