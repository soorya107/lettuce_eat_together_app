"""Content-based food recommendation engine.

Each dish is turned into a text "soup" (cuisine, course, diet, spice level,
ingredients, tags), vectorised with TF-IDF, and compared with cosine similarity.
A user profile is the average vector of the dishes they like; dishes closest to
that profile (and passing the user's filters) are recommended.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_PATH = Path(__file__).parent / "data" / "foods.csv"

# A vegan dish is also vegetarian; a non-veg eater can eat everything.
DIET_ALLOWED = {
    "vegan": {"vegan"},
    "veg": {"vegan", "veg"},
    "non-veg": {"vegan", "veg", "non-veg"},
}

# Ingredients and dietary category for common curry sides. These let the
# recommendation card hide pairings that conflict with a member's profile.
PAIRING_DETAILS = {
    "chapathi": ({"wheat", "gluten"}, "vegan"),
    "naan": ({"wheat", "gluten", "milk", "dairy"}, "veg"),
    "porotta": ({"wheat", "gluten", "milk", "dairy"}, "veg"),
    "parotta": ({"wheat", "gluten", "milk", "dairy"}, "veg"),
    "appam": ({"rice", "coconut"}, "vegan"),
    "roti": ({"wheat", "gluten"}, "vegan"),
    "jasmine rice": ({"rice"}, "vegan"),
    "steamed rice": ({"rice"}, "vegan"),
    "rice": ({"rice"}, "vegan"),
    "bhatura": ({"wheat", "gluten", "dairy"}, "veg"),
}

RESULT_COLUMNS = [
    "name", "cuisine", "diet", "course", "spice", "calories", "prep_time",
    "serving_g", "ingredients", "protein_g", "carbs_g", "fat_g",
    "pairing", "recipe_steps",
]


@dataclass
class Preferences:
    diet: str = "non-veg"                                   # "vegan" | "veg" | "non-veg"
    liked: list[str] = field(default_factory=list)          # dish names the user likes
    cuisines: list[str] = field(default_factory=list)       # empty = any cuisine
    courses: list[str] = field(default_factory=list)        # empty = any course
    exclude_ingredients: list[str] = field(default_factory=list)
    max_calories: int | None = None
    max_prep_time: int | None = None


class FoodRecommender:
    def __init__(self, csv_path: str | Path = DATA_PATH):
        self.df = pd.read_csv(csv_path).fillna("").reset_index(drop=True)
        # Keep older/custom catalogue files compatible with the richer recipe cards.
        for column in ("pairing", "recipe_steps"):
            if column not in self.df:
                self.df[column] = ""
        self._name_to_idx = {n.lower(): i for i, n in enumerate(self.df["name"])}
        self.vectorizer = TfidfVectorizer(token_pattern=r"\S+")
        self.matrix = self.vectorizer.fit_transform(self._build_soup())

    # ------------------------------------------------------------------ setup
    def _ingredient_list(self, i: int) -> list[str]:
        raw = str(self.df.at[i, "ingredients"])
        return [x.strip().lower() for x in raw.split(";") if x.strip()]

    def _build_soup(self) -> list[str]:
        soups = []
        for i, row in self.df.iterrows():
            ingredients = [x.replace(" ", "_") for x in self._ingredient_list(i)]
            tokens = (
                [row["cuisine"].lower()] * 2          # cuisine counts double
                + [row["course"].lower(), row["diet"].lower(), f"spice_{row['spice']}"]
                + ingredients
                + str(row["tags"]).lower().split()
            )
            soups.append(" ".join(tokens))
        return soups

    # ---------------------------------------------------------------- helpers
    def dish_names(self) -> list[str]:
        return sorted(self.df["name"])

    def cuisines(self) -> list[str]:
        return sorted(self.df["cuisine"].unique())

    def courses(self) -> list[str]:
        return sorted(self.df["course"].unique())

    def ingredients(self) -> list[str]:
        items = {ing for i in range(len(self.df)) for ing in self._ingredient_list(i)}
        return sorted(items)

    def _filter_mask(self, prefs: Preferences) -> np.ndarray:
        df = self.df
        mask = df["diet"].isin(DIET_ALLOWED[prefs.diet]).to_numpy().copy()
        if prefs.cuisines:
            mask &= df["cuisine"].isin(prefs.cuisines).to_numpy()
        if prefs.courses:
            mask &= df["course"].isin(prefs.courses).to_numpy()
        if prefs.max_calories is not None:
            mask &= (df["calories"] <= prefs.max_calories).to_numpy()
        if prefs.max_prep_time is not None:
            mask &= (df["prep_time"] <= prefs.max_prep_time).to_numpy()
        for ing in prefs.exclude_ingredients:
            has_ing = df["ingredients"].str.lower().str.contains(ing.lower(), regex=False)
            mask &= ~has_ing.to_numpy()
        return mask

    def _why(self, i: int, liked_idx: list[int]) -> str:
        if not liked_idx:
            return "Matches your filters"
        liked_ingredients = {ing for j in liked_idx for ing in self._ingredient_list(j)}
        shared = sorted(set(self._ingredient_list(i)) & liked_ingredients)
        liked_cuisines = {self.df.at[j, "cuisine"] for j in liked_idx}
        parts = []
        if self.df.at[i, "cuisine"] in liked_cuisines:
            parts.append(f"same cuisine ({self.df.at[i, 'cuisine']})")
        if shared:
            parts.append("shares " + ", ".join(shared[:3]))
        return "; ".join(parts) or "similar flavour profile"

    @staticmethod
    def _safe_pairings(pairing: str, diet: str, allergies: list[str]) -> str:
        """Keep only sides compatible with the member's diet and exclusions."""
        if not pairing:
            return ""
        aliases = {
            "milk solids": "milk", "dairy": "milk", "coconut milk": "coconut",
            "wheat flour": "wheat", "whole wheat": "wheat",
        }
        excluded = set()
        for allergy in allergies:
            item = str(allergy).strip().lower()
            excluded.add(aliases.get(item, item))
        safe = []
        for option in str(pairing).split("|"):
            name = option.strip()
            details = PAIRING_DETAILS.get(name.lower())
            if not details:
                continue
            ingredients, pairing_diet = details
            if diet == "vegan" and pairing_diet != "vegan":
                continue
            if any(
                allergen in ingredient or ingredient in allergen
                for allergen in excluded
                for ingredient in ingredients
                if allergen
            ):
                continue
            safe.append(name)
        return " · ".join(safe)

    # ------------------------------------------------------------ recommenders
    def recommend(self, prefs: Preferences, n: int = 10) -> pd.DataFrame:
        """Top-n dishes for the given preferences."""
        mask = self._filter_mask(prefs)
        liked_idx = [
            self._name_to_idx[name.lower()]
            for name in prefs.liked
            if name.lower() in self._name_to_idx
        ]

        candidates = np.flatnonzero(mask)
        if liked_idx:
            profile = np.asarray(self.matrix[liked_idx].mean(axis=0))
            scores = cosine_similarity(profile, self.matrix).ravel()
            candidates = np.array([c for c in candidates if c not in liked_idx], dtype=int)
            order = candidates[np.argsort(-scores[candidates], kind="stable")][:n]
        else:
            # Cold start: nothing liked yet, so show a (fixed-seed) shuffle of what passes the filters.
            scores = np.zeros(len(self.df))
            order = np.random.default_rng(42).permutation(candidates)[:n]

        out = self.df.iloc[order][RESULT_COLUMNS].copy()
        out["pairing"] = [
            self._safe_pairings(value, prefs.diet, prefs.exclude_ingredients)
            for value in out["pairing"]
        ]
        out["match"] = (scores[order] * 100).round(1)
        out["why"] = [self._why(i, liked_idx) for i in order]
        return out.reset_index(drop=True)

    def similar_to(self, dish: str, n: int = 5, prefs: Preferences | None = None) -> pd.DataFrame:
        """Dishes most similar to a single dish (optionally still applying filters)."""
        if dish.lower() not in self._name_to_idx:
            raise KeyError(f"Unknown dish: {dish!r}")
        base = prefs or Preferences()
        return self.recommend(replace(base, liked=[dish]), n=n)

    # --------------------------------------------------------- family logic
    def family_preferences(self, members: list) -> "Preferences":
        """Combine several FamilyMember profiles into one strict Preferences object.

        - diet: the most restrictive diet covers everyone (if anyone is vegan,
          only dishes every vegan-compatible diet allows are kept — in practice
          this means picking the most restrictive diet among members).
        - allergies: union of everyone's allergies (a dish is out if ANY member
          reacts to it).
        - liked: union of everyone's liked dishes, used to build the group's
          taste profile.
        """
        if not members:
            return Preferences()

        diet_rank = {"vegan": 0, "veg": 1, "non-veg": 2}  # lower = more restrictive
        strictest_diet = min((m.diet for m in members), key=lambda d: diet_rank.get(d, 2))

        all_allergies = sorted({a for m in members for a in m.allergies})
        all_liked = [name for m in members for name in m.liked]

        return Preferences(
            diet=strictest_diet,
            liked=all_liked,
            exclude_ingredients=all_allergies,
        )

    def recommend_for_family(
        self, members: list, n: int = 10, cuisine: str | None = None
    ) -> pd.DataFrame:
        """Dishes every single member could eat — the most restrictive diet in
        the family wins. Useful for a one-dish-for-everyone meal, but note this
        hides non-veg options entirely if even one member is veg/vegan; for a
        realistic family spread, use recommend_family_spread() instead."""
        prefs = self.family_preferences(members)
        if cuisine:
            prefs.cuisines = [cuisine]
        return self.recommend(prefs, n=n)

    def recommend_family_spread(
        self, members: list, n: int = 6, cuisine: str | None = None
    ) -> dict:
        """Dishes grouped by each diet present in the family, so a non-veg
        member still gets non-veg suggestions instead of being forced into
        whatever the strictest member in the family eats.

        Allergies are applied GLOBALLY across every group (shared kitchens and
        shared tables mean one member's allergen is usually avoided for
        everyone, for safety).

        Returns {diet: DataFrame}, e.g. {"veg": ..., "non-veg": ...}.
        """
        if not members:
            return {}

        all_allergies = sorted({a for m in members for a in m.allergies})
        groups: dict[str, list] = {}
        for m in members:
            groups.setdefault(m.diet, []).append(m)

        result = {}
        for diet, group_members in groups.items():
            prefs = Preferences(
                diet=diet,
                liked=[name for m in group_members for name in m.liked],
                exclude_ingredients=all_allergies,
                cuisines=[cuisine] if cuisine else [],
            )
            result[diet] = self.recommend(prefs, n=n)
        return result

    def per_member_breakdown(
        self, members: list, n: int = 3, cuisine: str | None = None
    ) -> dict:
        """A few personal picks for each member individually (their own diet/spice/allergies)."""
        result = {}
        for m in members:
            prefs = Preferences(
                diet=m.diet,
                liked=m.liked,
                exclude_ingredients=m.allergies,
                cuisines=[cuisine] if cuisine else [],
            )
            result[m.name] = self.recommend(prefs, n=n)
        return result


if __name__ == "__main__":
    rec = FoodRecommender()
    pd.set_option("display.width", 200, "display.max_columns", None)

    print("Because you liked Butter Chicken and Masala Dosa (vegetarian only):")
    prefs = Preferences(diet="veg", liked=["Butter Chicken", "Masala Dosa"])
    print(rec.recommend(prefs, n=5)[["name", "cuisine", "match", "why"]], "\n")

    print("Dishes similar to Pad Thai:")
    print(rec.similar_to("Pad Thai", n=5)[["name", "cuisine", "match", "why"]])
