# aistack: managed - deterministic nutrition tool.
"""Carbohydrate lookup and adjustment.

Values are APPROXIMATE grams of total carbohydrate per 100 g (cooked where noted),
rounded from typical published nutrition tables, for demo purposes only.
A production build replaces this table with a verified source such as
USDA FoodData Central. Not for medical use.
"""
from __future__ import annotations

CARBS_PER_100G: dict[str, float] = {
    # grains, breads, noodles
    "white rice (cooked)": 28, "brown rice (cooked)": 23, "quinoa (cooked)": 21,
    "corn tortilla": 45, "whole wheat tortilla": 46, "naan": 50, "whole wheat pita": 55,
    "soba noodles (cooked)": 21, "rice noodles (cooked)": 25, "udon noodles (cooked)": 21,
    "rolled oats (dry)": 66, "whole wheat bread": 41,
    # legumes and starchy veg
    "black beans (cooked)": 24, "chickpeas (cooked)": 27, "lentils (cooked)": 20,
    "edamame": 9, "sweet potato (baked)": 21, "potato (boiled)": 20, "corn kernels": 19,
    # fruit
    "banana": 23, "mango": 15, "pineapple": 13, "apple": 14, "avocado": 9, "lime juice": 8,
    # vegetables
    "tomato": 4, "onion": 9, "bell pepper": 6, "kimchi": 2, "cabbage": 6, "spinach": 4,
    "broccoli": 7, "carrot": 10, "cucumber": 4, "mushroom": 3, "zucchini": 3,
    "cilantro": 4, "ginger": 18, "garlic": 33, "scallion": 7,
    # protein and dairy
    "chicken breast": 0, "salmon": 0, "shrimp": 1, "eggs": 1, "ground turkey": 0,
    "lean beef": 0, "firm tofu": 3, "paneer": 3, "greek yogurt (plain)": 4,
    "cheddar": 1, "feta": 4,
    # sauces, fats, extras
    "coconut milk": 6, "peanuts": 16, "cashews": 30, "sesame seeds": 23, "olive oil": 0,
    "soy sauce": 5, "gochujang": 40, "salsa": 7, "hummus": 14, "peanut butter": 20,
    "honey": 82,
}

# Approximate (protein g, fat g, sodium mg, fiber g) per 100 g, same basis as CARBS_PER_100G.
# Rounded typical values for the demo; replace with a verified source (e.g. USDA FoodData Central).
OTHER_PER_100G: dict[str, tuple[float, float, float, float]] = {
    "white rice (cooked)": (2.7, 0.3, 1, 0.4), "brown rice (cooked)": (2.6, 0.9, 5, 1.8),
    "quinoa (cooked)": (4.4, 1.9, 7, 2.8), "corn tortilla": (5.7, 2.9, 45, 6.3),
    "whole wheat tortilla": (9, 7, 600, 7), "naan": (9, 5, 450, 2), "whole wheat pita": (10, 2.6, 530, 7.4),
    "soba noodles (cooked)": (5, 0.1, 60, 1.5), "rice noodles (cooked)": (1.8, 0.2, 19, 1),
    "udon noodles (cooked)": (2.6, 0.3, 160, 1.2), "rolled oats (dry)": (13, 7, 2, 10),
    "whole wheat bread": (13, 3.4, 450, 7), "black beans (cooked)": (8.9, 0.5, 140, 8.7),
    "chickpeas (cooked)": (8.9, 2.6, 24, 7.6), "lentils (cooked)": (9, 0.4, 2, 7.9), "edamame": (11, 5, 6, 5),
    "sweet potato (baked)": (2, 0.2, 36, 3.3), "potato (boiled)": (1.9, 0.1, 5, 1.8),
    "corn kernels": (3.3, 1.4, 15, 2), "banana": (1.1, 0.3, 1, 2.6), "mango": (0.8, 0.4, 1, 1.6),
    "pineapple": (0.5, 0.1, 1, 1.4), "apple": (0.3, 0.2, 1, 2.4), "avocado": (2, 15, 7, 6.7),
    "lime juice": (0.4, 0.1, 2, 0.4), "tomato": (0.9, 0.2, 5, 1.2), "onion": (1.1, 0.1, 4, 1.7),
    "bell pepper": (1, 0.3, 4, 2), "kimchi": (1.1, 0.5, 500, 1.6), "cabbage": (1.3, 0.1, 18, 2.5),
    "spinach": (2.9, 0.4, 79, 2.2), "broccoli": (2.8, 0.4, 33, 2.6), "carrot": (0.9, 0.2, 69, 2.8),
    "cucumber": (0.7, 0.1, 2, 0.5), "mushroom": (3.1, 0.3, 5, 1), "zucchini": (1.2, 0.3, 8, 1),
    "cilantro": (2.1, 0.5, 46, 2.8), "ginger": (1.8, 0.8, 13, 2), "garlic": (6.4, 0.5, 17, 2.1),
    "scallion": (1.8, 0.2, 16, 2.6), "chicken breast": (31, 3.6, 74, 0), "salmon": (22, 12, 61, 0),
    "shrimp": (24, 0.3, 111, 0), "eggs": (12.6, 9.5, 124, 0), "ground turkey": (27, 10, 85, 0),
    "lean beef": (26, 10, 72, 0), "firm tofu": (17, 8.7, 14, 2.3), "paneer": (18, 20, 30, 0),
    "greek yogurt (plain)": (10, 0.4, 36, 0), "cheddar": (25, 33, 620, 0), "feta": (14, 21, 900, 0),
    "coconut milk": (2.3, 21, 15, 2.2), "peanuts": (26, 49, 18, 8.5), "cashews": (18, 44, 12, 3.3),
    "sesame seeds": (18, 50, 11, 12), "olive oil": (0, 100, 2, 0), "soy sauce": (8, 0.1, 5500, 0.8),
    "gochujang": (4, 1.5, 2500, 2), "salsa": (1.5, 0.2, 430, 1.9), "hummus": (7.9, 9.6, 380, 6),
    "peanut butter": (25, 50, 430, 6), "honey": (0.3, 0, 4, 0.2),
}

