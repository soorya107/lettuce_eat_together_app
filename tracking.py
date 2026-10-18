"""Legacy JSON storage retained for older project versions.

The current Streamlit app stores accounts, food entries, and family notes in
SQLite through database.py. This module is not used by the current app.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from uuid import uuid4

DATA_DIR = Path(__file__).parent / "data"
LOG_PATH = DATA_DIR / "food_log.json"
SUPPORT_PATH = DATA_DIR / "family_support.json"


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _save(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")


class FoodDiary:
    def __init__(self, path: Path = LOG_PATH):
        self.path = path

    def entries(self, day: date) -> list[dict]:
        date_key = day.isoformat()
        return [e for e in _load(self.path) if e.get("date") == date_key]

    def add(self, *, day: date, member: str, meal: str, food: str,
            servings: float, serving_g: float, calories: float,
            protein_g: float, carbs_g: float, fat_g: float) -> None:
        records = _load(self.path)
        records.append({
            "id": uuid4().hex,
            "date": day.isoformat(),
            "member": member,
            "meal": meal,
            "food": food,
            "servings": servings,
            "serving_g": serving_g,
            "calories": round(calories * servings, 1),
            "protein_g": round(protein_g * servings, 1),
            "carbs_g": round(carbs_g * servings, 1),
            "fat_g": round(fat_g * servings, 1),
        })
        _save(self.path, records)

    def remove(self, entry_id: str) -> None:
        _save(self.path, [e for e in _load(self.path) if e.get("id") != entry_id])


class FamilySupport:
    def __init__(self, path: Path = SUPPORT_PATH):
        self.path = path

    def for_day(self, day: date) -> list[dict]:
        date_key = day.isoformat()
        return [n for n in _load(self.path) if n.get("date") == date_key]

    def add(self, *, day: date, sender: str, recipient: str, message: str) -> None:
        records = _load(self.path)
        records.append({
            "id": uuid4().hex,
            "date": day.isoformat(),
            "sender": sender,
            "recipient": recipient,
            "message": message.strip()[:180],
        })
        _save(self.path, records)
