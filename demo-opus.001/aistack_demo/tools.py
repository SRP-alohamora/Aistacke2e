"""Tooling layer: tool inventory, parameter schemas, drift detection and invocation logging.

Drift = a tool's current parameter signature no longer matches the hash registered in
data/tool_registry.yaml. Re-register intentionally after a reviewed change:

    uv run python -m aistack_demo.tools --register
"""
from __future__ import annotations

import hashlib
import inspect
import json
import time
from contextlib import contextmanager

import yaml

from . import grocery, guards, nutrition, photos
from .pipeline import retrieve
from .config import DATA

REGISTRY_FILE = DATA / "tool_registry.yaml"

# External tools connected over MCP. None at P0 (typed in-process adapters only; MCP client is P1).
MCP_SERVERS: list[dict] = []
MCP_CANDIDATES = [
    {"name": "Grocery cart partner", "why": "Shopping-list enhancement; needs per-user OAuth and write confirmation"},
    {"name": "CGM data partner", "why": "Glucose-aware carb targets; health data class"},
]


TOOLS = [
    {"name": "safety.check_request_text", "fn": guards.check_request_text, "adapter": "in-process",
     "role": "Detect dosing questions", "side_effects": "none"},
    {"name": "retrieval.retrieve", "fn": retrieve, "adapter": "in-process",
     "role": "Find fusion patterns", "side_effects": "none"},
    {"name": "nutrition.boost_for_goals", "fn": nutrition.boost_for_goals, "adapter": "in-process",
     "role": "Meet protein / fat minimums", "side_effects": "none"},
    {"name": "nutrition.adjust_to_target", "fn": nutrition.adjust_to_target, "adapter": "in-process",
     "role": "Re-balance carbs", "side_effects": "none"},
    {"name": "nutrition.meal_nutrients", "fn": nutrition.meal_nutrients, "adapter": "in-process",
     "role": "Per-meal totals and % DV", "side_effects": "none"},
    {"name": "grocery.shopping_estimate", "fn": grocery.shopping_estimate, "adapter": "in-process",
     "role": "Store cost estimate (sample prices)", "side_effects": "none"},
    {"name": "grocery.budget_options", "fn": grocery.budget_options, "adapter": "in-process",
     "role": "Cheaper same-role swaps", "side_effects": "none"},
    {"name": "photos.choose_photo", "fn": photos.choose_photo, "adapter": "in-process",
     "role": "Pick licensed photo", "side_effects": "none"},
]


def param_schema(fn) -> list[dict]:
    out = []
    for p in inspect.signature(fn).parameters.values():
        out.append({"name": p.name, "type": str(p.annotation).replace("typing.", ""),
                    "default": None if p.default is inspect.Parameter.empty else repr(p.default)})
    return out


def schema_hash(schema: list[dict]) -> str:
    return hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:12]


def registered() -> dict:
    return yaml.safe_load(REGISTRY_FILE.read_text())["tools"] if REGISTRY_FILE.exists() else {}


def inventory() -> list[dict]:
    reg = registered()
    out = []
    for t in TOOLS:
        schema = param_schema(t["fn"])
        h = schema_hash(schema)
        pinned = reg.get(t["name"])
        out.append({"name": t["name"], "adapter": t["adapter"], "role": t["role"], "side_effects": t["side_effects"],
                    "params": schema, "hash": h, "registered_hash": pinned,
                    "drift": "unregistered" if pinned is None else ("ok" if pinned == h else "drift")})
    return out


def drift_summary() -> dict:
    inv = inventory()
    bad = [t["name"] for t in inv if t["drift"] != "ok"]
    return {"total": len(inv), "ok": len(inv) - len(bad), "drifted": bad}


def register() -> None:
    REGISTRY_FILE.write_text(yaml.safe_dump(
        {"note": "Registered tool parameter-schema hashes. Change only after reviewing a tool signature change.",
         "tools": {t["name"]: t["hash"] for t in inventory()}}, sort_keys=True))


# --- invocation log ------------------------------------------------------------------------

class ToolLog:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    @contextmanager
    def call(self, name: str, **params):
        t0 = time.perf_counter()
        entry = {"tool": name, "params": {k: _short(v) for k, v in params.items()}, "status": "ok"}
        try:
            yield entry
        except Exception as e:
            entry["status"] = f"error: {type(e).__name__}"
            raise
        finally:
            entry["ms"] = round((time.perf_counter() - t0) * 1000, 2)
            self.calls.append(entry)


def _short(v) -> str:
    s = json.dumps(v, default=str)
    return s if len(s) <= 80 else s[:77] + "..."


if __name__ == "__main__":
    import sys

    if "--register" in sys.argv:
        register()
        print(f"registered {len(TOOLS)} tool schemas -> {REGISTRY_FILE}")
    else:
        for t in inventory():
            print(f"{t['name']:28s} {t['hash']}  {t['drift']}")