# FDA Daily Values (2,000 kcal reference diet).
DAILY_VALUE = {"carbs_g": 275, "protein_g": 50, "fat_g": 78, "sodium_mg": 2300, "fiber_g": 28}

TOLERANCE_G = 5.0

# Typically higher-priced items, avoided when budget_friendly is set. Qualitative, not price data.
PREMIUM = {"salmon", "shrimp", "cashews", "lean beef", "paneer", "feta", "avocado", "pineapple"}


def normalise(name: str) -> str | None:
    """Map a model-supplied name to a table key, or None if unknown."""
    key = name.strip().lower()
    if not key:
        return None
    if key in CARBS_PER_100G:
        return key
    candidates = [key, key.rstrip("s"), key[:-2] if key.endswith("es") else key]
    for cand in candidates:
        for known in CARBS_PER_100G:
            if cand == known.split(" (")[0]:
                return known
    # loose match for user-typed pantry items, e.g. "chicken" -> "chicken breast"
    for known in CARBS_PER_100G:
        base = known.split(" (")[0]
        if len(key) >= 4 and (base.startswith(key.rstrip("s")) or key in base.split()):
            return known
    return None


def carbs_for(name: str, grams: float) -> float:
    return round(CARBS_PER_100G[name] * grams / 100.0, 1)


def total_carbs(items: list[tuple[str, float]]) -> float:
    return round(sum(carbs_for(n, g) for n, g in items), 1)


def adjust_to_target(items: list[tuple[str, float]], target_g: float,
                     tolerance_g: float = TOLERANCE_G) -> tuple[list[tuple[str, float]], bool]:
    """Scale the most carb-dense ingredients until total carbs are within tolerance.

    Returns (adjusted items, whether any change was made). Deterministic.
    """
    items = [(n, float(g)) for n, g in items]
    changed = False
    for _ in range(3):
        total = total_carbs(items)
        gap = target_g - total
        if abs(gap) <= tolerance_g:
            break
        ranked = sorted(range(len(items)), key=lambda i: CARBS_PER_100G[items[i][0]], reverse=True)
        for idx in ranked:
            name, grams = items[idx]
            density = CARBS_PER_100G[name]
            if density < 5:
                continue
            new_grams = max(10.0, min(600.0, grams + gap / (density / 100.0)))
            if abs(new_grams - grams) >= 1:
                items[idx] = (name, round(new_grams))
                changed = True
                break
        else:
            break
    return items, changed


def meal_nutrients(items: list[tuple[str, float]]) -> dict:
    """Totals per meal plus % Daily Value. Approximate."""
    carbs = total_carbs(items)
    protein = fat = sodium = fiber = 0.0
    for name, grams in items:
        p, f, na, fi = OTHER_PER_100G.get(name, (0, 0, 0, 0))
        protein += p * grams / 100
        fat += f * grams / 100
        sodium += na * grams / 100
        fiber += fi * grams / 100
    totals = {"carbs_g": carbs, "protein_g": round(protein, 1), "fat_g": round(fat, 1),
              "sodium_mg": round(sodium), "fiber_g": round(fiber, 1)}
    return {**totals,
            "calories_kcal": round(4 * carbs + 4 * protein + 9 * fat),
            "pct_daily_value": {k: round(100 * v / DAILY_VALUE[k]) for k, v in totals.items()}}


def boost_for_goals(items: list[tuple[str, float]], min_protein: float | None, min_fat: float | None,
                    excluded: list[str]) -> tuple[list[tuple[str, float]], bool]:
    """Scale protein / fat sources up (deterministically) until per-meal minimums are met."""
    items = [(n, float(g)) for n, g in items]
    changed = False

    def total(idx: int) -> float:
        return sum(OTHER_PER_100G[n][idx] * g / 100 for n, g in items)

    for idx, minimum, density_floor, cap in ((0, min_protein, 10, 250.0), (1, min_fat, 10, 120.0)):
        if not minimum or total(idx) >= minimum:
            continue
        ranked = sorted(range(len(items)), key=lambda i: OTHER_PER_100G[items[i][0]][idx], reverse=True)
        for i in ranked:
            name, grams = items[i]
            dens = OTHER_PER_100G[name][idx]
            if dens < density_floor:
                break
            limit = 25.0 if name == "olive oil" else cap
            need = (minimum - total(idx)) / (dens / 100)
            new = min(limit, grams + need)
            if new > grams + 0.5:
                items[i] = (name, round(new))
                changed = True
            if total(idx) >= minimum:
                break
        if idx == 1 and total(1) < minimum and not any(e in "olive oil" for e in excluded) \
                and all(n != "olive oil" for n, _ in items):
            items.append(("olive oil", round(min(25.0, minimum - total(1)))))
            changed = True
    return items, changed
