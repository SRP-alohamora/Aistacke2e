"""Pick the closest real photo (Wikimedia Commons, CC-licensed) for a recipe by tag overlap."""
from __future__ import annotations

import json
from functools import lru_cache

from .config import STATIC


@lru_cache
def library() -> list[dict]:
    path = STATIC / "photos" / "photos.json"
    return json.loads(path.read_text()) if path.exists() else []


def choose_photo(ingredient_names: list[str], cuisines: list[str]) -> dict | None:
    wanted = set(ingredient_names) | {c.lower() for c in cuisines}
    best, best_score = None, -1.0
    for p in library():
        tags = set(p["tags"])
        # ingredients weigh more than cuisine labels
        score = 2 * len(tags & set(ingredient_names)) + len(tags & {c.lower() for c in cuisines})
        if ingredient_names and ingredient_names[0] in tags:  # main ingredient (protein) matters most
            score += 3
        if score > best_score:
            best, best_score = p, score
    if not best:
        return None
    return {"src": best["file"], "title": best["title"].removeprefix("File:").rsplit(".", 1)[0],
            "artist": best["artist"], "license": best["license"], "license_url": best["license_url"],
            "page": best["page"], "match_score": best_score, "matched": sorted(set(best["tags"]) & wanted)}
