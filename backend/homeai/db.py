import json
import sqlite3
from pathlib import Path
from .config import get_settings
from .models import EnergyPlan, SecurityEvent


def _connect():
    path = Path(get_settings().database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def initialize():
    with _connect() as con:
        con.execute("CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, body TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, received_at TEXT NOT NULL, body TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS scheduler_runs (local_date TEXT PRIMARY KEY, ran_at TEXT NOT NULL)")


def save_plan(plan: EnergyPlan):
    with _connect() as con:
        con.execute("INSERT OR REPLACE INTO plans VALUES (?, ?, ?)", (plan.id, plan.created_at.isoformat(), plan.model_dump_json()))


def latest_plan() -> EnergyPlan | None:
    with _connect() as con:
        row = con.execute("SELECT body FROM plans ORDER BY created_at DESC LIMIT 1").fetchone()
    return EnergyPlan.model_validate_json(row[0]) if row else None


def save_event(event: SecurityEvent) -> bool:
    with _connect() as con:
        result = con.execute("INSERT OR IGNORE INTO events VALUES (?, ?, ?)", (event.id, event.received_at.isoformat(), event.model_dump_json()))
        return result.rowcount > 0


def recent_events(limit: int = 30) -> list[SecurityEvent]:
    with _connect() as con:
        rows = con.execute("SELECT body FROM events ORDER BY received_at DESC LIMIT ?", (min(limit, 100),)).fetchall()
    return [SecurityEvent.model_validate_json(r[0]) for r in rows]


def claim_scheduler_day(local_date: str, now_iso: str) -> bool:
    with _connect() as con:
        result = con.execute("INSERT OR IGNORE INTO scheduler_runs VALUES (?, ?)", (local_date, now_iso))
        return result.rowcount > 0


def release_scheduler_day(local_date: str):
    with _connect() as con:
        con.execute("DELETE FROM scheduler_runs WHERE local_date = ?", (local_date,))


def recent_plans(limit: int = 20) -> list[EnergyPlan]:
    """Read the newest simulation records without modifying device state."""
    with _connect() as con:
        rows = con.execute("SELECT body FROM plans ORDER BY created_at DESC LIMIT ?", (min(limit, 50),)).fetchall()
    return [EnergyPlan.model_validate_json(row[0]) for row in rows]
