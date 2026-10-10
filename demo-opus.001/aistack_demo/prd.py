"""Draft a short product requirements document from the onboarding answers (deterministic)."""
from __future__ import annotations

from .profile import extract_profile
from .recommender import REQUIREMENTS


def draft(build: str, user: str, goal: str, guidance: str = "") -> dict:
    prof = extract_profile(build, user, goal, guidance)
    f = prof["fields"]
    health = f["data_sensitivity"]["value"] == "health_adjacent"
    ux = f.get("ux_guidance", {}).get("value", "")
    sections = [
        ("Product", build.strip().rstrip(".")),
        ("Problem statement",
         f"{user.strip().rstrip('.')} needs meals that fit their goals without hours of planning. "
         "Generic recipe apps ignore carbohydrate targets, activity timing and dietary restrictions, "
         "and chat assistants may invent nutrition numbers." if health else
         f"{user.strip().rstrip('.')} lacks a quick, reliable way to {goal.strip().rstrip('.').lower()}."),
        ("Target customer", f"{user.strip().rstrip('.')} ({f['audience']['value']} use"
         + (", health-adjacent data" if health else "") + ")."),
        ("Goal", goal.strip().rstrip(".") + "."),
        ("Job to be done", "When I plan a meal around my training, I want a quick fusion recipe that fits my carb "
         "target and restrictions, so I can eat well without calculating nutrition myself." if health else
         f"When I need to {goal.strip().rstrip('.').lower()}, I want it done quickly and reliably."),
        ("MVP scope", "\n".join([
            "- Recipe with a photo and a recipe card (ingredients, steps, prep time)",
            "- Tunable tiles: organic, budget friendly, nutrition goals (balanced, high protein, keto, high fiber, low sodium)",
            "- \"Enter ingredients available\" box to build recipes around what you have",
            "- Add health conditions and restrictions (gluten-free, dairy-free, nut allergy, vegan, ...)",
            "- Nutrients per meal with % Daily Value; carbs computed by a nutrition tool, never by the model",
            "- Store price links and budget swaps (sample prices in the MVP)",
        ])),
        ("Out of scope (MVP)", "Insulin or medication dosing advice · storing glucose readings · meal plans · "
         "live store prices · native mobile apps"),
        ("Requirements", "\n".join(f"- {r['id']}: {r['text']}" for r in REQUIREMENTS)),
        ("Success metrics", "\n".join([
            "- 95% of recipes land within ±5 g of the carb target",
            "- 100% of dosing questions blocked",
            "- Cost per successful recipe tracked and under budget",
            "- Week-4 retention of active users ≥ 20%",
        ])),
        ("Constraints and safety", "Not medical advice; disclaimer on every recipe. Health-related fields are tagged "
         "and kept out of logs. US region." if health else "Standard privacy and security baseline."),
    ]
    if guidance.strip():
        sections.append(("Experience guidance (demo)", guidance.strip()
                         + (f"\nRecognised: {ux}." if ux and ux != "free text" else "")))
    text = "\n\n".join(f"{t.upper()}\n{b}" for t, b in sections)
    return {"title": f"PRD - {build.strip().rstrip('.')}", "sections": [{"title": t, "body": b} for t, b in sections],
            "text": text, "template": f["template"]["value"]}
