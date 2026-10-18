"""Transparent, approximate adult calorie-goal estimates."""
from __future__ import annotations

ACTIVITY_FACTORS = {
    "Sedentary": 1.2,
    "Lightly active": 1.375,
    "Moderately active": 1.55,
    "Very active": 1.725,
    "Extra active": 1.9,
}

PACE_KG_PER_WEEK = {
    "Maintain weight": 0.0,
    "Lose 0.2 kg/week": -0.2,
    "Lose 0.5 kg/week": -0.5,
    "Gain 0.2 kg/week": 0.2,
    "Gain 0.5 kg/week": 0.5,
}


def estimate_daily_goal(member) -> dict[str, int | str | None] | None:
    """Estimate maintenance and intake targets with Mifflin-St Jeor.

    The simple pace adjustment uses 7,700 kcal per kg as an approximate
    arithmetic conversion. This is a rough estimate, not a clinical plan.
    """
    needed = (
        member.current_weight_kg, member.goal_weight_kg, member.age_years,
        member.height_cm, member.calorie_formula, member.activity_level,
    )
    if any(value is None for value in needed) or member.age_years < 18:
        return None
    if member.current_weight_kg <= 0 or member.goal_weight_kg <= 0 or member.height_cm <= 0:
        return None
    if member.calorie_formula not in {"Female formula", "Male formula"}:
        return None
    if member.activity_level not in ACTIVITY_FACTORS:
        return None

    weight = float(member.current_weight_kg)
    height = float(member.height_cm)
    age = int(member.age_years)
    sex_adjustment = -161 if member.calorie_formula == "Female formula" else 5
    resting = 10 * weight + 6.25 * height - 5 * age + sex_adjustment
    maintenance = round(resting * ACTIVITY_FACTORS[member.activity_level])

    # If current and goal weights match, maintenance always wins regardless
    # of a stale pace saved in an older profile.
    if abs(float(member.current_weight_kg) - float(member.goal_weight_kg)) < 0.01:
        pace = "Maintain weight"
    else:
        pace = member.goal_pace or "Maintain weight"
        required_direction = "Gain" if member.goal_weight_kg > member.current_weight_kg else "Lose"
        if pace != "Maintain weight" and not pace.startswith(required_direction):
            rate = "0.5" if "0.5" in pace else "0.2"
            pace = f"{required_direction} {rate} kg/week"
    delta = PACE_KG_PER_WEEK.get(pace, 0.0)
    target = round(maintenance + delta * 7700 / 7)
    # NIDDK's Body Weight Planner requires targets of at least 1,000 kcal/day.
    # Do not silently clamp a lower estimate; leave the target unset instead.
    safe_target = target if target >= 1000 else None
    return {"maintenance_kcal": maintenance, "target_kcal": safe_target, "pace": pace}
