"""Paths, data loading and the model factory (live vs offline)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

from .models import AnthropicModel, FixtureModel, OpenAIModel

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EVIDENCE = ROOT / "evidence"
STATIC = ROOT / "static"
PACKAGE = Path(__file__).resolve().parent


@lru_cache
def prices() -> dict:
    return yaml.safe_load((DATA / "prices.yaml").read_text())


@lru_cache
def simulation() -> dict:
    return yaml.safe_load((DATA / "simulation.yaml").read_text())


@lru_cache
def eval_cases() -> dict:
    return yaml.safe_load((DATA / "eval_cases.yaml").read_text())


def forced_offline() -> bool:
    return os.environ.get("AISTACK_DEMO_OFFLINE") == "1"


def provider_key_present(provider: str) -> bool:
    env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)
    return bool(env and os.environ.get(env))


def mode_for(model_key: str) -> str:
    provider = prices()["models"][model_key]["provider"]
    if forced_offline() or not provider_key_present(provider):
        return "offline"
    return "live"


def make_model(model_key: str, mode: str | None = None):
    entry = prices()["models"][model_key]
    mode = mode or mode_for(model_key)
    if mode == "offline":
        return FixtureModel(entry["model_id"], simulation().get(model_key))
    if entry["provider"] == "anthropic":
        return AnthropicModel(entry["model_id"])
    if entry["provider"] == "openai":
        return OpenAIModel(entry["model_id"])
    raise ValueError(f"no adapter for provider {entry['provider']}")
