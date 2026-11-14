"""Kitchen domain logic (BACKEND_SPEC.md sections 4-9).

All state changes go through `Kitchen`. Methods are synchronous and run inside
one SQLite transaction under a process-wide lock; the API layer drains
`changes()` afterwards to fan out to the UI and `context_version` to push
context to CV after the commit (never before).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import jsonschema

from kbackend.config import Settings
from kbackend.db import row, rows

log = logging.getLogger(__name__)

STATUS_RANK = {"submitted": 0, "kitchen_ack": 1, "preparing": 2, "ready": 3, "served": 4, "canceled": 5}
ACTIVE_TICKET_STATES = ("submitted", "kitchen_ack", "preparing", "ready")
FROZEN_CAMERA_STATES = ("obstructed", "lost")


class NotFound(Exception):
    pass


class Conflict(Exception):
    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.detail = detail or {}


class Invalid(Exception):
    pass


def iso(ts: float) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def parse_iso(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _j(v: Any) -> str:
    return json.dumps(v)


class Kitchen:
    def __init__(self, settings: Settings, conn, clock=time.time,
                 plating_camera: str = "plating_cam", ingredient_camera: str = "ingredient_cam") -> None:
        self.s = settings
        self.db = conn
        self.clock = clock
        self.plating_camera = plating_camera
        self.ingredient_camera = ingredient_camera
        self.lock = threading.RLock()
        schema = json.loads(Path(settings.schema_path).read_text())
        self.validator = jsonschema.Draft202012Validator(schema)
        self._touched: dict[str, set[str]] = {}
        self._events_out: list[dict[str, Any]] = []
        self.context_version = 0          # bumps when bays/claims/active-ticket context changes
        self.cv_calls: list[dict[str, Any]] = []  # zone resolves to forward to CV after commit
        self._seed()

    # ------------------------------------------------------------------ infra
    def now(self) -> str:
        return iso(self.clock())

    @contextmanager
    def tx(self) -> Iterator[None]:
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            else:
                self.db.execute("COMMIT")

    def _seed(self) -> None:
        with self.tx():
            for bay_id in self.s.bays:
                self.db.execute("INSERT OR IGNORE INTO bays(id) VALUES (?)", (bay_id,))
            for zid, z in self.s.zones.items():
                self.db.execute("INSERT OR IGNORE INTO zones(id, ingredient, on_hand) VALUES (?,?,?)",
                                (zid, z.ingredient, z.on_hand))

    def _touch(self, kind: str, ident: str | int | None) -> None:
        if ident is not None:
            self._touched.setdefault(kind, set()).add(str(ident))

    def _ctx_changed(self) -> None:
        self.context_version += 1

    def _next_id(self, name: str, fmt: str) -> str:
        cur = self.db.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()
        n = (cur["value"] if cur else 0) + 1
        self.db.execute("INSERT INTO counters(name, value) VALUES (?, ?) "
                        "ON CONFLICT(name) DO UPDATE SET value=excluded.value", (name, n))
        return fmt.format(n)

    def _log(self, source: str, entity: str, entity_id: Any, action: str, data: dict | None = None,
             obs: str | None = None, at: str | None = None) -> None:
        self.db.execute(
            "INSERT INTO event_log(at, source, entity, entity_id, action, data, observation_event_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (at or self.now(), source, entity, None if entity_id is None else str(entity_id), action,
             _j(data or {}), obs))

    def _review(self, kind: str, ref: str | None, reason: str, data: dict | None = None,
                dedupe: bool = False) -> int:
        if dedupe:
            existing = self.db.execute(
                "SELECT id FROM review_items WHERE kind=? AND ref IS ? AND status='open'", (kind, ref)).fetchone()
            if existing:
                self.db.execute("UPDATE review_items SET reason=?, data=? WHERE id=?",
                                (reason, _j(data or {}), existing["id"]))
                self._touch("review", existing["id"])
                return existing["id"]
        cur = self.db.execute(
            "INSERT INTO review_items(kind, ref, reason, data, created_at) VALUES (?,?,?,?,?)",
            (kind, ref, reason, _j(data or {}), self.now()))
        rid = cur.lastrowid
        self._log("system", "review_item", rid, "opened", {"kind": kind, "reason": reason})
        self._touch("review", rid)
        return rid  # type: ignore[return-value]

    # ------------------------------------------------------------ change feed
    def changes(self) -> list[dict[str, Any]]:
        """Drain UI messages for everything touched since the last call."""
        with self.lock:
            touched, self._touched = self._touched, {}
            events, self._events_out = self._events_out, []
            out: list[dict[str, Any]] = [{"kind": "cv_event", "data": e} for e in events]
            for kind, ids in touched.items():
                for ident in sorted(ids):
                    data = self._get(kind, ident)
                    out.append({"kind": kind, "id": ident, "data": data})
            return out

    def _get(self, kind: str, ident: str) -> dict[str, Any] | None:
        if kind == "ticket":
            return self.ticket(ident)
        if kind == "bay":
            return self._bay_view(ident)
        if kind == "task":
            return row(self.db.execute("SELECT * FROM running_tasks WHERE id=?", (ident,)).fetchone())
        if kind == "zone":
            return self._zone_view(ident)
        if kind == "review":
            return row(self.db.execute("SELECT * FROM review_items WHERE id=?", (int(ident),)).fetchone())
        if kind == "camera":
            return self._camera_view(ident)
        if kind == "active_ticket":
            return self.active_ticket()
        return None

    # --------------------------------------------------------------- reads
    def ticket(self, ticket_id: str) -> dict[str, Any] | None:
        return row(self.db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone())

    def _ticket_or_404(self, ticket_id: str) -> dict[str, Any]:
        t = self.ticket(ticket_id)
        if t is None:
            raise NotFound(f"ticket {ticket_id} not found")
        return t

    def _bay(self, bay_id: str) -> dict[str, Any] | None:
        return row(self.db.execute("SELECT * FROM bays WHERE id=?", (bay_id,)).fetchone())

    def _camera(self, camera_id: str) -> dict[str, Any] | None:
        return row(self.db.execute("SELECT * FROM camera_status WHERE camera_id=?", (camera_id,)).fetchone())

    def camera_is_stale(self, camera_id: str) -> bool:
        c = self._camera(camera_id)
        if c is None:
            return True  # never seen live
        if c["state"] in FROZEN_CAMERA_STATES:
            return True
        hb = parse_iso(c["last_heartbeat_at"])
        return hb is None or self.clock() - hb > self.s.cv_stale_after_s

    def _camera_view(self, camera_id: str) -> dict[str, Any] | None:
        c = self._camera(camera_id)
        if c is None:
            return None
        return {**c, "stale": self.camera_is_stale(camera_id)}

    def _bay_view(self, bay_id: str) -> dict[str, Any] | None:
        b = self._bay(bay_id)
        if b is None:
            return None
        t = self.ticket(b["assigned_ticket_id"]) if b["assigned_ticket_id"] else None
        return {**b, "plate_count_stale": self.camera_is_stale(self.plating_camera),
                "plates_expected": t["plates_expected"] if t else None,
                "free": self._bay_is_free(b)}

    def _zone_view(self, zone_id: str) -> dict[str, Any] | None:
        z = row(self.db.execute("SELECT * FROM zones WHERE id=?", (zone_id,)).fetchone())
        if z is None:
            return None
        return {**z, "available": z["on_hand"] - z["reserved"],
                "observed_count_stale": self.camera_is_stale(self.ingredient_camera)}

    def active_ticket(self) -> dict[str, Any] | None:
        return row(self.db.execute("SELECT ticket_id, set_by, set_at FROM active_ticket WHERE id=1").fetchone())

    def state(self) -> dict[str, Any]:
        with self.lock:
            cams = [r["camera_id"] for r in self.db.execute("SELECT camera_id FROM camera_status")]
            return {
                "now": self.now(),
                "config": {"readiness_mode": self.s.readiness_mode,
                           "auto_serve_on_removal": self.s.auto_serve_on_removal,
                           "allocate_on": self.s.allocate_on},
                "tickets": rows(self.db.execute(
                    "SELECT * FROM tickets WHERE status NOT IN ('served','canceled') ORDER BY created_at")),
                "recent_served": rows(self.db.execute(
                    "SELECT * FROM tickets WHERE status='served' ORDER BY served_at DESC LIMIT 20")),
                "bays": [self._bay_view(b) for b in self.s.bays],
                "waiting_for_bay": [r["ticket_id"] for r in self.db.execute(
                    "SELECT ticket_id FROM bay_queue ORDER BY queued_at, rowid")],
                "tasks": self.task_queue(),
                "zones": [self._zone_view(r["id"]) for r in self.db.execute("SELECT id FROM zones ORDER BY id")],
                "cameras": [self._camera_view(c) for c in cams],
                "review_items": self.review_items(),
                "active_ticket": self.active_ticket(),
            }

    def task_queue(self) -> list[dict[str, Any]]:
        """Open/claimed/blocked tasks ranked: hot food ready first (oldest ready_at), then VIP."""
        ts = rows(self.db.execute(
            "SELECT * FROM running_tasks WHERE status IN ('open','claimed','blocked') "
            "ORDER BY ready_at ASC, vip DESC, created_at ASC"))
        now = self.clock()
        for t in ts:
            r = parse_iso(t["ready_at"])
            t["waiting_s"] = None if r is None else round(now - r, 1)
        return ts

    def review_items(self, status: str = "open") -> list[dict[str, Any]]:
        return rows(self.db.execute("SELECT * FROM review_items WHERE status=? ORDER BY id", (status,)))

    def event_log(self, limit: int = 500) -> list[dict[str, Any]]:
        return rows(self.db.execute("SELECT * FROM event_log ORDER BY id DESC LIMIT ?", (limit,)))

    def observations(self, limit: int = 500) -> list[dict[str, Any]]:
        return rows(self.db.execute("SELECT * FROM observations ORDER BY observed_at DESC LIMIT ?", (limit,)))

    # ----------------------------------------------------- context for CV
    def bays_context(self) -> dict[str, Any]:
        with self.lock:
            out: dict[str, Any] = {}
            for b in self.s.bays:
                bay = self._bay(b)
                if bay and bay["assigned_ticket_id"]:
                    t = self.ticket(bay["assigned_ticket_id"])
                    out[b] = {"ticket_id": bay["assigned_ticket_id"], "table": bay["assigned_table"],
                              "course": bay["assigned_course"],
                              "expected_plates": t["plates_expected"] if t else None}
                else:
                    out[b] = None
            return {"bays": out}

    def claims_context(self) -> dict[str, Any]:
        with self.lock:
            claims: dict[str, Any] = {b: None for b in self.s.bays}
            for t in self.db.execute(
                    "SELECT id, bay_id, claimed_by FROM running_tasks WHERE status='claimed' AND bay_id IS NOT NULL"):
                claims[t["bay_id"]] = {"task_id": t["id"], "server_id": t["claimed_by"]}
            return {"claims": claims}

    def active_ticket_context(self) -> dict[str, Any] | None:
        with self.lock:
            return self.active_ticket()

    # ============================================================ CV ingest
    def ingest(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """BACKEND_SPEC 4. Validate, dedup on event_id, store, then act.

        Batches (e.g. a CV outbox flush) are processed in observed_at order.
        """
        valid: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for i, ev in enumerate(events):
            errors = sorted(self.validator.iter_errors(ev), key=lambda e: e.path)
            if errors:
                msg = errors[0].message[:300]
                log.warning("rejecting malformed CV event #%d: %s", i, msg)
                rejected.append({"index": i, "event_id": ev.get("event_id") if isinstance(ev, dict) else None,
                                 "error": msg})
            else:
                valid.append(ev)
        valid.sort(key=lambda e: (parse_iso(e["observed_at"]) or 0.0))
        accepted, duplicates = [], []
        for ev in valid:
            try:
                with self.tx():
                    if not self._store_observation(ev):
                        duplicates.append(ev["event_id"])
                        continue
                    self._handle(ev)
            except Exception as e:
                # a handler bug must not lose the event or the rest of the batch:
                # keep the observation, flagged as not acted on
                log.exception("handler failed for %s %s", ev["type"], ev["event_id"])
                with self.tx():
                    self._store_observation(ev, acted=0, note=f"handler error: {e!r}"[:300])
            accepted.append(ev["event_id"])
            self._events_out.append(ev)
        return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}

    def _store_observation(self, ev: dict[str, Any], acted: int = 1, note: str | None = None) -> bool:
        cur = self.db.execute(
            "INSERT OR IGNORE INTO observations(event_id, type, source, camera_id, observed_at, zone_id, "
            "bay_id, confidence, status, attribution_ticket_id, attribution_ambiguous, payload, received_at, "
            "acted, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ev["event_id"], ev["type"], ev["source"], ev["camera_id"], ev["observed_at"], ev["zone_id"],
             ev["bay_id"], ev["confidence"], ev["status"], ev["attribution"]["ticket_id"],
             int(ev["attribution"]["ambiguous"]), _j(ev["payload"]), self.now(), acted, note))
        return cur.rowcount == 1

    def _handle(self, ev: dict[str, Any]) -> None:
        t = ev["type"]
        if t == "CAMERA_STATUS":
            self._on_camera_status(ev)
            return
        cam = self._camera(ev["camera_id"])
        if cam is not None and cam["state"] in FROZEN_CAMERA_STATES and cam["detected_by"] == "cv":
            log.warning("event %s from %s camera %s: stored, not acted on", t, cam["state"], ev["camera_id"])
            self.db.execute("UPDATE observations SET acted=0, note=? WHERE event_id=?",
                            (f"camera {cam['state']}", ev["event_id"]))
            return
        handler = {
            "BAY_STATE": self._on_bay_state,
            "PLATE_ARRIVED": self._on_plate_arrived,
            "PLATE_REMOVED": self._on_plate_removed,
            "INGREDIENT_PICKED": self._on_ingredient_picked,
            "INGREDIENT_RETURNED": self._on_ingredient_returned,
            "INGREDIENT_CHANGE_PENDING": self._on_ingredient_pending,
            "ZONE_SNAPSHOT": self._on_zone_snapshot,
        }[t]
        handler(ev)

    # ------------------------------------------------------------- cameras
    def _on_camera_status(self, ev: dict[str, Any]) -> None:
        p = ev["payload"]
        cid = ev["camera_id"]
        prev = self._camera(cid)
        if prev and (parse_iso(prev["last_heartbeat_at"]) or 0) > (parse_iso(ev["observed_at"]) or 0):
            return  # older than what we know (outbox flush)
        self.db.execute(
            "INSERT INTO camera_status(camera_id, state, reason, since, last_heartbeat_at, detected_by) "
            "VALUES (?,?,?,?,?,'cv') ON CONFLICT(camera_id) DO UPDATE SET state=excluded.state, "
            "reason=excluded.reason, since=excluded.since, last_heartbeat_at=excluded.last_heartbeat_at, "
            "detected_by='cv'",
            (cid, p["state"], p["reason"], p["since"], ev["observed_at"]))
        if prev is None or prev["state"] != p["state"] or prev["detected_by"] != "cv":
            self._log("cv", "camera", cid, f"state:{p['state']}", {"reason": p["reason"]}, ev["event_id"])
            if prev is not None and prev["state"] in FROZEN_CAMERA_STATES and p["state"] not in FROZEN_CAMERA_STATES:
                # camera came back: CV-derived values are live again
                if cid == self.plating_camera:
                    for b in self.s.bays:
                        self._touch("bay", b)
                else:
                    for r in self.db.execute("SELECT id FROM zones"):
                        self._touch("zone", r["id"])
        self._touch("camera", cid)

    def check_stale(self) -> list[str]:
        """BACKEND_SPEC 9: mark cameras lost after a heartbeat gap. Run periodically."""
        marked = []
        with self.tx():
            for c in rows(self.db.execute("SELECT * FROM camera_status WHERE state != 'lost'")):
                hb = parse_iso(c["last_heartbeat_at"])
                if hb is None or self.clock() - hb > self.s.cv_stale_after_s:
                    self.db.execute("UPDATE camera_status SET state='lost', reason='no_heartbeat', since=?, "
                                    "detected_by='system' WHERE camera_id=?", (self.now(), c["camera_id"]))
                    self._log("system", "camera", c["camera_id"], "state:lost", {"reason": "no_heartbeat"})
                    self._touch("camera", c["camera_id"])
                    if c["camera_id"] == self.plating_camera:
                        for b in self.s.bays:
                            self._touch("bay", b)
                    else:
                        for r in self.db.execute("SELECT id FROM zones"):
                            self._touch("zone", r["id"])
                    marked.append(c["camera_id"])
        return marked

    # ---------------------------------------------------------------- bays
    @staticmethod
    def _bay_is_free(b: dict[str, Any]) -> bool:
        return b["assigned_ticket_id"] is None and b["last_plate_count"] == 0 and not b["pickup_unresolved"]

    def _update_bay_count(self, ev: dict[str, Any], count: int) -> bool:
        """Apply a CV count to a bay if it's not older than what we have. Returns True if applied."""
        b = self._bay(ev["bay_id"])
        if b is None:
            self.db.execute("UPDATE observations SET acted=0, note='unknown bay' WHERE event_id=?",
                            (ev["event_id"],))
            return False
        if b["last_seen_at"] and (parse_iso(b["last_seen_at"]) or 0) > (parse_iso(ev["observed_at"]) or 0):
            return False
        self.db.execute("UPDATE bays SET last_plate_count=?, last_seen_at=? WHERE id=?",
                        (count, ev["observed_at"], ev["bay_id"]))
        self._touch("bay", ev["bay_id"])
        return True

    def _assign_bay(self, bay_id: str, t: dict[str, Any], source: str) -> None:
        self.db.execute("UPDATE bays SET assigned_ticket_id=?, assigned_table=?, assigned_course=? WHERE id=?",
                        (t["id"], t["table_no"], t["course"], bay_id))
        self.db.execute("UPDATE tickets SET bay_id=? WHERE id=?", (bay_id, t["id"]))
        self.db.execute("DELETE FROM bay_queue WHERE ticket_id=?", (t["id"],))
        self._log(source, "bay", bay_id, "assigned", {"ticket_id": t["id"]})
        self._touch("bay", bay_id)
        self._touch("ticket", t["id"])
        self._ctx_changed()

    def _clear_bay(self, bay_id: str, source: str, reason: str, obs: str | None = None) -> None:
        b = self._bay(bay_id)
        if b is None or b["assigned_ticket_id"] is None and not b["pickup_unresolved"]:
            return
        self.db.execute("UPDATE bays SET assigned_ticket_id=NULL, assigned_table=NULL, assigned_course=NULL, "
                        "pickup_unresolved=0 WHERE id=?", (bay_id,))
        self._log(source, "bay", bay_id, "cleared", {"reason": reason, "ticket_id": b["assigned_ticket_id"]}, obs)
        self._touch("bay", bay_id)
        self._ctx_changed()

    def _allocate(self, t: dict[str, Any], source: str = "system") -> str | None:
        if t["bay_id"]:
            return t["bay_id"]
        for bay_id in self.s.bays:
            b = self._bay(bay_id)
            if b and self._bay_is_free(b):
                self._assign_bay(bay_id, t, source)
                return bay_id
        self.db.execute("INSERT OR IGNORE INTO bay_queue(ticket_id, queued_at) VALUES (?,?)", (t["id"], self.now()))
        self._log(source, "ticket", t["id"], "waiting_for_bay")
        self._touch("ticket", t["id"])
        return None

    def _drain_bay_queue(self) -> None:
        for q in rows(self.db.execute("SELECT ticket_id FROM bay_queue ORDER BY queued_at, rowid")):
            t = self.ticket(q["ticket_id"])
            if t is None or t["status"] not in ACTIVE_TICKET_STATES:
                self.db.execute("DELETE FROM bay_queue WHERE ticket_id=?", (q["ticket_id"],))
                continue
            if self._allocate(t) is None:
                return  # no free bay; FIFO order preserved

    def _on_bay_state(self, ev: dict[str, Any]) -> None:
        p = ev["payload"]
        bay_id = ev["bay_id"]
        prev = self._bay(bay_id)
        if not self._update_bay_count(ev, p["plate_count"]):
            return
        assert prev is not None
        if p["plate_count"] != prev["last_plate_count"] and prev["last_seen_at"] is not None:
            # CV saw a change we never got a PLATE_* event for (typically: during an obstruction).
            # Camera-driven automation was frozen, so ask staff instead of guessing.
            if prev["assigned_ticket_id"]:
                self._review("bay_recount", bay_id,
                             f"bay {bay_id} recount {prev['last_plate_count']} -> {p['plate_count']} "
                             f"(ticket {prev['assigned_ticket_id']}); confirm ready/served manually",
                             {"before": prev["last_plate_count"], "after": p["plate_count"],
                              "ticket_id": prev["assigned_ticket_id"], "note": p.get("note")}, dedupe=True)
            elif p["plate_count"] > 0:
                self._review("plate_unassigned_bay", bay_id, f"plate in unassigned bay {bay_id}",
                             {"count": p["plate_count"]}, dedupe=True)
        if p["plate_count"] == 0:
            self._drain_bay_queue()

    # ----------------------------------------------------- ready / served
    def _set_ticket_status(self, t: dict[str, Any], status: str, source: str, obs: str | None = None,
                           force: bool = False) -> bool:
        """Forward-only transitions unless force (staff override). Returns True if changed."""
        if not force and STATUS_RANK[status] <= STATUS_RANK[t["status"]]:
            return False
        now = self.now()
        sets = ["status=?", "status_source=?"]
        args: list[Any] = [status, source]
        if status == "ready":
            sets.append("ready_at=?")
            args.append(now)
        if status == "served":
            sets += ["served_at=?", "served_source=?"]
            args += [now, source]
        self.db.execute(f"UPDATE tickets SET {', '.join(sets)} WHERE id=?", (*args, t["id"]))
        self._log(source, "ticket", t["id"], f"status:{status}", {"from": t["status"]}, obs)
        self._touch("ticket", t["id"])
        t["status"] = status
        return True

    def _badge(self, ticket_id: str, add: str | None = None, remove_prefix: str | None = None) -> None:
        t = self.ticket(ticket_id)
        if t is None:
            return
        badges = [b for b in t["badges"] if not (remove_prefix and b.startswith(remove_prefix))]
        if add and add not in badges:
            badges.append(add)
        self.db.execute("UPDATE tickets SET badges=? WHERE id=?", (_j(badges), ticket_id))
        self._touch("ticket", ticket_id)

    def _make_ready(self, t: dict[str, Any], source: str, obs: str | None = None) -> None:
        if not self._set_ticket_status(t, "ready", source, obs):
            return
        self._badge(t["id"], remove_prefix="partially plated")
        existing = self.db.execute("SELECT id FROM running_tasks WHERE ticket_id=? AND status IN "
                                   "('open','claimed','blocked')", (t["id"],)).fetchone()
        if existing:
            return
        tid = self._next_id("task", "RUN-{}")
        now = self.now()
        self.db.execute(
            "INSERT INTO running_tasks(id, ticket_id, table_no, bay_id, dishes, seats, vip, status, created_at, "
            "ready_at) VALUES (?,?,?,?,?,?,?, 'open', ?, ?)",
            (tid, t["id"], t["table_no"], t["bay_id"], _j(t["dishes"]), _j(t["seats"]), t["vip"], now, now))
        self._log(source, "task", tid, "created", {"ticket_id": t["id"], "bay_id": t["bay_id"]}, obs)
        self._touch("task", tid)

    def _open_task_for(self, ticket_id: str) -> dict[str, Any] | None:
        return row(self.db.execute("SELECT * FROM running_tasks WHERE ticket_id=? AND status IN "
                                   "('open','claimed','blocked') ORDER BY created_at DESC", (ticket_id,)).fetchone())

    def _finish_task(self, ticket_id: str, source: str, obs: str | None = None) -> None:
        task = self._open_task_for(ticket_id)
        if task is None:
            return
        self.db.execute("UPDATE running_tasks SET status='completed', completed_at=? WHERE id=?",
                        (self.now(), task["id"]))
        self._log(source, "task", task["id"], "completed", {"ticket_id": ticket_id}, obs)
        self._touch("task", task["id"])
        if task["status"] == "claimed":
            self._ctx_changed()

    def _serve(self, t: dict[str, Any], source: str, obs: str | None = None, badge: str | None = None) -> None:
        self._set_ticket_status(t, "served", source, obs)
        if badge:
            self._badge(t["id"], add=badge)
        self._finish_task(t["id"], source, obs)

    def _on_plate_arrived(self, ev: dict[str, Any]) -> None:
        p = ev["payload"]
        bay_id = ev["bay_id"]
        bay = self._bay(bay_id)
        if not self._update_bay_count(ev, p["count_after"]):
            return
        assert bay is not None
        if not bay["assigned_ticket_id"]:
            self._review("plate_unassigned_bay", bay_id, f"plate in unassigned bay {bay_id}",
                         {"count": p["count_after"], "event_id": ev["event_id"]}, dedupe=True)
            return
        t = self.ticket(bay["assigned_ticket_id"])
        assert t is not None
        if t["status"] == "served":
            # plates came back after a served: record a correction, never auto-reopen
            self._log("cv", "ticket", t["id"], "plates_returned", {"bay_id": bay_id, "count": p["count_after"]},
                      ev["event_id"])
            self._review("plate_returned", t["id"],
                         f"plates returned to bay {bay_id} after ticket {t['id']} was served",
                         {"bay_id": bay_id, "count": p["count_after"]})
            return
        if t["status"] == "canceled":
            self._review("plate_unassigned_bay", bay_id, f"plate in bay {bay_id} for canceled ticket {t['id']}",
                         {"count": p["count_after"]}, dedupe=True)
            return
        self.db.execute("UPDATE tickets SET plated_count=? WHERE id=?", (p["count_after"], t["id"]))
        self._touch("ticket", t["id"])
        expected = t["plates_expected"]
        full = p["count_after"] >= expected
        if p["count_after"] > expected:
            self._review("extra_plate", bay_id, f"extra plate in bay {bay_id} ({p['count_after']} of {expected})",
                         {"ticket_id": t["id"], "count": p["count_after"]}, dedupe=True)
        if not full:
            self._badge(t["id"], add=f"partially plated ({p['count_after']} of {expected})",
                        remove_prefix="partially plated")
            return
        if self.s.readiness_mode == "auto":
            self._make_ready(t, "cv", ev["event_id"])
        else:
            self._badge(t["id"], add="plated (observed)", remove_prefix="partially plated")
            self._log("cv", "ticket", t["id"], "plated_observed", {"bay_id": bay_id}, ev["event_id"])

    def _on_plate_removed(self, ev: dict[str, Any]) -> None:
        p = ev["payload"]
        bay_id = ev["bay_id"]
        bay = self._bay(bay_id)
        if not self._update_bay_count(ev, p["count_after"]):
            return
        assert bay is not None
        ticket_id = bay["assigned_ticket_id"]
        t = self.ticket(ticket_id) if ticket_id else None
        if t is not None:
            self.db.execute("UPDATE tickets SET plated_count=? WHERE id=?", (p["count_after"], t["id"]))
            self._touch("ticket", t["id"])

        if not p["bay_now_empty"]:
            if t is not None:
                self._badge(t["id"], add=f"partially picked up ({p['count_after']} left)",
                            remove_prefix="partially picked up")
            return
        if t is not None:
            self._badge(t["id"], remove_prefix="partially picked up")

        if t is None:
            self._review("unexplained_removal", bay_id, f"plate removed from unassigned bay {bay_id}",
                         {"event_id": ev["event_id"]})
            self._drain_bay_queue()
            return

        if t["status"] in ("served", "canceled"):
            # served already confirmed (e.g. by staff); the bay is now physically empty
            self._clear_bay(bay_id, "cv", f"emptied after {t['status']}", ev["event_id"])
            self._drain_bay_queue()
            return

        if t["status"] != "ready":
            self._review("unexplained_removal", t["id"],
                         f"plates removed from bay {bay_id} before ticket {t['id']} was ready",
                         {"bay_id": bay_id, "status": t["status"]})
            self.db.execute("UPDATE bays SET pickup_unresolved=1 WHERE id=?", (bay_id,))
            return

        if not p["unclaimed"]:
            self._serve(t, "cv", ev["event_id"])
            self._clear_bay(bay_id, "cv", "served", ev["event_id"])
            self._drain_bay_queue()
            return

        if self.s.auto_serve_on_removal and self.s.readiness_mode == "auto":
            self._serve(t, "cv", ev["event_id"], badge="served, unclaimed pickup")
            self._review("unclaimed_pickup", t["id"],
                         f"ticket {t['id']} picked up from bay {bay_id} with no claim", {"bay_id": bay_id})
            self._clear_bay(bay_id, "cv", "served (unclaimed)", ev["event_id"])
            self._drain_bay_queue()
        else:
            self._review("unexplained_removal", t["id"],
                         f"plate removed from bay {bay_id}, no claim: served?", {"bay_id": bay_id})
            self.db.execute("UPDATE bays SET pickup_unresolved=1 WHERE id=?", (bay_id,))

    # ========================================================= inventory
    def _apply_movement(self, zone_id: str, delta: int, kind: str, source: str, ticket_id: str | None = None,
                        obs: str | None = None) -> None:
        z = self.db.execute("SELECT id FROM zones WHERE id=?", (zone_id,)).fetchone()
        if z is None:
            raise NotFound(f"zone {zone_id} not found")
        self.db.execute(
            "INSERT INTO inventory_movements(zone_id, qty_delta, kind, ticket_id, source, observation_event_id, at) "
            "VALUES (?,?,?,?,?,?,?)", (zone_id, delta, kind, ticket_id, source, obs, self.now()))
        self.db.execute("UPDATE zones SET on_hand = on_hand + ? WHERE id=?", (delta, zone_id))
        self._log(source, "zone", zone_id, kind, {"qty_delta": delta, "ticket_id": ticket_id}, obs)
        self._touch("zone", zone_id)

    def _recompute_reserved(self, zone_id: str) -> None:
        self.db.execute("UPDATE zones SET reserved = (SELECT COALESCE(SUM(qty),0) FROM reservations "
                        "WHERE zone_id=? AND status='open') WHERE id=?", (zone_id, zone_id))
        self._touch("zone", zone_id)

    def _consume_reservation(self, ticket_id: str, zone_id: str, n: int) -> None:
        """Pick of n attributed to ticket: reduce its open reservation (8.2)."""
        remaining = n
        for r in rows(self.db.execute("SELECT * FROM reservations WHERE ticket_id=? AND zone_id=? AND "
                                      "status='open' ORDER BY id", (ticket_id, zone_id))):
            if remaining <= 0:
                break
            take = min(remaining, r["qty"])
            left = r["qty"] - take
            remaining -= take
            self.db.execute("UPDATE reservations SET qty=?, status=? WHERE id=?",
                            (left, "fulfilled" if left == 0 else "open", r["id"]))
        self._recompute_reserved(zone_id)

    def _reopen_reservation(self, ticket_id: str, zone_id: str, n: int) -> None:
        t = self.ticket(ticket_id)
        if t is None or t["status"] in ("served", "canceled"):
            return
        self.db.execute("INSERT INTO reservations(ticket_id, zone_id, qty, status) VALUES (?,?,?, 'open')",
                        (ticket_id, zone_id, n))
        self._recompute_reserved(zone_id)

    def _attributed_ticket(self, ev: dict[str, Any]) -> str | None:
        a = ev["attribution"]
        if a["ambiguous"] or not a["ticket_id"]:
            return None
        return a["ticket_id"] if self.ticket(a["ticket_id"]) else None

    def _on_ingredient_picked(self, ev: dict[str, Any]) -> None:
        p = ev["payload"]
        n = -p["qty_delta"]
        ticket_id = self._attributed_ticket(ev)
        self._apply_movement(ev["zone_id"], -n, "pick", "cv", ticket_id, ev["event_id"])
        self._observe_count(ev["zone_id"], p["count_after"], ev["observed_at"])
        if ticket_id:
            self._consume_reservation(ticket_id, ev["zone_id"], n)
        else:
            self._review("unassigned_movement", ev["event_id"],
                         f"{n} x {p['ingredient']} picked from {ev['zone_id']} with no ticket"
                         + (" (ambiguous)" if ev["attribution"]["ambiguous"] else ""),
                         {"zone_id": ev["zone_id"], "qty": n, "optional": True})

    def _on_ingredient_returned(self, ev: dict[str, Any]) -> None:
        p = ev["payload"]
        ticket_id = self._attributed_ticket(ev)
        self._apply_movement(ev["zone_id"], p["qty_delta"], "return", "cv", ticket_id, ev["event_id"])
        self._observe_count(ev["zone_id"], p["count_after"], ev["observed_at"])
        if ticket_id:
            self._reopen_reservation(ticket_id, ev["zone_id"], p["qty_delta"])

    def _on_ingredient_pending(self, ev: dict[str, Any]) -> None:
        p = ev["payload"]
        self._review("ingredient_change_pending", ev["event_id"],
                     f"{ev['zone_id']}: count changed ({p['reason']}), please confirm",
                     {"zone_id": ev["zone_id"], "ingredient": p["ingredient"], "reason": p["reason"],
                      "count_before": p["count_before"], "count_after_estimate": p["count_after_estimate"],
                      "ticket_id": self._attributed_ticket(ev)})

    def _observe_count(self, zone_id: str, count: int, at: str) -> None:
        self.db.execute("UPDATE zones SET last_observed_count=?, last_observed_at=? WHERE id=? AND "
                        "(last_observed_at IS NULL OR last_observed_at <= ?)", (count, at, zone_id, at))
        self._touch("zone", zone_id)

    def _on_zone_snapshot(self, ev: dict[str, Any]) -> None:
        zid = ev["zone_id"]
        z = self._zone_view(zid)
        if z is None:
            self.db.execute("UPDATE observations SET acted=0, note='unknown zone' WHERE event_id=?",
                            (ev["event_id"],))
            return
        count = ev["payload"]["count"]
        self._observe_count(zid, count, ev["observed_at"])
        if abs(count - z["on_hand"]) > self.s.zone_count_tolerance:
            self._review("zone_mismatch", zid, f"zone {zid} reads {count}, recorded {z['on_hand']}",
                         {"zone_id": zid, "observed": count, "recorded": z["on_hand"]}, dedupe=True)

    # ======================================================= staff actions
    def create_ticket(self, table: str | None, course: str | None = None, plates_expected: int = 1,
                      dishes: list[str] | None = None, seats: list[Any] | None = None, vip: bool = False,
                      ticket_id: str | None = None) -> dict[str, Any]:
        if plates_expected < 1:
            raise Invalid("plates_expected must be >= 1")
        dishes = dishes or []
        for d in dishes:
            if self.s.recipes and d not in self.s.recipes:
                log.info("dish %s has no recipe; no reservations made", d)
        with self.tx():
            tid = ticket_id or self._next_id("ticket", "T-{:04d}")
            if self.ticket(tid):
                raise Conflict(f"ticket {tid} exists")
            self.db.execute(
                "INSERT INTO tickets(id, table_no, course, status, plates_expected, dishes, seats, vip, "
                "status_source, created_at) VALUES (?,?,?, 'submitted', ?,?,?,?, 'staff', ?)",
                (tid, table, course, plates_expected, _j(dishes), _j(seats), int(vip), self.now()))
            self._log("staff", "ticket", tid, "submitted", {"table": table, "dishes": dishes})
            zones_touched = set()
            for d in dishes:
                for line in self.s.recipes.get(d, []):
                    self.db.execute("INSERT INTO reservations(ticket_id, zone_id, qty, status) "
                                    "VALUES (?,?,?, 'open')", (tid, line.zone, line.qty))
                    zones_touched.add(line.zone)
            for z in zones_touched:
                self._recompute_reserved(z)
            t = self.ticket(tid)
            assert t is not None
            if self.s.allocate_on == "submit":
                self._allocate(t)
            self._touch("ticket", tid)
        return self.ticket(tid)  # type: ignore[return-value]

    def advance_ticket(self, ticket_id: str, status: str, source: str = "staff") -> dict[str, Any]:
        """kitchen_ack / preparing (from the order/voice flow)."""
        if status not in ("kitchen_ack", "preparing"):
            raise Invalid("use /ready or /served for those states")
        with self.tx():
            t = self._ticket_or_404(ticket_id)
            self._set_ticket_status(t, status, source)
        return self.ticket(ticket_id)  # type: ignore[return-value]

    def cooking_complete(self, ticket_id: str, source: str = "staff") -> dict[str, Any]:
        """allocate_on=cooking_complete: allocate the bay when the order is about to be plated."""
        with self.tx():
            t = self._ticket_or_404(ticket_id)
            if t["status"] not in ACTIVE_TICKET_STATES:
                raise Conflict(f"ticket is {t['status']}")
            self._log(source, "ticket", ticket_id, "cooking_complete")
            self._allocate(t, source)
        return self.ticket(ticket_id)  # type: ignore[return-value]

    def declare_ready(self, ticket_id: str, source: str = "staff") -> dict[str, Any]:
        """Cook declares ready by voice/tap: confirm mode, or the manual fallback. Always works."""
        with self.tx():
            t = self._ticket_or_404(ticket_id)
            if t["status"] in ("served", "canceled"):
                raise Conflict(f"ticket is {t['status']}")
            self._make_ready(t, source)
        return self.ticket(ticket_id)  # type: ignore[return-value]

    def confirm_served(self, ticket_id: str, server_id: str | None = None, source: str = "staff") -> dict[str, Any]:
        """Server confirms served. Always works; overrides a camera-derived served."""
        with self.tx():
            t = self._ticket_or_404(ticket_id)
            if t["status"] == "canceled":
                raise Conflict("ticket is canceled")
            if t["status"] == "served":
                if t["served_source"] != "staff":
                    self.db.execute("UPDATE tickets SET served_source='staff', status_source='staff' WHERE id=?",
                                    (ticket_id,))
                    self._log(source, "ticket", ticket_id, "served_confirmed",
                              {"overrides": t["served_source"], "server_id": server_id})
                    self._badge(ticket_id, remove_prefix="served, unclaimed")
            else:
                self._serve(t, source)
                self._log(source, "ticket", ticket_id, "served_confirmed", {"server_id": server_id})
            # Bay clears here only if CV already reports it empty; otherwise the
            # next PLATE_REMOVED to empty clears it.
            if t["bay_id"]:
                b = self._bay(t["bay_id"])
                if b and b["assigned_ticket_id"] == ticket_id and b["last_plate_count"] == 0:
                    self._clear_bay(t["bay_id"], source, "served (staff)")
                    self._drain_bay_queue()
                elif b and b["pickup_unresolved"] and b["assigned_ticket_id"] == ticket_id:
                    self.db.execute("UPDATE bays SET pickup_unresolved=0 WHERE id=?", (t["bay_id"],))
                    self._touch("bay", t["bay_id"])
        return self.ticket(ticket_id)  # type: ignore[return-value]

    def cancel_ticket(self, ticket_id: str, source: str = "staff") -> dict[str, Any]:
        with self.tx():
            t = self._ticket_or_404(ticket_id)
            if t["status"] in ("served", "canceled"):
                raise Conflict(f"ticket is {t['status']}")
            self._set_ticket_status(t, "canceled", source)
            zones = [r["zone_id"] for r in self.db.execute(
                "SELECT DISTINCT zone_id FROM reservations WHERE ticket_id=? AND status='open'", (ticket_id,))]
            self.db.execute("UPDATE reservations SET status='released' WHERE ticket_id=? AND status='open'",
                            (ticket_id,))
            for z in zones:
                self._recompute_reserved(z)
            task = self._open_task_for(ticket_id)
            if task:
                self.db.execute("UPDATE running_tasks SET status='canceled' WHERE id=?", (task["id"],))
                self._touch("task", task["id"])
                self._ctx_changed()
            self.db.execute("DELETE FROM bay_queue WHERE ticket_id=?", (ticket_id,))
            if t["bay_id"]:
                b = self._bay(t["bay_id"])
                if b and b["assigned_ticket_id"] == ticket_id and b["last_plate_count"] == 0:
                    self._clear_bay(t["bay_id"], source, "ticket canceled")
                    self._drain_bay_queue()
            if self.active_ticket() and self.active_ticket()["ticket_id"] == ticket_id:  # type: ignore[index]
                self.db.execute("DELETE FROM active_ticket")
                self._touch("active_ticket", "1")
                self._ctx_changed()
        return self.ticket(ticket_id)  # type: ignore[return-value]

    # ---- tasks ----
    def _task_or_404(self, task_id: str) -> dict[str, Any]:
        t = row(self.db.execute("SELECT * FROM running_tasks WHERE id=?", (task_id,)).fetchone())
        if t is None:
            raise NotFound(f"task {task_id} not found")
        return t

    def claim_task(self, task_id: str, server_id: str) -> dict[str, Any]:
        with self.tx():
            task = self._task_or_404(task_id)
            if task["status"] == "claimed":
                if task["claimed_by"] == server_id:
                    return task  # idempotent repeat
                raise Conflict("already claimed", {"claimed_by": task["claimed_by"]})
            if task["status"] != "open":
                raise Conflict(f"task is {task['status']}")
            self.db.execute("UPDATE running_tasks SET status='claimed', claimed_by=? WHERE id=?",
                            (server_id, task_id))
            self._log("staff", "task", task_id, "claimed", {"server_id": server_id})
            self._touch("task", task_id)
            self._ctx_changed()
        return self._task_or_404(task_id)

    def release_task(self, task_id: str, server_id: str | None = None) -> dict[str, Any]:
        with self.tx():
            task = self._task_or_404(task_id)
            if task["status"] not in ("claimed", "blocked"):
                raise Conflict(f"task is {task['status']}")
            self.db.execute("UPDATE running_tasks SET status='open', claimed_by=NULL, block_reason=NULL "
                            "WHERE id=?", (task_id,))
            self._log("staff", "task", task_id, "released", {"server_id": server_id})
            self._touch("task", task_id)
            self._ctx_changed()
        return self._task_or_404(task_id)

    def block_task(self, task_id: str, reason: str | None = None) -> dict[str, Any]:
        with self.tx():
            task = self._task_or_404(task_id)
            if task["status"] not in ("open", "claimed"):
                raise Conflict(f"task is {task['status']}")
            self.db.execute("UPDATE running_tasks SET status='blocked', block_reason=? WHERE id=?",
                            (reason, task_id))
            self._log("staff", "task", task_id, "blocked", {"reason": reason})
            self._touch("task", task_id)
            if task["status"] == "claimed":
                self._ctx_changed()
        return self._task_or_404(task_id)

    def complete_task(self, task_id: str, server_id: str | None = None) -> dict[str, Any]:
        """Server marks the run done: same as confirming served for its ticket."""
        task = self._task_or_404(task_id)
        if task["status"] in ("completed", "canceled"):
            raise Conflict(f"task is {task['status']}")
        self.confirm_served(task["ticket_id"], server_id or task["claimed_by"])
        return self._task_or_404(task_id)

    # ---- active ticket ----
    def set_active_ticket(self, ticket_id: str, set_by: str | None = None) -> dict[str, Any]:
        with self.tx():
            t = self._ticket_or_404(ticket_id)
            if t["status"] not in ACTIVE_TICKET_STATES:
                raise Conflict(f"ticket is {t['status']}")
            self.db.execute("INSERT INTO active_ticket(id, ticket_id, set_by, set_at) VALUES (1,?,?,?) "
                            "ON CONFLICT(id) DO UPDATE SET ticket_id=excluded.ticket_id, set_by=excluded.set_by, "
                            "set_at=excluded.set_at", (ticket_id, set_by, self.now()))
            self._log("staff", "active_ticket", ticket_id, "set", {"set_by": set_by})
            self._touch("active_ticket", "1")
            self._ctx_changed()
        return self.active_ticket()  # type: ignore[return-value]

    def clear_active_ticket(self) -> None:
        with self.tx():
            if self.active_ticket() is None:
                return
            self.db.execute("DELETE FROM active_ticket")
            self._log("staff", "active_ticket", None, "cleared")
            self._touch("active_ticket", "1")
            self._ctx_changed()

    # ---- bay override ----
    def override_bay(self, bay_id: str, action: str, ticket_id: str | None = None,
                     staff_id: str | None = None, confirm: bool = False) -> dict[str, Any]:
        """Staff-forced clear or reassign. Requires confirm=True ("are you sure"). Logged."""
        if not confirm:
            raise Invalid("override requires confirm=true")
        with self.tx():
            b = self._bay(bay_id)
            if b is None:
                raise NotFound(f"bay {bay_id} not found")
            data = {"staff_id": staff_id, "plate_count": b["last_plate_count"], "previous": b["assigned_ticket_id"]}
            if b["assigned_ticket_id"]:
                self.db.execute("UPDATE tickets SET bay_id=NULL WHERE id=?", (b["assigned_ticket_id"],))
                self._touch("ticket", b["assigned_ticket_id"])
            self.db.execute("UPDATE bays SET assigned_ticket_id=NULL, assigned_table=NULL, assigned_course=NULL, "
                            "pickup_unresolved=0 WHERE id=?", (bay_id,))
            self._log("staff", "bay", bay_id, f"override:{action}", data | {"ticket_id": ticket_id})
            self._touch("bay", bay_id)
            self._ctx_changed()
            if action == "reassign":
                if not ticket_id:
                    raise Invalid("reassign needs ticket_id")
                t = self._ticket_or_404(ticket_id)
                if t["bay_id"]:
                    old = t["bay_id"]
                    self.db.execute("UPDATE bays SET assigned_ticket_id=NULL, assigned_table=NULL, "
                                    "assigned_course=NULL WHERE id=?", (old,))
                    self._touch("bay", old)
                    t["bay_id"] = None
                self._assign_bay(bay_id, t, "staff")
            elif action != "clear":
                raise Invalid("action must be clear or reassign")
            if b["last_plate_count"] == 0:
                self._drain_bay_queue()
        return self._bay_view(bay_id)  # type: ignore[return-value]

    # ---- inventory staff actions ----
    def restock(self, zone_id: str, qty: int, staff_id: str | None = None) -> dict[str, Any]:
        if qty <= 0:
            raise Invalid("qty must be > 0")
        with self.tx():
            self._apply_movement(zone_id, qty, "restock", "staff")
            self._queue_cv_resolve(zone_id)
        return self._zone_view(zone_id)  # type: ignore[return-value]

    def waste(self, zone_id: str, qty: int, staff_id: str | None = None) -> dict[str, Any]:
        if qty <= 0:
            raise Invalid("qty must be > 0")
        with self.tx():
            self._apply_movement(zone_id, -qty, "waste", "staff")
            self._queue_cv_resolve(zone_id)
        return self._zone_view(zone_id)  # type: ignore[return-value]

    def correct(self, zone_id: str, count: int, staff_id: str | None = None) -> dict[str, Any]:
        if count < 0:
            raise Invalid("count must be >= 0")
        with self.tx():
            z = self._zone_view(zone_id)
            if z is None:
                raise NotFound(f"zone {zone_id} not found")
            if count != z["on_hand"]:
                self._apply_movement(zone_id, count - z["on_hand"], "correction", "staff")
            self._queue_cv_resolve(zone_id, count)
            self._close_zone_mismatch(zone_id, f"corrected to {count}", staff_id)
        return self._zone_view(zone_id)  # type: ignore[return-value]

    def _queue_cv_resolve(self, zone_id: str, count: int | None = None) -> None:
        if count is None:
            z = self.db.execute("SELECT on_hand FROM zones WHERE id=?", (zone_id,)).fetchone()
            count = z["on_hand"]
        # latest wins per zone
        self.cv_calls = [c for c in self.cv_calls if c["zone_id"] != zone_id]
        self.cv_calls.append({"zone_id": zone_id, "count": max(0, count)})

    def _close_zone_mismatch(self, zone_id: str, resolution: str, staff_id: str | None) -> None:
        for r in self.db.execute("SELECT id FROM review_items WHERE kind='zone_mismatch' AND ref=? AND "
                                 "status='open'", (zone_id,)).fetchall():
            self.db.execute("UPDATE review_items SET status='resolved', resolution=?, resolved_by=?, "
                            "resolved_at=? WHERE id=?", (resolution, staff_id, self.now(), r["id"]))
            self._touch("review", r["id"])

    # ---- review items ----
    def resolve_review(self, item_id: int, resolution: str, count: int | None = None,
                       staff_id: str | None = None, ticket_id: str | None = None) -> dict[str, Any]:
        if resolution not in ("accept", "reject", "correct"):
            raise Invalid("resolution must be accept, reject or correct")
        with self.tx():
            item = row(self.db.execute("SELECT * FROM review_items WHERE id=?", (item_id,)).fetchone())
            if item is None:
                raise NotFound(f"review item {item_id} not found")
            if item["status"] == "resolved":
                return item  # idempotent
            d = item["data"]
            kind = item["kind"]
            if kind == "ingredient_change_pending":
                zid = d["zone_id"]
                if resolution == "accept":
                    est = d.get("count_after_estimate")
                    if est is None:
                        raise Invalid("no estimate to accept; use correct with a count")
                    delta = est - d["count_before"]
                    self._apply_movement(zid, delta, "pick" if delta < 0 else "return", "staff",
                                         d.get("ticket_id"), None)
                    if d.get("ticket_id") and delta < 0:
                        self._consume_reservation(d["ticket_id"], zid, -delta)
                    self._queue_cv_resolve(zid, est)
                elif resolution == "correct":
                    if count is None:
                        raise Invalid("correct needs count")
                    z = self._zone_view(zid)
                    assert z is not None
                    if count != z["on_hand"]:
                        self._apply_movement(zid, count - z["on_hand"], "correction", "staff")
                    self._queue_cv_resolve(zid, count)
                else:  # reject: nothing physically changed; reset CV to its pre-change baseline
                    self._queue_cv_resolve(zid, d["count_before"])
            elif kind == "zone_mismatch":
                zid = d["zone_id"]
                if resolution == "accept":  # trust the camera
                    z = self._zone_view(zid)
                    assert z is not None
                    self._apply_movement(zid, d["observed"] - z["on_hand"], "correction", "staff")
                    self._queue_cv_resolve(zid, d["observed"])
                elif resolution == "correct":
                    if count is None:
                        raise Invalid("correct needs count")
                    z = self._zone_view(zid)
                    assert z is not None
                    if count != z["on_hand"]:
                        self._apply_movement(zid, count - z["on_hand"], "correction", "staff")
                    self._queue_cv_resolve(zid, count)
                else:  # trust the record; re-baseline CV to it
                    self._queue_cv_resolve(zid)
            elif kind == "unassigned_movement" and resolution == "accept" and ticket_id:
                mv = self.db.execute("SELECT * FROM inventory_movements WHERE observation_event_id=?",
                                     (item["ref"],)).fetchone()
                if mv is not None:
                    self.db.execute("UPDATE inventory_movements SET ticket_id=? WHERE id=?", (ticket_id, mv["id"]))
                    self._consume_reservation(ticket_id, mv["zone_id"], -mv["qty_delta"])
                    self._log("staff", "zone", mv["zone_id"], "movement_assigned", {"ticket_id": ticket_id})
            elif kind in ("unexplained_removal", "unclaimed_pickup") and resolution == "accept":
                tid = item["ref"] if self.ticket(item["ref"] or "") else None
                if tid:
                    self._resolve_served_review(tid, staff_id)
                elif d.get("bay_id"):
                    self.db.execute("UPDATE bays SET pickup_unresolved=0 WHERE id=?", (d["bay_id"],))
                    self._touch("bay", d["bay_id"])
            self.db.execute("UPDATE review_items SET status='resolved', resolution=?, resolved_by=?, resolved_at=? "
                            "WHERE id=?", (resolution if count is None else f"{resolution}:{count}", staff_id,
                                           self.now(), item_id))
            self._log("staff", "review_item", item_id, f"resolved:{resolution}", {"count": count, "kind": kind})
            self._touch("review", item_id)
        return row(self.db.execute("SELECT * FROM review_items WHERE id=?", (item_id,)).fetchone())  # type: ignore

    def _resolve_served_review(self, ticket_id: str, staff_id: str | None) -> None:
        t = self.ticket(ticket_id)
        assert t is not None
        if t["status"] != "served":
            self._serve(t, "staff")
        else:
            self.db.execute("UPDATE tickets SET served_source='staff' WHERE id=?", (ticket_id,))
            self._badge(ticket_id, remove_prefix="served, unclaimed")
        if t["bay_id"]:
            b = self._bay(t["bay_id"])
            if b and b["assigned_ticket_id"] == ticket_id:
                self.db.execute("UPDATE bays SET pickup_unresolved=0 WHERE id=?", (t["bay_id"],))
                if b["last_plate_count"] == 0:
                    self._clear_bay(t["bay_id"], "staff", "served (review)")
                    self._drain_bay_queue()
                self._touch("bay", t["bay_id"])
