"""Family profile objects used by food recommendations and the SQLite app."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FamilyMember:
    name: str
    diet: str = "non-veg"  # "vegan" | "veg" | "non-veg"
    allergies: list[str] = field(default_factory=list)
    liked: list[str] = field(default_factory=list)
    calorie_goal_kcal: int | None = None
    current_weight_kg: float | None = None
    goal_weight_kg: float | None = None
    goal_pace: str | None = None
    activity_level: str | None = None
    age_years: int | None = None
    height_cm: float | None = None
    calorie_formula: str | None = None
    user_id: int | None = None
