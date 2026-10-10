# aistack: managed - typed contracts for the Fusion Fuel recipe boundary.
"""Pydantic contracts. JSON Schema exports carry `x-aistack` semantic metadata."""
from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

DISCLAIMER = (
    "Not medical advice. Check carbohydrate targets and any medication "
    "decisions with your care team."
)


def _meta(unit: str | None = None, semantic: str | None = None,
          data_class: str | None = None) -> dict:
    extra: dict = {}
    if unit:
        extra["x-aistack-unit"] = unit
    if semantic:
        extra["x-aistack-semantic"] = semantic
    if data_class:
        extra["x-aistack-data-class"] = data_class
    return extra


class ActivityTiming(str, Enum):
    PRE_WORKOUT = "pre_workout"
    POST_WORKOUT = "post_workout"
    REST_DAY = "rest_day"


GoalKey = Literal["balanced", "high_protein", "keto", "high_fiber", "low_sodium"]
RestrictionKey = Literal["gluten_free", "dairy_free", "nut_free", "shellfish_free",
                         "low_sodium", "vegetarian", "vegan"]


class RecipeRequest(BaseModel):
    """aistack/RecipeRequest@1.2.0 - side effects: none; timeout 30 s; idempotent on request_id.

    1.2.0 (minor, backward compatible): optional organic, budget_friendly, available_ingredients.
    1.3.0 (minor): optional restrictions (health conditions / dietary restrictions).
    1.4.0 (minor): optional nutrition_goals.
    """

    model_config = ConfigDict(extra="forbid")

    request_id: UUID = Field(default_factory=uuid4)
    cuisines: list[str] = Field(min_length=1, max_length=3,
                                description="Cuisines to fuse, e.g. ['korean', 'mexican']")
    max_prep_minutes: int = Field(30, ge=5, le=30, json_schema_extra=_meta(unit="min"))
    carb_target_g: float = Field(ge=10, le=120, json_schema_extra=_meta(
        unit="g", semantic="nutrition.carbohydrate_grams.per_meal_target", data_class="health"))
    activity: ActivityTiming = ActivityTiming.REST_DAY
    exclusions: list[str] = Field(default_factory=list, json_schema_extra=_meta(data_class="health"),
                                  description="Allergens or disliked ingredients")
    note: str = Field("", max_length=500, json_schema_extra=_meta(data_class="confidential"),
                      description="Free text from the user; passes the guard first")
    organic: bool = Field(False, description="Prefer organic versions of ingredients")
    budget_friendly: bool = Field(False, description="Avoid premium-priced ingredients")
    available_ingredients: list[str] = Field(default_factory=list, max_length=30,
                                             json_schema_extra=_meta(data_class="internal"),
                                             description="Ingredients the user already has; preferred when possible")
    restrictions: list[RestrictionKey] = Field(default_factory=list, max_length=7,
                                               json_schema_extra=_meta(data_class="health"),
                                               description="Health conditions or dietary restrictions")
    nutrition_goals: list[GoalKey] = Field(default_factory=lambda: ["balanced"], max_length=5,
                                           json_schema_extra=_meta(data_class="health"),
                                           description="Per-meal nutrition goals")


class Ingredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    grams: float = Field(gt=0, le=1000, json_schema_extra=_meta(unit="g"))
    carbs_g: float = Field(ge=0, json_schema_extra=_meta(
        unit="g", semantic="nutrition.carbohydrate_grams.computed"))


class Nutrients(BaseModel):
    """Approximate per-meal totals; pct_daily_value uses FDA Daily Values (2,000 kcal diet)."""

    model_config = ConfigDict(extra="forbid")

    carbs_g: float = Field(ge=0, json_schema_extra=_meta(unit="g"))
    protein_g: float = Field(ge=0, json_schema_extra=_meta(unit="g"))
    fat_g: float = Field(ge=0, json_schema_extra=_meta(unit="g"))
    sodium_mg: float = Field(ge=0, json_schema_extra=_meta(unit="mg"))
    fiber_g: float = Field(ge=0, json_schema_extra=_meta(unit="g"))
    calories_kcal: float = Field(ge=0, json_schema_extra=_meta(unit="kcal"))
    pct_daily_value: dict[str, int]


class RecipeCard(BaseModel):
    """aistack/RecipeCard@2.1.0 - carbs are computed by the nutrition tool, never by the model.

    2.1.0 (minor): optional tags and pantry_used.
    2.2.0 (minor): optional nutrients (protein, fat, sodium, fiber, calories, % Daily Value).
    2.3.0 (minor): optional goals (per-goal status with checks).
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=80)
    prep_minutes: int = Field(ge=1, le=30, json_schema_extra=_meta(unit="min"))
    ingredients: list[Ingredient] = Field(min_length=3)
    steps: list[str] = Field(min_length=2, max_length=10)
    carbs_g: float = Field(ge=0, json_schema_extra=_meta(
        unit="g", semantic="nutrition.carbohydrate_grams.computed"))
    carb_target_g: float
    computed_by: Literal["nutrition_tool"] = "nutrition_tool"
    nutrients: Nutrients | None = None
    goals: list[dict] = Field(default_factory=list, description="Per-goal status: key, label, met, checks")
    tags: list[str] = Field(default_factory=list)
    pantry_used: list[str] = Field(default_factory=list,
                                   description="Ingredients from available_ingredients that the recipe uses")
    disclaimer: Literal[DISCLAIMER] = DISCLAIMER  # type: ignore[valid-type]


class BlockedResponse(BaseModel):
    blocked: Literal[True] = True
    reason: str
    message: str
    disclaimer: str = DISCLAIMER


# JSON Schema the model must follow for its draft (structured output).
# Kept to features every provider's strict mode accepts.
DRAFT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "prep_minutes": {"type": "integer"},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "grams": {"type": "number"},
                },
                "required": ["name", "grams"],
                "additionalProperties": False,
            },
        },
        "steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "prep_minutes", "ingredients", "steps"],
    "additionalProperties": False,
}
