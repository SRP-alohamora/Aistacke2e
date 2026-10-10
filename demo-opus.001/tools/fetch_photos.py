"""Download a small library of freely licensed food photos from Wikimedia Commons.

Each photo is matched to recipes by tags (cuisines and ingredients). Attribution is stored
in static/photos/photos.json and shown under the image. Re-run to refresh:

    uv run python tools/fetch_photos.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent.parent / "static" / "photos"
API = "https://commons.wikimedia.org/w/api.php"
UA = "aistack-demo/0.1 (AiStackE2E demo; photo attribution kept)"
OK_LICENSES = ("CC BY", "CC0", "Public domain")

THEMES = [
    {"slug": "burrito-bowl", "query": "burrito bowl", "tags": ["mexican", "black beans (cooked)", "corn tortilla", "salsa", "avocado", "chicken breast"]},
    {"slug": "bibimbap", "query": "bibimbap", "tags": ["korean", "kimchi", "gochujang", "eggs", "spinach", "white rice (cooked)"]},
    {"slug": "poke-bowl", "query": "poke bowl salmon", "tags": ["japanese", "salmon", "edamame", "brown rice (cooked)", "cucumber", "avocado"]},
    {"slug": "thai-noodles", "query": "pad thai shrimp", "tags": ["thai", "rice noodles (cooked)", "shrimp", "peanuts", "lime juice"]},
    {"slug": "palak-paneer", "query": "palak paneer", "tags": ["indian", "paneer", "spinach", "naan"]},
    {"slug": "chana-masala", "query": "chana masala", "tags": ["indian", "chickpeas (cooked)", "tomato", "onion"]},
    {"slug": "quinoa-salad", "query": "quinoa salad bowl", "tags": ["mediterranean", "quinoa (cooked)", "feta", "cucumber", "tomato"]},
    {"slug": "tofu-bowl", "query": "tofu rice bowl vegetables", "tags": ["firm tofu", "broccoli", "brown rice (cooked)", "korean", "japanese"]},
    {"slug": "sweet-potato-bowl", "query": "sweet potato bowl", "tags": ["american", "sweet potato (baked)", "ground turkey", "broccoli"]},
    {"slug": "tacos", "query": "chicken tacos plate", "tags": ["mexican", "corn tortilla", "chicken breast", "cilantro", "salsa"]},
    {"slug": "buddha-bowl", "query": "buddha bowl", "tags": ["mediterranean", "italian", "american", "chickpeas (cooked)", "quinoa (cooked)", "sweet potato (baked)", "spinach", "hummus"]},
]


def strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def get(client: httpx.Client, url: str, **kw) -> httpx.Response:
    for attempt in range(5):
        r = client.get(url, **kw)
        if r.status_code != 429:
            r.raise_for_status()
            return r
        time.sleep(5 * (attempt + 1))
    r.raise_for_status()
    return r


def search(client: httpx.Client, query: str) -> list[dict]:
    r = get(client, API, params={
        "action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6, "gsrlimit": 12, "prop": "imageinfo",
        "iiprop": "url|extmetadata|size", "iiurlwidth": 1280, "format": "json"})
    pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    return pages


def pick(pages: list[dict]) -> dict | None:
    for p in pages:
        ii = p["imageinfo"][0]
        meta = ii.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        w, h = ii.get("width", 0), ii.get("height", 0)
        if not lic.startswith(OK_LICENSES) or w < 1200 or not (1.2 <= w / max(h, 1) <= 2.0):
            continue
        return {"title": p["title"], "thumb": ii["thumburl"], "page": ii["descriptionurl"], "license": lic,
                "license_url": meta.get("LicenseUrl", {}).get("value", ""),
                "artist": strip_html(meta.get("Artist", {}).get("value", "unknown"))[:120]}
    return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])  # optional: refresh only these slugs, keep the rest
    existing = json.loads((OUT / "photos.json").read_text()) if (OUT / "photos.json").exists() else []
    keep = {t["slug"] for t in THEMES}
    library = [e for e in existing if e["slug"] in keep and only and e["slug"] not in only]
    with httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True) as client:
        for theme in THEMES:
            if only and theme["slug"] not in only:
                continue
            found = pick(search(client, theme["query"]))
            if not found:
                print(f"skip {theme['slug']}: no suitable licensed image", file=sys.stderr)
                continue
            img = get(client, found["thumb"])
            if not img.headers.get("content-type", "").startswith("image/"):
                print(f"skip {theme['slug']}: not an image", file=sys.stderr)
                continue
            (OUT / f"{theme['slug']}.jpg").write_bytes(img.content)
            library.append({**theme, **{k: v for k, v in found.items() if k != "thumb"},
                            "file": f"/static/photos/{theme['slug']}.jpg"})
            print(f"ok   {theme['slug']}: {found['title']} ({found['license']})")
            time.sleep(2)
    (OUT / "photos.json").write_text(json.dumps(library, indent=2))


if __name__ == "__main__":
    main()
