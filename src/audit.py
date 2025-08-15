from pathlib import Path
import sqlite3, datetime, uuid
from typing import Dict, Tuple

from collections.abc import Iterable

DB_PATH = Path("data/cc_audit.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  ts       TEXT NOT NULL,
  run_id   TEXT NOT NULL,
  version  TEXT NOT NULL,
  regime   TEXT NOT NULL,
  doc      TEXT NOT NULL,
  rule_id  TEXT NOT NULL,
  label    TEXT NOT NULL,
  severity TEXT NOT NULL,
  snippet  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_run    ON events(run_id);
CREATE INDEX IF NOT EXISTS idx_events_doc    ON events(doc);
CREATE INDEX IF NOT EXISTS idx_events_regime ON events(regime);
CREATE INDEX IF NOT EXISTS idx_events_rule   ON events(rule_id);
"""


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as cx:
        cx.executescript(SCHEMA)


def new_run_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def write_events(rows: Iterable[dict], regime: str, version: str, run_id: str) -> tuple[int, str]:
    """Persist findings to SQLite; returns (count, db_path)."""
    init_db()
    ts = now_iso()

    # 🔧 MATERIAL FIX: realize the iterable once so we can both insert and count
    rows_list = list(rows)

    with sqlite3.connect(DB_PATH) as cx:
        cx.executemany(
            """
            INSERT INTO events (ts, run_id, version, regime, doc, rule_id, label, severity, snippet)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    ts,
                    run_id,
                    version,
                    regime,
                    r.get("doc", ""),
                    r.get("rule_id", ""),
                    r.get("label", ""),
                    r.get("severity", "info"),
                    r.get("snippet", ""),
                )
                for r in rows_list
            ],
        )
    return (len(rows_list), str(DB_PATH))
