"""SQLite storage and account helpers for the family nutrition app."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "nutrition.db"
PASSWORD_ITERATIONS = 310_000


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection



@contextmanager
def _connection():
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    with _connection() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS households (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            invite_code TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            household_id INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            password_salt BLOB NOT NULL,
            password_hash BLOB NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            diet TEXT NOT NULL DEFAULT 'non-veg',
            allergies_json TEXT NOT NULL DEFAULT '[]',
            liked_json TEXT NOT NULL DEFAULT '[]',
            calorie_goal_kcal INTEGER,
            current_weight_kg REAL,
            goal_weight_kg REAL,
            goal_pace TEXT,
            activity_level TEXT,
            age_years INTEGER,
            height_cm REAL,
            calorie_formula TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS users_household_idx ON users(household_id);
        CREATE TABLE IF NOT EXISTS food_entries (
            id TEXT PRIMARY KEY,
            household_id INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            entry_date TEXT NOT NULL,
            meal TEXT NOT NULL,
            food TEXT NOT NULL,
            servings REAL NOT NULL,
            serving_g REAL NOT NULL,
            calories REAL NOT NULL,
            protein_g REAL NOT NULL,
            carbs_g REAL NOT NULL,
            fat_g REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS food_entries_household_date_idx
            ON food_entries(household_id, entry_date);
        CREATE TABLE IF NOT EXISTS family_notes (
            id TEXT PRIMARY KEY,
            household_id INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            entry_date TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS family_notes_household_date_idx
            ON family_notes(household_id, entry_date);
        """)


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )


def register_account(*, display_name: str, username: str, password: str,
                     household_name: str = "", invite_code: str = "") -> dict:
    display_name = display_name.strip()
    username = username.strip().lower()
    if not display_name:
        raise ValueError("Enter your name.")
    if not re.fullmatch(r"[a-z0-9_.-]{3,30}", username):
        raise ValueError("Username must be 3–30 characters: letters, numbers, dot, dash, or underscore.")
    if len(password) < 8:
        raise ValueError("Use a password with at least 8 characters.")

    salt = secrets.token_bytes(16)
    password_hash = _hash_password(password, salt)
    normalized_code = invite_code.strip().upper()
    with _connection() as connection:
        if connection.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            raise ValueError("That username is already in use. Choose another one.")
        if normalized_code:
            household = connection.execute(
                "SELECT id FROM households WHERE invite_code = ?", (normalized_code,)
            ).fetchone()
            if household is None:
                raise ValueError("That family invite code was not found.")
            household_id = household["id"]
            role = "member"
        else:
            if not household_name.strip():
                raise ValueError("Enter a family name, or enter an invite code to join a family.")
            household = connection.execute(
                "INSERT INTO households(name, invite_code) VALUES (?, ?)",
                (household_name.strip(), secrets.token_urlsafe(9).upper()),
            )
            household_id = household.lastrowid
            role = "owner"
        if connection.execute(
            "SELECT 1 FROM users WHERE household_id = ? AND lower(display_name) = lower(?)",
            (household_id, display_name),
        ).fetchone():
            raise ValueError("That name is already used in this family. Choose another display name.")
        cursor = connection.execute(
            """INSERT INTO users(household_id, username, display_name, password_salt,
                password_hash, role) VALUES (?, ?, ?, ?, ?, ?)""",
            (household_id, username, display_name, salt, password_hash, role),
        )
        user_id = cursor.lastrowid
    return get_user(user_id)


