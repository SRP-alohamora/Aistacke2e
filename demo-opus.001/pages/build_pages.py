"""Build the static GitHub Pages site for demo-opus.001 (stdlib only).

The site serves the same single-page UI; pages/pyodide-bridge.js runs the Python backend in the
browser with Pyodide. Output layout:

    <out>/index.html          UI with the bridge script injected before app.js
    <out>/static/...          CSS, JS, photos
    <out>/engine/bundle.json  aistack_demo/*.py, data/*.yaml, photo metadata, evidence (written into Pyodide's FS)
    <out>/source/<f>.html     read-only source viewer pages for guardrail links

Usage: python demo-opus.001/pages/build_pages.py --out _site
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def source_page(name: str, text: str) -> str:
    rows = "".join(f'<tr id="L{i}"><td class="n"><a href="#L{i}">{i}</a></td><td><pre>{html.escape(line)}</pre></td></tr>'
                   for i, line in enumerate(text.splitlines(), 1))
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(name)}</title>
<style>body{{margin:0;font:13px/1.5 ui-monospace,Menlo,monospace;background:#fff;color:#202124}}
header{{padding:12px 20px;border-bottom:1px solid #dadce0;font:500 15px Roboto,system-ui,sans-serif;position:sticky;top:0;background:#fff}}
table{{border-collapse:collapse;width:100%}}td{{padding:0 12px;vertical-align:top}}td.n{{color:#9aa0a6;text-align:right;user-select:none;width:1%}}
td.n a{{color:inherit;text-decoration:none}}pre{{margin:0;white-space:pre-wrap}}tr:target{{background:#fef7e0}}tr:target td.n{{color:#b06000;font-weight:700}}</style>
</head><body><header>{html.escape(name)} <span style="color:#5f6368;font-weight:400">· read-only · demo-opus.001</span></header><table>{rows}</table>
<script>const t=document.querySelector(location.hash||'#none');if(t)t.scrollIntoView({{block:'center'}});</script></body></html>"""


def build(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "static", out / "static")
    shutil.copy(ROOT / "pages" / "pyodide-bridge.js", out / "static" / "pyodide-bridge.js")

    index = (ROOT / "static" / "index.html").read_text()
    marker = '<script src="static/app.js"></script>'
    assert marker in index, "index.html layout changed"
    index = index.replace(marker, '<script src="static/pyodide-bridge.js"></script>\n' + marker)
    (out / "index.html").write_text(index)

    files: dict[str, str] = {}
    for p in sorted((ROOT / "aistack_demo").glob("*.py")):
        files[f"aistack_demo/{p.name}"] = p.read_text()
    for p in sorted((ROOT / "data").glob("*.yaml")) + sorted((ROOT / "data").glob("*.json")):
        files[f"data/{p.name}"] = p.read_text()
    files["static/photos/photos.json"] = (ROOT / "static" / "photos" / "photos.json").read_text()
    for p in sorted((ROOT / "evidence").glob("*.json")):
        files[f"evidence/{p.name}"] = p.read_text()
    (out / "engine").mkdir()
    (out / "engine" / "bundle.json").write_text(json.dumps({"files": files}))

    (out / "source").mkdir()
    for p in [*sorted((ROOT / "aistack_demo").glob("*.py")), *sorted((ROOT / "data").glob("*.yaml"))]:
        (out / "source" / f"{p.name}.html").write_text(source_page(p.name, p.read_text()))

    (out / ".nojekyll").write_text("")
    print(f"built {out} ({len(files)} engine files)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_site")
    build(Path(ap.parse_args().out).resolve())
