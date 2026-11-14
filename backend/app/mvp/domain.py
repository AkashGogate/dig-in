"""MVP v2 single-process authority; all state and outbox enqueue share a lock.

Network analytics drains elsewhere. Operational state/receipts/outbox are memory
only; v1 coordination is a frozen separate demo, never a second MVP authority.
"""

from __future__ import annotations

import copy
import hashlib
import threading
from uuid import uuid4

from app.analytics.events import CanonicalEvent
from app.analytics.outbox import Outbox
from app.coordination.rules import Conflict, require
from app.mvp import contracts as c
from app.mvp.fixtures import seed
from app.mvp.voice import parse_kitchen, parse_order


class Restaurant:
    def __init__(self, menu=None, outbox=None):
        self.state = seed(menu)
        self.lock = threading.RLock()
        self.outbox = outbox or Outbox()
        self.sessions = {}
        self.receipts = {}
        self.waiting = []

    def session(self, actor_id):
        with self.lock:
            require(actor_id in self.state.actors, "Unknown demo actor")
            token = str(uuid4())
            self.sessions[token] = actor_id
            return {
                "session_id": token,
                "actor": self.state.actors[actor_id].model_dump(),
            }

    def execute(self, command: c.Command, session_id: str):
        with self.lock:
            require(session_id in self.sessions, "Select a demo staff/device session")
            actor = self.state.actors[self.sessions[session_id]]
            fingerprint = hashlib.sha256(
                (actor.id + command.model_dump_json()).encode()
            ).hexdigest()
            if command.event_id in self.receipts:
                old, result = self.receipts[command.event_id]
                require(
                    old == fingerprint,
                    "event_id reused with different content/identity",
                )
                return {
                    "result": copy.deepcopy(result),
                    "state": self.snapshot(),
                    "replayed": True,
                }
            require(
                all(x.event_id != command.event_id for x in self.state.events),
                "event_id collides with a derived event",
            )
            before, waiting = self.state.model_copy(deep=True), self.waiting[:]
            self._current, self._actor, self._received = command, actor, c.now()
            self._pending = []
            try:
                result = self._apply(command.payload)
                self.outbox.enqueue(
                    self._pending
                )  # local memory only, never adapter I/O
                self.state.events.extend(self._pending)
                self.receipts[command.event_id] = (fingerprint, copy.deepcopy(result))
            except Exception:
                self.state, self.waiting = before, waiting
                raise
            finally:
                self._pending = []
                self._current = None  # do not retain a voice capture command/text
                self._actor = None
            return {"result": result, "state": self.snapshot(), "replayed": False}

    def _emit(
        self,
        event_type,
        order_id=None,
        dish_id=None,
        payload=None,
        *,
        derived=False,
        outcome="accepted",
        source=None,
    ):
        e = self._current
        key = (
            f"{e.event_id}:{event_type}:{hashlib.sha256(str(dish_id or order_id or len(self._pending)).encode()).hexdigest()[:16]}"
            if derived
            else e.event_id
        )
        # One input can produce several facts; only its primary fact uses its ID.
        if any(x.event_id == key for x in self._pending):
            key += f":{len(self._pending)}"
        self._pending.append(
            CanonicalEvent(
                event_id=key,
                order_id=order_id,
                dish_id=dish_id,
                type=event_type,
                source=source or ("system" if derived else e.source),
                actor="core" if derived else (e.device_id or self._actor.id),
                time=e.time,
                received_at=self._received,
                run_id=e.run_id,
                simulated=e.simulated,
                outcome=outcome,
                payload=payload or {},
            )
        )

    def _kitchen(self):
        require(self._actor.role in ("cook", "lead"), "Kitchen/lead session required")

    def _order(self, key):
        require(key in self.state.orders, "Unknown order")
        return self.state.orders[key]

    def _draft(self, p):
        order = self._order(p.order_id)
        require(order.owner == self._actor.id, "Only draft owner may edit/send")
        require(
            order.status == "draft" and order.revision == p.revision,
            "Stale draft; refresh and review",
        )
        return order

    def _line(self, value):
        item = self.state.menu.item(value.menu_id)
        require(item is not None, "Unknown menu ID; choose a configured item")
        require(
            set(value.modifiers) <= {m.id for m in item.modifiers},
            "Unknown modifier ID",
        )
        return c.Line(
            **value.model_dump(),
            item_name=item.name,
            station=item.station,
            typical_minutes=item.typical_minutes,
            recipe=None
            if item.recipe is None
            else [x.model_dump() for x in item.recipe],
            price_cents=item.price_cents,
        )

    def _dishes(self, order):
        return [d for d in self.state.dishes.values() if d.order_id == order.id]

    def _validate_table(self, table_id):
        require(table_id in self.state.tables, "Choose a configured table")

    def _fallback(self, dish, reason=None):
        zone = self.state.zones.get(dish.zone_id)
        camera = self.state.cameras[zone.camera_id] if zone else None
        return {
            "automation_available": camera.status == "ok" if camera else None,
            "fallback_reason": reason,
        }

    def _apply(self, p):
        s, e = self.state, self._current
        if isinstance(p, c.StartOrder):
            require(
                self._actor.role in ("server", "lead") and e.source == "tap",
                "Start an order by tap as server",
            )
            self._validate_table(p.table_id)
            order = c.Order(
                id=e.event_id,
                owner=self._actor.id,
                table_id=p.table_id,
                created_at=e.time,
            )
            s.orders[order.id] = order
            self._emit("draft.created", order.id, payload={"table_id": order.table_id})
            return {"order_id": order.id}
        if isinstance(p, c.EditDraft):
            require(e.source == "tap", "Manual review edits require tap source")
            order = self._draft(p)
            self._validate_table(p.table_id)
            require(
                len({x.id for x in p.lines}) == len(p.lines), "Line IDs must be unique"
            )
            require(
                all(
                    x.seat is None or x.seat in s.tables[p.table_id].seats
                    for x in p.lines
                ),
                "Seat is not at this table",
            )
            order.table_id, order.lines = p.table_id, [self._line(x) for x in p.lines]
            order.revision += 1
            self._emit(
                "draft.updated",
                order.id,
                payload={"line_count": len(order.lines), "revision": order.revision},
            )
            return {"revision": order.revision}
        if isinstance(p, c.CaptureVoice):
            require(
                e.source == "voice", "Capture must be an explicit voice-adapter action"
            )
            order = self._draft(p)
            parsed = parse_order(s.menu, p.text, order.table_id)
            order.lines = [
                self._line(c.LineInput(id=f"{e.event_id}:line:{n}", **value))
                for n, value in enumerate(parsed["lines"])
            ]
            order.voice_baseline = copy.deepcopy(order.lines)
            order.initial_voice_draft_line_count = len(order.lines)
            order.capture_mode = "mock_voice"  # no live STT wired in this scaffold
            order.flags = [
                c.DraftFlag(
                    id=f"{e.event_id}:flag:{n}",
                    code=f["code"],
                    message=f["message"],
                    candidates=f.get("candidates", []),
                    spoken_table_id=parsed.get("table_id")
                    if f["code"] == "table_mismatch"
                    else None,
                )
                for n, f in enumerate(parsed["flags"])
            ]
            if parsed.get("table_mismatch") and not any(
                f.code == "table_mismatch" for f in order.flags
            ):
                order.flags.append(
                    c.DraftFlag(
                        id=f"{e.event_id}:table",
                        code="table_mismatch",
                        message="Spoken table differs; explicitly resolve before sending",
                        spoken_table_id=parsed.get("table_id"),
                    )
                )
            order.revision += 1
            self._emit(
                "draft.updated",
                order.id,
                payload={
                    "capture_mode": order.capture_mode,
                    "initial_voice_draft_line_count": len(order.lines),
                    "flag_codes": [f.code for f in order.flags],
                    "revision": order.revision,
                },
            )
            return {
                "revision": order.revision,
                "flags": [f.model_dump() for f in order.flags],
            }
        if isinstance(p, c.ResolveFlag):
            require(e.source == "tap", "Resolve flags explicitly by tap")
            order = self._draft(p)
            flag = next((f for f in order.flags if f.id == p.flag_id), None)
            require(flag is not None, "Unknown/stale draft flag")
            if flag.code == "table_required":
                require(
                    p.resolution == "keep_selected_table",
                    "Explicitly use the selected table or repeat voice capture",
                )
            elif flag.code == "table_mismatch":
                require(
                    p.resolution in ("keep_selected_table", "use_spoken_table"),
                    "Choose selected or spoken table",
                )
                if p.resolution == "use_spoken_table":
                    self._validate_table(flag.spoken_table_id)
                    order.table_id = flag.spoken_table_id
            else:
                require(
                    p.resolution == "reviewed_remove_unknown",
                    "Review candidates/edit the line, then explicitly dismiss unknown words",
                )
            order.flags.remove(flag)
            order.revision += 1
            self._emit(
                "draft.flag_resolved",
                order.id,
                payload={"code": flag.code, "resolution": p.resolution},
            )
            return {"revision": order.revision}
        if isinstance(p, c.ConfirmSend):
            require(
                e.source == "tap" and p.human_confirmed,
                "Human Confirm and send tap required",
            )
            order = self._draft(p)
            require(not order.flags, "Resolve table mismatch/unknown menu flags first")
            require(bool(order.lines), "Add at least one configured dish")
            count = sum(x.quantity for x in order.lines)
            require(
                count <= len(s.zones),
                "Order exceeds total physical zone capacity; split into reviewed orders",
            )
            if order.voice_baseline is not None:
                initial = {
                    x.id: x.model_dump(
                        include={"menu_id", "quantity", "modifiers", "seat", "requests"}
                    )
                    for x in order.voice_baseline
                }
                final = {
                    x.id: x.model_dump(
                        include={"menu_id", "quantity", "modifiers", "seat", "requests"}
                    )
                    for x in order.lines
                }
                order.corrected_draft_lines = sum(
                    initial.get(key) != final.get(key)
                    for key in initial.keys() | final.keys()
                )
            order.status, order.submitted_at = "submitted", e.time
            for line in order.lines:
                for n in range(line.quantity):
                    key = f"{order.id}:dish:{line.id}:{n}"
                    s.dishes[key] = c.Dish(
                        id=key,
                        order_id=order.id,
                        line_id=line.id,
                        menu_id=line.menu_id,
                        item_name=line.item_name,
                        modifiers=line.modifiers,
                        seat=line.seat,
                        requests=line.requests,
                        station=line.station,
                        typical_minutes=line.typical_minutes,
                    )
            self._emit(
                "order.submitted",
                order.id,
                payload={
                    "table_id": order.table_id,
                    "dishes": [d.model_dump(mode="json") for d in self._dishes(order)],
                    "corrected_draft_lines": order.corrected_draft_lines,
                    "initial_voice_draft_line_count": order.initial_voice_draft_line_count,
                    "capture_mode": order.capture_mode,
                    "final_line_count": len(order.lines),
                },
            )
            return {"order_id": order.id}
        if isinstance(p, c.OrderAction):
            order = self._order(p.order_id)
            if p.action == "acknowledge":
                return self._acknowledge(order)
            if p.action == "retry_zones":
                self._kitchen()
                require(
                    order.acknowledged_at is not None,
                    "Acknowledge before zone allocation",
                )
                self._emit("zones.retry_requested", order.id, outcome="observed")
                self._allocate()
                return {"zone_status": order.zone_status}
            require(
                self._actor.role in ("server", "lead") and e.source == "tap",
                "Server confirms optional delivered tap",
            )
            require(
                order.picked_up_at is not None and order.delivered_at is None,
                "All dishes must be picked up before delivered",
            )
            order.delivered_at, order.status = e.time, "delivered"
            self._emit("order.delivered", order.id)
            return {"delivered": True}
        if isinstance(p, c.DishAction):
            require(p.dish_id in s.dishes, "Unknown physical dish unit")
            dish = s.dishes[p.dish_id]
            if p.action == "start_dish":
                return self._start(dish)
            require(
                e.source == "tap",
                "Camera readiness/pickup must supply stable zone evidence",
            )
            if p.action == "ready_dish":
                self._kitchen()
                return self._ready(dish, fallback_reason=p.fallback_reason)
            require(
                self._actor.role in ("server", "cook", "lead"), "Staff confirms pickup"
            )
            return self._pickup(dish, fallback_reason=p.fallback_reason)
        if isinstance(p, c.KitchenVoice):
            self._kitchen()
            require(e.source == "voice", "Kitchen voice requires voice source")
            parsed = parse_kitchen(s.menu, p.text)
            flags = parsed.get("flags", [])
            candidates = [
                o
                for o in s.orders.values()
                if o.table_id == parsed.get("table_id")
                and (
                    o.status == "submitted"
                    if parsed.get("action") == "acknowledge"
                    else o.acknowledged_at is not None
                    and o.status not in ("picked_up", "delivered")
                )
            ]
            if flags or len(candidates) != 1:
                self._emit(
                    "voice.clarification",
                    payload={
                        "reason": "ambiguous_or_unknown_order",
                        "candidate_order_ids": [o.id for o in candidates],
                    },
                    outcome="observed",
                )
                return {
                    "flags": [
                        {
                            "code": "clarification",
                            "message": "Select one eligible order by tap; table/phrase is ambiguous.",
                        }
                    ]
                }
            order = candidates[0]
            if parsed["action"] == "acknowledge":
                return self._acknowledge(order)
            matches = [
                d
                for d in self._dishes(order)
                if d.menu_id == parsed.get("menu_id") and d.stage == "queued"
            ]
            if len(matches) != 1:
                self._emit(
                    "voice.clarification",
                    order.id,
                    payload={
                        "reason": "ambiguous_dish_unit",
                        "candidate_dish_ids": [d.id for d in matches],
                    },
                    outcome="observed",
                )
                return {
                    "flags": [
                        {
                            "code": "clarification",
                            "message": "Select a physical dish unit/modifier by tap.",
                        }
                    ]
                }
            return self._start(matches[0])
        if isinstance(p, c.CameraStatus):
            self._kitchen()
            require(e.source == "system", "Camera status is service/system provenance")
            require(p.camera_id in s.cameras, "Unknown camera")
            camera = s.cameras[p.camera_id]
            camera.status, camera.reason = p.status, p.reason
            if p.status != "ok":
                for zone in s.zones.values():
                    if zone.camera_id == camera.id:
                        zone.occupancy, zone.verified_by = "unknown", "unknown"
                        zone.blocked_reason = p.reason
            self._emit(
                "camera.status",
                payload={
                    "camera_id": camera.id,
                    "status": camera.status,
                    "reason": camera.reason,
                },
            )
            return {"status": camera.status}
        if isinstance(p, c.ZoneObservation):
            self._kitchen()
            require(e.source == "camera", "Zone observations require camera source")
            require(p.zone_id in s.zones, "Unknown physical zone")
            zone = s.zones[p.zone_id]
            require(
                zone.assignment_version == p.assignment_version,
                "Stale zone assignment version",
            )
            require(
                zone.last_signal_at is None or e.time >= zone.last_signal_at,
                "Out-of-order camera timestamp",
            )
            if (
                s.cameras[zone.camera_id].status != "ok"
                or p.hand_present
                or p.stable_ms < s.stable_ms_required
            ):
                self._emit(
                    "camera.observation",
                    zone.order_id,
                    zone.dish_id,
                    {
                        "zone_id": zone.id,
                        "outcome": "ignored_blocked"
                        if s.cameras[zone.camera_id].status != "ok"
                        else "ignored_unstable_or_hand",
                    },
                    outcome="observed",
                )
                return {"outcome": "ignored", "reason": "blocked/offline/hand/unstable"}
            zone.last_signal_at = e.time
            zone.occupancy, zone.verified_by = (
                "occupied" if p.occupied else "empty",
                "camera",
            )
            if zone.needs_review:
                self._emit(
                    "camera.observation",
                    zone.order_id,
                    zone.dish_id,
                    {"zone_id": zone.id, "outcome": "review_required"},
                    outcome="observed",
                )
                return {"outcome": "review_required"}
            if not zone.dish_id:
                if p.occupied:
                    zone.needs_review, zone.blocked_reason = (
                        True,
                        "Unassigned occupied zone; review returned/unexpected plate",
                    )
                    self._emit(
                        "zone.unexpected",
                        payload={
                            "zone_id": zone.id,
                            "assignment_version": zone.assignment_version,
                        },
                        outcome="observed",
                    )
                    return {"outcome": "unexpected"}
                self._emit(
                    "camera.observation",
                    payload={"zone_id": zone.id, "outcome": "empty_unassigned"},
                    outcome="observed",
                )
                self._allocate()
                return {"outcome": "empty_unassigned"}
            dish = s.dishes[zone.dish_id]
            if p.occupied:
                zone.had_stable_occupancy = True
                if dish.ready_at is None:
                    return self._ready(dish)
                self._emit(
                    "camera.observation",
                    dish.order_id,
                    dish.id,
                    {"zone_id": zone.id, "outcome": "occupied_unchanged"},
                    outcome="observed",
                )
                return {"outcome": "occupied_unchanged"}
            if dish.ready_at is not None and zone.had_stable_occupancy:
                return self._pickup(dish)
            self._emit(
                "camera.observation",
                dish.order_id,
                dish.id,
                {"zone_id": zone.id, "outcome": "empty_before_ready"},
                outcome="observed",
            )
            return {"outcome": "empty_before_ready"}
        if isinstance(p, c.ReconcileZone):
            self._kitchen()
            require(
                e.source == "tap" and p.zone_id in s.zones,
                "Staff tap reviews known zone",
            )
            zone = s.zones[p.zone_id]
            require(
                p.assignment_version == zone.assignment_version, "Stale zone assignment"
            )
            if not p.occupied and zone.dish_id:
                require(
                    s.dishes[zone.dish_id].picked_up_at is not None,
                    "Use explicit Ready/Pickup taps for assigned food; do not erase it",
                )
            zone.occupancy = "occupied" if p.occupied else "empty"
            zone.needs_review, zone.blocked_reason, zone.verified_by = (
                False,
                None,
                "tap",
            )
            self._emit(
                "zone.reconciled",
                zone.order_id,
                zone.dish_id,
                {"zone_id": zone.id, "occupied": p.occupied, "reason": p.reason},
            )
            self._allocate()
            return {"reconciled": True}
        if isinstance(p, c.StockObservation):
            self._kitchen()
            require(
                e.source == "camera" and p.zone_id in s.ingredient_zones,
                "Known ingredient camera zone required",
            )
            s.stock_observations[e.event_id] = {
                "zone_id": p.zone_id,
                "delta": p.delta,
                "accepted": False,
                "eligible": p.stable_ms >= s.stable_ms_required and not p.hand_present,
            }
            self._emit(
                "stock.observation",
                payload={
                    "zone_id": p.zone_id,
                    "delta": p.delta,
                    "requires_review": True,
                    "eligible": s.stock_observations[e.event_id]["eligible"],
                },
                outcome="observed",
            )
            return {"observation_id": e.event_id}
        if isinstance(p, c.AcceptStock):
            self._kitchen()
            require(
                e.source == "tap" and p.zone_id in s.ingredient_zones,
                "Staff reviews stock count",
            )
            require(
                p.quantity != 0 and (p.kind == "correction" or p.quantity > 0),
                "Nonzero signed correction or positive count required",
            )
            require(
                p.order_id is None or p.order_id in s.orders,
                "Unknown ticket attribution",
            )
            if p.observation_id:
                obs = s.stock_observations.get(p.observation_id)
                require(
                    obs is not None
                    and obs["eligible"]
                    and not obs["accepted"]
                    and obs["zone_id"] == p.zone_id,
                    "Unknown/unstable/already accepted observation",
                )
                obs["accepted"] = True
            delta = -p.quantity if p.kind in ("consume", "waste") else p.quantity
            require(
                self._balances()[p.zone_id] + delta >= 0,
                "Stock would be negative; reconcile count",
            )
            s.stock_movements.append(
                c.StockMovement(
                    event_id=e.event_id,
                    zone_id=p.zone_id,
                    delta=delta,
                    kind=p.kind,
                    observation_id=p.observation_id,
                    order_id=p.order_id,
                    reason=p.reason,
                )
            )
            self._emit(
                "stock.changed",
                p.order_id,
                payload={
                    "zone_id": p.zone_id,
                    "delta": delta,
                    "kind": p.kind,
                    "observation_id": p.observation_id,
                    "reason": p.reason,
                },
            )
            return {"balance": self._balances()[p.zone_id]}
        raise Conflict("Unsupported MVP action")

    def _acknowledge(self, order):
        self._kitchen()
        require(
            self._current.source in ("tap", "voice") and order.status == "submitted",
            "Select one submitted order",
        )
        require(
            len(self._dishes(order)) <= len(self.state.zones),
            "Dish count exceeds configured physical zones",
        )
        order.acknowledged_at, order.status = self._current.time, "acknowledged"
        self._emit(
            "order.acknowledged",
            order.id,
            payload={"automation_available": None, "fallback_reason": None},
        )
        self.waiting.append(order.id)
        self._allocate()
        return {"order_id": order.id, "zone_status": order.zone_status}

    def _allocate(self):
        s = self.state
        for key in self.waiting[:]:
            order = s.orders[key]
            dishes = self._dishes(order)
            free = [
                z
                for z in s.zones.values()
                if z.dish_id is None and z.occupancy == "empty" and not z.needs_review
            ]
            if len(free) < len(dishes):
                if order.zone_status != "waiting":
                    order.zone_status, order.waiting_since = (
                        "waiting",
                        self._current.time,
                    )
                    self._emit(
                        "zones.waiting",
                        order.id,
                        payload={"required": len(dishes), "free": len(free)},
                        derived=True,
                    )
                break  # strict FIFO; no partial allocation or bypassing large waits
            for zone, dish in zip(free, dishes):
                zone.assignment_version += 1
                zone.order_id, zone.dish_id = order.id, dish.id
                zone.had_stable_occupancy, zone.last_signal_at = False, None
                dish.zone_id = zone.id
            order.zone_status = "assigned"
            self.waiting.remove(key)
            self._emit(
                "zones.assigned",
                order.id,
                payload={
                    "assignments": [
                        {
                            "zone_id": d.zone_id,
                            "dish_id": d.id,
                            "assignment_version": s.zones[d.zone_id].assignment_version,
                        }
                        for d in dishes
                    ]
                },
                derived=True,
            )

    def _start(self, dish):
        self._kitchen()
        order = self._order(dish.order_id)
        require(
            self._current.source in ("tap", "voice")
            and order.acknowledged_at is not None
            and dish.stage == "queued",
            "Start one queued dish after acknowledgment",
        )
        dish.stage, dish.started_at = "started", self._current.time
        order.status = "cooking"
        self._emit(
            "dish.started",
            order.id,
            dish.id,
            {
                "station": dish.station,
                "typical_minutes": dish.typical_minutes,
                "automation_available": None,
                "fallback_reason": None,
            },
        )
        return {"dish_id": dish.id}

    def _ready(self, dish, fallback_reason=None):
        order = self._order(dish.order_id)
        require(
            order.acknowledged_at is not None and dish.zone_id is not None,
            "Acknowledge and reserve all zones before ready",
        )
        require(dish.stage in ("queued", "started"), "Dish already ready/picked up")
        zone = self.state.zones[dish.zone_id]
        require(not zone.needs_review, "Review unexpected/returned plate first")
        dish.stage, dish.ready_at = "ready", self._current.time
        zone.occupancy, zone.had_stable_occupancy = "occupied", True
        zone.verified_by = "tap" if self._current.source == "tap" else "camera"
        self._emit(
            "dish.ready",
            order.id,
            dish.id,
            {
                "zone_id": zone.id,
                "assignment_version": zone.assignment_version,
                **self._fallback(dish, fallback_reason),
            },
        )
        if (
            all(d.ready_at is not None for d in self._dishes(order))
            and not order.ready_notified
        ):
            order.ready_notified, order.ready_at, order.status = (
                True,
                self._current.time,
                "ready",
            )
            self._emit(
                "order.ready",
                order.id,
                payload={"table_id": order.table_id},
                derived=True,
            )
            event_id = self._pending[-1].event_id
            self.state.notifications.append(
                c.Notification(
                    id=event_id,
                    order_id=order.id,
                    table_id=order.table_id,
                    time=self._current.time,
                )
            )
        return {"dish_id": dish.id, "stage": dish.stage}

    def _pickup(self, dish, fallback_reason=None):
        require(dish.stage == "ready", "Ready milestone required before pickup")
        order, zone = self._order(dish.order_id), self.state.zones[dish.zone_id]
        dish.stage, dish.picked_up_at = "picked_up", self._current.time
        self._emit(
            "dish.picked_up",
            order.id,
            dish.id,
            {
                "zone_id": zone.id,
                "assignment_version": zone.assignment_version,
                **self._fallback(dish, fallback_reason),
            },
        )
        zone.order_id = zone.dish_id = None
        zone.assignment_version += 1
        zone.occupancy, zone.needs_review, zone.blocked_reason = "empty", False, None
        zone.had_stable_occupancy = False
        zone.verified_by = "tap" if self._current.source == "tap" else "camera"
        # Historical dish zone stays as provenance; current lookup is zone.dish_id.
        if all(d.picked_up_at is not None for d in self._dishes(order)):
            order.status, order.picked_up_at, order.zone_status = (
                "picked_up",
                self._current.time,
                "released",
            )
            self._emit("order.picked_up", order.id, derived=True)
        self._allocate()
        return {"dish_id": dish.id, "stage": dish.stage}

    def _balances(self):
        return {
            key: zone.initial
            + sum(m.delta for m in self.state.stock_movements if m.zone_id == key)
            for key, zone in self.state.ingredient_zones.items()
        }

    def snapshot(self):
        with self.lock:
            result = self.state.model_dump(mode="json")
            expected = {key: 0.0 for key in self.state.ingredient_zones}
            for order in self.state.orders.values():
                if order.submitted_at is not None:
                    for line in order.lines:
                        for ingredient in line.recipe or []:
                            key = ingredient.get(
                                "zone_id"
                            ) or self.state.menu.ingredient_zones.get(
                                ingredient["ingredient"]
                            )
                            if key in expected:
                                expected[key] += ingredient["qty"] * line.quantity
            result["computed"] = {
                "order_progress": {
                    o.id: {
                        "total": len(self._dishes(o)),
                        "ready": sum(d.ready_at is not None for d in self._dishes(o)),
                        "picked_up": sum(
                            d.picked_up_at is not None for d in self._dishes(o)
                        ),
                    }
                    for o in self.state.orders.values()
                },
                "balances": self._balances(),
                "expected_consumption": expected,
                "analytics_health": self.outbox.health(),
            }
            return result
