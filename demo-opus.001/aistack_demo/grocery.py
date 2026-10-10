"""Shopping estimate: Whole Foods vs Walmart.

PRICES ARE SAMPLE ESTIMATES FOR THE DEMO (USD per kg as purchased), not live store quotes.
Prices vary by location and date; links open the store's own search page.
"""
from __future__ import annotations

from urllib.parse import quote, quote_plus

DISCLAIMER = "Sample prices for the demo, not live store quotes. Check the store for current prices."

# (Whole Foods, Walmart) USD/kg - illustrative.
SAMPLE_PRICE_PER_KG: dict[str, tuple[float, float]] = {
    "white rice (cooked)": (2.0, 1.0), "brown rice (cooked)": (2.2, 1.1), "quinoa (cooked)": (5.5, 3.3),
    "corn tortilla": (6.5, 3.3), "whole wheat tortilla": (8.0, 4.4), "naan": (11.0, 6.6),
    "whole wheat pita": (8.8, 4.8), "soba noodles (cooked)": (6.6, 4.0), "rice noodles (cooked)": (4.4, 2.6),
    "udon noodles (cooked)": (6.6, 4.4), "rolled oats (dry)": (5.5, 2.9), "whole wheat bread": (8.8, 4.0),
    "black beans (cooked)": (4.4, 2.2), "chickpeas (cooked)": (4.4, 2.2), "lentils (cooked)": (3.3, 1.8),
    "edamame": (8.8, 5.5), "sweet potato (baked)": (4.4, 2.6), "potato (boiled)": (3.3, 1.8),
    "corn kernels": (5.5, 3.0), "banana": (2.2, 1.2), "mango": (6.6, 4.0), "pineapple": (6.6, 3.3),
    "apple": (5.5, 3.5), "avocado": (11.0, 6.6), "lime juice": (8.8, 5.5), "tomato": (6.6, 4.4),
    "onion": (3.3, 2.2), "bell pepper": (8.8, 5.5), "kimchi": (17.6, 11.0), "cabbage": (3.3, 2.0),
    "spinach": (17.6, 8.8), "broccoli": (8.8, 5.5), "carrot": (3.3, 2.2), "cucumber": (5.5, 3.3),
    "mushroom": (13.2, 8.8), "zucchini": (6.6, 4.4), "cilantro": (22.0, 11.0), "ginger": (13.2, 8.8),
    "garlic": (17.6, 11.0), "scallion": (13.2, 8.8), "chicken breast": (15.4, 8.8), "salmon": (30.8, 19.8),
    "shrimp": (26.4, 15.4), "eggs": (8.8, 5.5), "ground turkey": (15.4, 9.9), "lean beef": (19.8, 13.2),
    "firm tofu": (6.6, 4.4), "paneer": (22.0, 17.6), "greek yogurt (plain)": (8.8, 5.5),
    "cheddar": (17.6, 11.0), "feta": (22.0, 15.4), "coconut milk": (6.6, 4.4), "peanuts": (11.0, 6.6),
    "cashews": (26.4, 17.6), "sesame seeds": (17.6, 11.0), "olive oil": (17.6, 9.9), "soy sauce": (8.8, 4.4),
    "gochujang": (17.6, 13.2), "salsa": (8.8, 4.4), "hummus": (13.2, 8.8), "peanut butter": (11.0, 5.5),
    "honey": (17.6, 11.0),
}
DEFAULT_PRICE = (8.0, 5.0)


def _search_term(name: str) -> str:
    return name.split(" (")[0]


def wholefoods_url(name: str) -> str:
    return f"https://www.wholefoodsmarket.com/search?text={quote(_search_term(name))}"


def walmart_url(name: str) -> str:
    return f"https://www.walmart.com/search?q={quote_plus(_search_term(name))}"


