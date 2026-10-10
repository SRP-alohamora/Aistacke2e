# aistack: managed - rule-based guard for declared safety requirement R5.
"""Blocks medication and insulin dosing requests before any model call."""
from __future__ import annotations

import re

_DOSING = re.compile(
    r"\b(insulin|bolus|basal|units? of|dose|dosage|dosing|metformin|medication|"
    r"glp-?1|sulfonylurea|how much .{0,20}(take|inject))\b",
    re.IGNORECASE,
)

BLOCK_MESSAGE = (
    "I can't help with insulin or medication dosing. Please ask your diabetes care team. "
    "I can still suggest a recipe that fits your carbohydrate target."
)


def check_request_text(*texts: str) -> str | None:
    """Return a block reason if any text asks about dosing, else None."""
    for text in texts:
        if text and _DOSING.search(text):
            return "medication_dosing"
    return None
