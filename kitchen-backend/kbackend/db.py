"""SQLite storage (BACKEND_SPEC.md section 3). Plain sqlite3, single process."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    table_no TEXT,
    course TEXT,
    status TEXT NOT NULL,              -- submitted | kitchen_ack | preparing | ready | served | canceled
    plates_expected INTEGER NOT NULL DEFAULT 1,
    plated_count INTEGER NOT NULL DEFAULT 0,
    bay_id TEXT,
    dishes TEXT NOT NULL DEFAULT '[]',
    seats TEXT,
    vip INTEGER NOT NULL DEFAULT 0,
    badges TEXT NOT NULL DEFAULT '[]',
    status_source TEXT,
    created_at TEXT NOT NULL,
    ready_at TEXT,
    served_at TEXT,
    served_source TEXT
);
CREATE TABLE IF NOT EXISTS bays (
    id TEXT PRIMARY KEY,
    assigned_ticket_id TEXT,
    assigned_table TEXT,
    assigned_course TEXT,
    last_plate_count INTEGER NOT NULL DEFAULT 0,
    last_seen_at TEXT,
    pickup_unresolved INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS bay_queue (
    ticket_id TEXT PRIMARY KEY,
    queued_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS running_tasks (
    id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    table_no TEXT,
    bay_id TEXT,
    dishes TEXT NOT NULL DEFAULT '[]',
    seats TEXT,
    vip INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,              -- open | claimed | completed | blocked | canceled
    claimed_by TEXT,
    block_reason TEXT,
    created_at TEXT NOT NULL,
    ready_at TEXT,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS zones (
    id TEXT PRIMARY KEY,
    ingredient TEXT NOT NULL,
    on_hand INTEGER NOT NULL DEFAULT 0,
    reserved INTEGER NOT NULL DEFAULT 0,
    last_observed_count INTEGER,
    last_observed_at TEXT
);
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    qty INTEGER NOT NULL,
    status TEXT NOT NULL                -- open | fulfilled | released
);
CREATE TABLE IF NOT EXISTS observations (
    event_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    source TEXT NOT NULL,
    camera_id TEXT,
    observed_at TEXT NOT NULL,
    zone_id TEXT,
    bay_id TEXT,
    confidence REAL,
    status TEXT,
    attribution_ticket_id TEXT,
    attribution_ambiguous INTEGER NOT NULL DEFAULT 0,
    payload TEXT NOT NULL,
    received_at TEXT NOT NULL,
    acted INTEGER NOT NULL DEFAULT 1,  -- 0 = stored but not acted on (e.g. camera obstructed)
    note TEXT
);
CREATE TABLE IF NOT EXISTS inventory_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id TEXT NOT NULL,
    qty_delta INTEGER NOT NULL,
    kind TEXT NOT NULL,                -- pick | return | restock | waste | correction
    ticket_id TEXT,
    source TEXT NOT NULL,              -- cv | staff
    observation_event_id TEXT,
    at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_movement_obs
    ON inventory_movements(observation_event_id) WHERE observation_event_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS review_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    ref TEXT,
    reason TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'open', -- open | resolved
    resolution TEXT,
    resolved_by TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS camera_status (
    camera_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    reason TEXT,
    since TEXT,
    last_heartbeat_at TEXT,
    detected_by TEXT NOT NULL DEFAULT 'cv'  -- cv | system (backend marked it lost from a heartbeat gap)
);
CREATE TABLE IF NOT EXISTS active_ticket (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    ticket_id TEXT NOT NULL,
    set_by TEXT,
    set_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    source TEXT NOT NULL,              -- cv | staff | system
    entity TEXT NOT NULL,
    entity_id TEXT,
    action TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    observation_event_id TEXT
);
CREATE TABLE IF NOT EXISTS counters (
    name TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
"""

JSON_COLS = {"dishes", "seats", "badges", "payload", "data"}


def connect(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if r is None:
        return None
    d = dict(r)
    for k in JSON_COLS & d.keys():
        if isinstance(d[k], str):
            d[k] = json.loads(d[k])
    return d


def rows(rs) -> list[dict[str, Any]]:
    return [row(r) for r in rs]  # type: ignore[misc]
