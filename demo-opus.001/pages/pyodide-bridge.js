"use strict";
// GitHub Pages build only: runs the demo's Python backend (FastAPI app) inside the browser with Pyodide.
// Every fetch("/api/...") is routed to the in-browser app. Offline fixture mode only: no API keys in the browser.
(() => {
  const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/";
  const FASTAPI = "fastapi==0.115.6";
  const BRIDGE_PY = `
import os, sys
os.environ["AISTACK_DEMO_OFFLINE"] = "1"
sys.path.insert(0, "/home/pyodide/app")

# Pyodide has no threads: run sync endpoints inline instead of in a thread pool.
async def _inline(func, *args, **kwargs):
    return func(*args, **kwargs)
import starlette.concurrency, starlette.routing, fastapi.concurrency, fastapi.routing, fastapi.dependencies.utils
for _m in (starlette.concurrency, starlette.routing, fastapi.concurrency, fastapi.routing, fastapi.dependencies.utils):
    if hasattr(_m, "run_in_threadpool"):
        _m.run_in_threadpool = _inline

from aistack_demo.server import app
from pyodide.ffi import to_js
import js

async def handle(method, path, query, body):
    raw = bytes(body.to_py()) if body is not None else b""
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
             "scheme": "https", "path": path, "raw_path": path.encode(), "query_string": query.encode(),
             "root_path": "", "headers": [(b"content-type", b"application/json")],
             "client": ("browser", 0), "server": ("pages", 443)}
    sent = False
    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": raw, "more_body": False}
        return {"type": "http.disconnect"}
    msgs = []
    async def send(message):
        msgs.append(message)
    await app(scope, receive, send)
    start = next(m for m in msgs if m["type"] == "http.response.start")
    data = b"".join(m.get("body", b"") for m in msgs if m["type"] == "http.response.body")
    headers = [[k.decode(), v.decode()] for k, v in start["headers"]]
    return to_js({"status": start["status"], "headers": headers, "body": data}, dict_converter=js.Object.fromEntries)
`;

  const overlay = document.createElement("div");
  overlay.id = "engineOverlay";
  overlay.innerHTML = `<div class="engine-card"><div class="spinner"></div>
    <div><b>Starting the demo engine</b><div class="muted" id="engineStep">Loading Python in your browser…</div>
    <div class="muted engine-note">The app's Python backend runs entirely in this tab (Pyodide). Offline, simulated model - no API keys, nothing sent to a server.</div></div></div>`;
  const style = document.createElement("style");
  style.textContent = `#engineOverlay{position:fixed;inset:0;background:rgb(248 249 250/.92);z-index:50;display:grid;place-items:center}
    .engine-card{display:flex;gap:16px;align-items:center;background:#fff;border:1px solid #dadce0;border-radius:14px;padding:22px 26px;max-width:520px;font:14px/1.5 Roboto,system-ui,sans-serif}
    .engine-note{font-size:12px;margin-top:6px}`;
  document.head.appendChild(style);
  const step = (t) => { const el = document.getElementById("engineStep"); if (el) el.textContent = t; };

  let ready = null;
  function boot() {
    if (ready) return ready;
    document.body ? document.body.appendChild(overlay) : addEventListener("DOMContentLoaded", () => document.body.appendChild(overlay));
    ready = (async () => {
      await new Promise((res, rej) => {
        const s = document.createElement("script"); s.src = PYODIDE + "pyodide.js"; s.onload = res; s.onerror = rej; document.head.appendChild(s);
      });
      const py = await loadPyodide({ indexURL: PYODIDE });
      step("Loading pydantic and pyyaml…");
      await py.loadPackage(["micropip", "pydantic", "pyyaml"]);
      step("Installing FastAPI…");
      await py.pyimport("micropip").install(FASTAPI);
      step("Loading the AiStackE2E demo…");
      const bundle = await (await fetch("engine/bundle.json")).json();
      for (const [path, content] of Object.entries(bundle.files)) {
        const full = "/home/pyodide/app/" + path;
        py.FS.mkdirTree(full.slice(0, full.lastIndexOf("/")));
        py.FS.writeFile(full, content);
      }
      await py.runPythonAsync(BRIDGE_PY);
      overlay.remove();
      return py;
    })().catch((e) => {
      step("Could not start the demo engine: " + e.message);
      throw e;
    });
    return ready;
  }

  const realFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    // Only the app's own relative "/api/..." calls are routed to Python; everything else (Pyodide, CDN) is a real fetch.
    if (typeof input !== "string" || !input.startsWith("/api/")) return realFetch(input, init);
    const url = input;
    const py = await boot();
    const [path, query = ""] = url.split("?");
    const body = init.body ? new TextEncoder().encode(init.body) : null;
    const res = await py.globals.get("handle")(init.method || "GET", path, query, body);
    return new Response(res.status === 204 ? null : res.body, { status: res.status, headers: res.headers });
  };
  boot();
})();
