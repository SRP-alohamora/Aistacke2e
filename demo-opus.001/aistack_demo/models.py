# aistack: managed - ChatModel port and provider adapters.
"""Typed model adapters behind one port.

- AnthropicModel: official `anthropic` SDK, structured output via output_config.format.
- OpenAIModel: Chat Completions over HTTPS with json_schema response_format.
  NOTE: not exercised against the live OpenAI API in this build (no key was available).
- FixtureModel: deterministic offline stand-in. Everything it returns is SIMULATED.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from dataclasses import dataclass, field

from .nutrition import CARBS_PER_100G, PREMIUM, normalise


@dataclass
class ModelResult:
    text: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    latency_ms: int = 0
    simulated: bool = False
    stop_reason: str = "end_turn"
    mapping_losses: list[str] = field(default_factory=list)


class ModelError(Exception):
    def __init__(self, code: str, retryable: bool, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.retryable = retryable
        self.detail = detail


class AnthropicModel:
    provider = "anthropic"

    def __init__(self, model_id: str, timeout_s: float = 60.0, effort: str = "low"):
        import anthropic  # imported lazily so offline mode needs no SDK credentials

        self._anthropic = anthropic
        self.model_id = model_id
        self.effort = effort
        self.client = anthropic.Anthropic(timeout=timeout_s, max_retries=2)

    def generate_json(self, system: str, user: str, schema: dict) -> ModelResult:
        a = self._anthropic
        t0 = time.perf_counter()
        try:
            resp = self.client.messages.create(
                model=self.model_id,
                max_tokens=8000,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                output_config={"effort": self.effort,
                               "format": {"type": "json_schema", "schema": schema}},
            )
        except a.BadRequestError as e:
            raise ModelError("INVALID_REQUEST", False, e.message) from e
        except a.AuthenticationError as e:
            raise ModelError("UNAUTHORIZED", False, "check ANTHROPIC_API_KEY") from e
        except a.NotFoundError as e:
            raise ModelError("INVALID_REQUEST", False, f"unknown model {self.model_id}") from e
        except a.RateLimitError as e:
            raise ModelError("RATE_LIMITED", True, e.message) from e
        except a.APIStatusError as e:
            raise ModelError("PROVIDER_UNAVAILABLE", e.status_code >= 500, e.message) from e
        except a.APIConnectionError as e:
            raise ModelError("PROVIDER_UNAVAILABLE", True, "network error") from e
        latency = int((time.perf_counter() - t0) * 1000)
        if resp.stop_reason == "refusal":
            raise ModelError("CONTENT_BLOCKED", False, "model declined the request")
        if resp.stop_reason == "max_tokens":
            raise ModelError("INVALID_RESPONSE", True, "output truncated at max_tokens")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        u = resp.usage
        return ModelResult(
            text=text, model=self.model_id, provider=self.provider,
            input_tokens=u.input_tokens, output_tokens=u.output_tokens,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
            latency_ms=latency, stop_reason=resp.stop_reason or "end_turn",
        )


class OpenAIModel:
    provider = "openai"
    URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, model_id: str, timeout_s: float = 60.0):
        import httpx

        self._httpx = httpx
        self.model_id = model_id
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ModelError("UNAUTHORIZED", False, "OPENAI_API_KEY is not set")
        self.client = httpx.Client(timeout=timeout_s,
                                   headers={"Authorization": f"Bearer {key}"})

    def generate_json(self, system: str, user: str, schema: dict) -> ModelResult:
        body = {
            "model": self.model_id,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "draft_recipe", "schema": schema,
                                                "strict": True}},
        }
        t0 = time.perf_counter()
        try:
            r = self.client.post(self.URL, json=body)
        except self._httpx.HTTPError as e:
            raise ModelError("PROVIDER_UNAVAILABLE", True, str(e)) from e
        latency = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 429:
            raise ModelError("RATE_LIMITED", True, r.text[:200])
        if r.status_code in (401, 403):
            raise ModelError("UNAUTHORIZED", False, r.text[:200])
        if r.status_code >= 400:
            raise ModelError("PROVIDER_UNAVAILABLE" if r.status_code >= 500 else "INVALID_REQUEST",
                             r.status_code >= 500, r.text[:200])
        data = r.json()
        choice = data["choices"][0]
        if choice.get("finish_reason") == "content_filter" or choice["message"].get("refusal"):
            raise ModelError("CONTENT_BLOCKED", False, "model declined the request")
        usage = data.get("usage", {})
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
        return ModelResult(
            text=choice["message"].get("content") or "", model=self.model_id,
            provider=self.provider,
            input_tokens=max(0, usage.get("prompt_tokens", 0) - cached),
            output_tokens=usage.get("completion_tokens", 0),
            cache_read_tokens=cached, latency_ms=latency,
            stop_reason=choice.get("finish_reason", "stop"),
            mapping_losses=["explicit cache_control hint not mapped (provider caches automatically)",
                            "effort setting not mapped"],
        )


# --- Offline fixture -------------------------------------------------------

_CUISINE_INGREDIENTS = {
    "korean": ["kimchi", "gochujang", "scallion", "sesame seeds", "firm tofu"],
    "mexican": ["corn tortilla", "black beans (cooked)", "salsa", "avocado", "lime juice"],
    "japanese": ["soba noodles (cooked)", "soy sauce", "edamame", "ginger", "salmon"],
    "indian": ["paneer", "chickpeas (cooked)", "spinach", "ginger", "naan"],
    "thai": ["rice noodles (cooked)", "coconut milk", "peanuts", "lime juice", "shrimp"],
    "mediterranean": ["whole wheat pita", "hummus", "feta", "cucumber", "tomato"],
    "italian": ["tomato", "zucchini", "olive oil", "garlic", "chicken breast"],
    "american": ["sweet potato (baked)", "ground turkey", "broccoli", "cheddar", "corn kernels"],
}
_PROTEINS = ["chicken breast", "salmon", "shrimp", "firm tofu", "eggs", "ground turkey", "paneer"]
_BASES = ["brown rice (cooked)", "quinoa (cooked)", "corn tortilla", "sweet potato (baked)",
          "soba noodles (cooked)", "rice noodles (cooked)", "black beans (cooked)"]

DEFAULT_SIM_PROFILE = {"carb_error_sd": 0.10, "exclusion_violation_rate": 0.0,
                       "schema_error_rate": 0.0, "latency_ms": 900}


class FixtureModel:
    """Deterministic, offline. Output is SIMULATED and must never be presented as measured."""

    provider = "fixture"

    def __init__(self, model_id: str, profile: dict | None = None):
        self.model_id = model_id
        self.profile = {**DEFAULT_SIM_PROFILE, **(profile or {})}

    def generate_json(self, system: str, user: str, schema: dict) -> ModelResult:
        req = _extract_request(user)
        # Preferences that only filter ingredients stay out of the seed, so toggling them changes only
        # the affected items (e.g. a budget swap) instead of producing an unrelated recipe.
        seed_req = {k: v for k, v in req.items() if k not in ("budget_friendly", "organic")}
        seed = hashlib.sha256(f"{self.model_id}|{json.dumps(seed_req, sort_keys=True)}".encode()).hexdigest()
        rng = random.Random(int(seed[:12], 16))
        cuisines = [c.lower() for c in req.get("cuisines", ["american"])]
        exclusions = [e.lower() for e in req.get("exclusions", [])]
        target = float(req.get("carb_target_g", 45))

        pool: list[str] = []
        for c in cuisines:
            pool += _CUISINE_INGREDIENTS.get(c, _CUISINE_INGREDIENTS["american"])
        violate = exclusions and rng.random() < self.profile["exclusion_violation_rate"]

        budget = bool(req.get("budget_friendly"))
        pantry = [k for k in (normalise(a) for a in req.get("available_ingredients", [])) if k]

        def allowed(n: str) -> bool:
            if budget and n in PREMIUM:
                return False
            return violate or not any(e in n for e in exclusions)

        def pick(options: list[str], fallback: str) -> str:
            from_pantry = [p for p in pantry if p in options and allowed(p)]
            if from_pantry:
                return from_pantry[0]
            return next((o for o in rng.sample(options, len(options)) if allowed(o)), fallback)

        goals = set(req.get("nutrition_goals") or [])
        protein = pick(_PROTEINS, "eggs")
        base = pick(["black beans (cooked)", "lentils (cooked)", "chickpeas (cooked)"] if "high_fiber" in goals
                    else _BASES, "quinoa (cooked)")
        boosters = (["broccoli", "spinach"] if "high_fiber" in goals else []) + \
            (["avocado", "cheddar"] if "keto" in goals else [])
        candidates = [p for p in pantry if p not in (protein, base)] + boosters + list(dict.fromkeys(pool))
        extras = [n for n in dict.fromkeys(candidates) if allowed(n) and n not in (protein, base)][:3]
        if violate:
            bad = next((k for k in CARBS_PER_100G if any(e in k for e in exclusions)), None)
            if bad and bad not in extras:
                extras = extras[:2] + [bad]
        items = [(protein, 170.0 if goals & {"high_protein", "keto"} else 120.0)] + [(n, 30.0 if CARBS_PER_100G[n] > 20 else 60.0) for n in extras]
        other = sum(CARBS_PER_100G[n] * g / 100 for n, g in items)
        aim = max(0.0, target * (1 + rng.gauss(0, self.profile["carb_error_sd"])) - other)
        base_g = max(20.0, round(aim / (CARBS_PER_100G[base] / 100))) if CARBS_PER_100G[base] else 100
        items.insert(1, (base, base_g))

        steps = [f"Prepare the {protein} and season it with the {cuisines[0]} flavours.",
                 f"Warm the {base} and combine with " + ", ".join(n for n, _ in items[2:]) + ".",
                 "Plate, garnish and serve immediately."]
        if rng.random() < self.profile["schema_error_rate"]:
            steps = steps[:1]  # violates the contract (min 2 steps)
        draft = {
            "title": f"{' x '.join(c.title() for c in cuisines)} {protein.split(' (')[0].title()} Bowl",
            "prep_minutes": min(int(req.get("max_prep_minutes", 30)), 15 + rng.randint(0, 10)),
            "ingredients": [{"name": n, "grams": g} for n, g in items],
            "steps": steps,
        }
        text = json.dumps(draft)
        return ModelResult(
            text=text, model=self.model_id, provider=self.provider,
            input_tokens=len(system) // 4 + len(user) // 4, output_tokens=len(text) // 4,
            latency_ms=int(self.profile["latency_ms"] * (0.8 + 0.4 * rng.random())),
            simulated=True,
        )


def _extract_request(user: str) -> dict:
    m = re.search(r"REQUEST_JSON:\s*(\{.*\})", user, re.DOTALL)
    return json.loads(m.group(1)) if m else {}