def authenticate(username: str, password: str) -> dict | None:
    username = username.strip().lower()
    with _connection() as connection:
        row = connection.execute(
            "SELECT id, password_salt, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if row is None:
        return None
    candidate = _hash_password(password, row["password_salt"])
    if not hmac.compare_digest(candidate, row["password_hash"]):
        return None
    return get_user(row["id"])


def get_user(user_id: int) -> dict | None:
    with _connection() as connection:
        row = connection.execute("""
            SELECT u.*, h.name AS household_name, h.invite_code
            FROM users u JOIN households h ON h.id = u.household_id
            WHERE u.id = ?
        """, (user_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["allergies"] = json.loads(result.pop("allergies_json"))
    result["liked"] = json.loads(result.pop("liked_json"))
    result.pop("password_salt", None)
    result.pop("password_hash", None)
    return result


def list_members(household_id: int) -> list[dict]:
    with _connection() as connection:
        rows = connection.execute("""
            SELECT id, household_id, username, display_name, role, diet,
                allergies_json, liked_json, calorie_goal_kcal, current_weight_kg,
                goal_weight_kg, goal_pace, activity_level, age_years, height_cm,
                calorie_formula
            FROM users WHERE household_id = ? ORDER BY id
        """, (household_id,)).fetchall()
    members = []
    for row in rows:
        member = dict(row)
        member["allergies"] = json.loads(member.pop("allergies_json"))
        member["liked"] = json.loads(member.pop("liked_json"))
        members.append(member)
    return members


def save_profile(user_id: int, *, diet: str, allergies: list[str], liked: list[str],
                 calorie_goal_kcal: int | None, current_weight_kg: float | None,
                 goal_weight_kg: float | None, goal_pace: str | None,
                 activity_level: str | None, age_years: int | None,
                 height_cm: float | None, calorie_formula: str | None) -> dict:
    with _connection() as connection:
        connection.execute("""UPDATE users SET diet = ?, allergies_json = ?, liked_json = ?,
            calorie_goal_kcal = ?, current_weight_kg = ?, goal_weight_kg = ?, goal_pace = ?,
            activity_level = ?, age_years = ?, height_cm = ?, calorie_formula = ?
            WHERE id = ?""", (
            diet, json.dumps(allergies), json.dumps(liked), calorie_goal_kcal,
            current_weight_kg, goal_weight_kg, goal_pace, activity_level,
            age_years, height_cm, calorie_formula, user_id,
        ))
    return get_user(user_id)


def add_food_entry(*, household_id: int, user_id: int, day: date, meal: str,
                   food: str, servings: float, serving_g: float, calories: float,
                   protein_g: float, carbs_g: float, fat_g: float) -> None:
    import uuid
    with _connection() as connection:
        connection.execute("""INSERT INTO food_entries(
            id, household_id, user_id, entry_date, meal, food, servings, serving_g,
            calories, protein_g, carbs_g, fat_g
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
            uuid.uuid4().hex, household_id, user_id, day.isoformat(), meal, food,
            servings, serving_g, round(calories * servings, 1),
            round(protein_g * servings, 1), round(carbs_g * servings, 1),
            round(fat_g * servings, 1),
        ))


def food_entries(household_id: int, day: date) -> list[dict]:
    with _connection() as connection:
        rows = connection.execute("""
            SELECT f.id, f.entry_date AS date, u.display_name AS member,
                u.id AS user_id, f.meal, f.food, f.servings, f.serving_g,
                f.calories, f.protein_g, f.carbs_g, f.fat_g
            FROM food_entries f JOIN users u ON u.id = f.user_id
            WHERE f.household_id = ? AND f.entry_date = ?
            ORDER BY f.created_at, f.id
        """, (household_id, day.isoformat())).fetchall()
    return [dict(row) for row in rows]


def remove_food_entry(entry_id: str, user_id: int) -> bool:
    with _connection() as connection:
        cursor = connection.execute(
            "DELETE FROM food_entries WHERE id = ? AND user_id = ?", (entry_id, user_id)
        )
    return cursor.rowcount > 0


def add_family_note(*, household_id: int, sender_id: int, recipient_id: int,
                    day: date, message: str) -> None:
    import uuid
    with _connection() as connection:
        same_household = connection.execute(
            "SELECT COUNT(*) FROM users WHERE id IN (?, ?) AND household_id = ?",
            (sender_id, recipient_id, household_id),
        ).fetchone()[0]
        if same_household != (1 if sender_id == recipient_id else 2):
            raise ValueError("Choose someone in your family.")
        connection.execute("""INSERT INTO family_notes(
            id, household_id, sender_id, recipient_id, entry_date, message
        ) VALUES (?, ?, ?, ?, ?, ?)""", (
            uuid.uuid4().hex, household_id, sender_id, recipient_id,
            day.isoformat(), message.strip()[:180],
        ))


def family_notes(household_id: int, day: date) -> list[dict]:
    with _connection() as connection:
        rows = connection.execute("""
            SELECT n.id, n.entry_date AS date, s.display_name AS sender,
                r.display_name AS recipient, n.message
            FROM family_notes n
            JOIN users s ON s.id = n.sender_id
            JOIN users r ON r.id = n.recipient_id
            WHERE n.household_id = ? AND n.entry_date = ?
            ORDER BY n.created_at, n.id
        """, (household_id, day.isoformat())).fetchall()
    return [dict(row) for row in rows]