def shopping_estimate(ingredients: list[dict]) -> dict:
    items = []
    for ing in ingredients:
        wf_kg, wm_kg = SAMPLE_PRICE_PER_KG.get(ing["name"], DEFAULT_PRICE)
        kg = ing["grams"] / 1000
        items.append({
            "name": ing["name"],
            "wholefoods": {"cost": round(kg * wf_kg, 2), "url": wholefoods_url(ing["name"])},
            "walmart": {"cost": round(kg * wm_kg, 2), "url": walmart_url(ing["name"])},
        })
    wf = round(sum(i["wholefoods"]["cost"] for i in items), 2)
    wm = round(sum(i["walmart"]["cost"] for i in items), 2)
    featured = max(items, key=lambda i: i["wholefoods"]["cost"])["name"] if items else None
    return {"items": items, "featured": featured,
            "totals": {"wholefoods": wf, "walmart": wm, "savings": round(wf - wm, 2),
                       "savings_pct": round(100 * (wf - wm) / wf) if wf else 0},
            "disclaimer": DISCLAIMER}


# Same-role substitutes considered for budget options (first cheaper, allowed one wins).
SUBSTITUTES: dict[str, list[str]] = {
    "salmon": ["chicken breast", "eggs", "firm tofu"], "shrimp": ["eggs", "chicken breast", "firm tofu"],
    "lean beef": ["ground turkey", "black beans (cooked)"], "ground turkey": ["chicken breast", "lentils (cooked)"],
    "chicken breast": ["eggs", "firm tofu", "lentils (cooked)"], "paneer": ["firm tofu", "eggs"],
    "firm tofu": ["eggs", "lentils (cooked)"], "eggs": ["lentils (cooked)"],
    "quinoa (cooked)": ["brown rice (cooked)", "white rice (cooked)"], "brown rice (cooked)": ["white rice (cooked)"],
    "naan": ["whole wheat tortilla", "corn tortilla"], "whole wheat pita": ["corn tortilla"],
    "corn tortilla": ["white rice (cooked)"], "soba noodles (cooked)": ["rice noodles (cooked)"],
    "udon noodles (cooked)": ["rice noodles (cooked)"], "edamame": ["black beans (cooked)", "chickpeas (cooked)"],
    "spinach": ["cabbage"], "kimchi": ["cabbage"], "cilantro": ["scallion"], "mushroom": ["zucchini"],
    "avocado": ["cucumber"], "cashews": ["peanuts"], "sesame seeds": ["peanuts"], "feta": ["greek yogurt (plain)"],
    "cheddar": ["greek yogurt (plain)"], "pineapple": ["banana"], "mango": ["banana"], "gochujang": ["salsa"],
    "bell pepper": ["carrot"], "broccoli": ["cabbage"], "sweet potato (baked)": ["potato (boiled)"],
}


def budget_options(ingredients: list[dict], excluded: set[str]) -> list[dict]:
    """Cheaper same-role swaps, priced at Walmart sample prices. Suggestions only - carbs need re-checking."""
    from .nutrition import CARBS_PER_100G

    present = {i["name"] for i in ingredients}
    taken: set[str] = set()
    options = []
    for ing in ingredients:
        name, kg = ing["name"], ing["grams"] / 1000
        cur = SAMPLE_PRICE_PER_KG.get(name, DEFAULT_PRICE)[1]
        for alt in SUBSTITUTES.get(name, []):
            if alt in present or alt in taken or any(e in alt for e in excluded):
                continue
            alt_price = SAMPLE_PRICE_PER_KG.get(alt, DEFAULT_PRICE)[1]
            saves = round(kg * (cur - alt_price), 2)
            if saves >= 0.05:
                carb_delta = round(ing["grams"] * (CARBS_PER_100G.get(alt, 0) - CARBS_PER_100G.get(name, 0)) / 100, 1)
                options.append({"from": name, "to": alt, "grams": ing["grams"], "saves_usd": saves,
                                "carb_delta_g": carb_delta, "walmart_url": walmart_url(alt)})
                taken.add(alt)
                break
    return sorted(options, key=lambda o: -o["saves_usd"])
