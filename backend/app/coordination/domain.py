"""Single-process demo authority: locked transactions, revision gates, retry receipts.

State/receipts reset on restart. Multiple workers/replicas are NOT supported.
"""

from __future__ import annotations

import copy
import hashlib
import threading
import uuid
from datetime import UTC, datetime

from app.coordination import contracts as c
from app.coordination.adapters import MockPositioning, MockReadback
from app.coordination.fixtures import seed
from app.coordination.kitchen import advance, observe
from app.coordination.rules import Conflict, require
from app.coordination.tasks import blockers, task_action


class Restaurant:
    def __init__(self):
        self.state = seed()
        self.lock = threading.RLock()
        self.sessions: dict[str, str] = {}
        self.receipts: dict[str, tuple[str, dict]] = {}
        self.positioning = MockPositioning()
        self.readback = MockReadback()

    def session(self, actor_id: str) -> dict:
        with self.lock:
            require(actor_id in self.state.actors, "Unknown demo actor")
            token = str(uuid.uuid4())
            self.sessions[token] = actor_id
            return {
                "session_id": token,
                "actor": self.state.actors[actor_id].model_dump(),
            }

    def execute(self, command: c.Command, session_id: str) -> dict:
        with self.lock:
            require(session_id in self.sessions, "Select a demo session first")
            actor = self.state.actors[self.sessions[session_id]]
            fingerprint = hashlib.sha256(
                (actor.id + command.model_dump_json()).encode()
            ).hexdigest()
            if command.id in self.receipts:
                previous, result = self.receipts[command.id]
                require(
                    previous == fingerprint,
                    "Event ID reused with changed content or actor",
                )
                return {
                    "result": copy.deepcopy(result),
                    "state": self.snapshot(),
                    "replayed": True,
                }
            p = command.payload
            is_observation = p.action == "observe"
            require(
                command.kind == ("observation" if is_observation else "command"),
                "Observation/command distinction does not match action",
            )
            if not is_observation:
                require(
                    command.source in ("manual", "voice"),
                    "Devices emit observations, not staff commands",
                )
            before = copy.deepcopy(self.state)
            try:
                result = self._apply(command, actor)
                target = next(
                    (
                        getattr(p, k)
                        for k in (
                            "order_id",
                            "dish_id",
                            "task_id",
                            "target_id",
                            "zone_id",
                            "bay_id",
                        )
                        if hasattr(p, k)
                    ),
                    result.get("order_id"),
                )
                self.state.events.append(
                    {
                        "id": command.id,
                        "schema_version": 1,
                        "source": command.source,
                        "kind": command.kind,
                        "occurred_at": command.occurred_at.isoformat(),
                        "received_at": c.now(),
                        "actor_id": actor.id,
                        "device_id": command.device_id,
                        "correlation_id": command.correlation_id or target,
                        "target_id": target,
                        "action": p.action,
                        "payload": p.model_dump(mode="json"),
                    }
                )
                self.receipts[command.id] = (fingerprint, copy.deepcopy(result))
            except Exception:
                self.state = before
                raise
            return {"result": result, "state": self.snapshot(), "replayed": False}

    def _order(self, order_id: str) -> c.Order:
        require(order_id in self.state.orders, "Unknown order")
        return self.state.orders[order_id]

    def _draft(self, p, actor):
        order = self._order(p.order_id)
        require(order.owner == actor.id, "Only the draft owner may edit or send")
        require(order.status == "draft", "Submitted orders require an amendment")
        require(
            order.revision == p.revision, "Stale draft revision; refresh and review"
        )
        return order

    def _kitchen(self, actor):
        require(actor.role in ("cook", "lead"), "Cook or shift lead required")

    def _validate_lines(self, table_id, lines):
        require(table_id in self.state.tables, "Select a configured table")
        require(bool(lines), "At least one order line required")
        require(
            len({entry.id for entry in lines}) == len(lines), "Line IDs must be unique"
        )
        for line in lines:
            require(
                line.seat in self.state.tables[table_id].seats,
                "Seat is not at selected table",
            )
            require(line.menu_id in self.state.menu, "Unknown menu item")
            require(
                set(line.modifiers) <= set(self.state.menu[line.menu_id].modifiers),
                "Modifier is not configured for this menu item",
            )

    def _new_dishes(self, order, line, count, event_id):
        for n in range(count):
            key = f"{event_id}:{line.id}:{n}"
            self.state.dishes[key] = c.Dish(
                id=key,
                order_id=order.id,
                line_id=line.id,
                seat=line.seat,
                menu_id=line.menu_id,
                course=line.course,
                modifiers=line.modifiers[:],
                requests=line.requests,
            )

    def _allocate(self):
        # Current product decision: assign at arrival, waiting queue on full bays.
        for bay in self.state.bays.values():
            if bay.order_id or bay.occupied or bay.unresolved_pickup:
                continue
            waiting = [
                d
                for d in self.state.dishes.values()
                if not d.bay_id and d.stage == "queued"
            ]
            if not waiting:
                return
            first = waiting[0]
            group = [
                d
                for d in waiting
                if (d.order_id, d.course) == (first.order_id, first.course)
            ][: bay.capacity]
            self._assign(bay, group)

    def _assign(self, bay, dishes):
        require(
            not bay.order_id and not bay.occupied and not bay.unresolved_pickup,
            "Bay is occupied or unresolved",
        )
        require(0 < len(dishes) <= bay.capacity, "Bay capacity exceeded")
        require(len({d.id for d in dishes}) == len(dishes), "Duplicate dish in batch")
        require(
            len({(d.order_id, d.course) for d in dishes}) == 1,
            "One ticket/course per bay assignment",
        )
        require(
            all(
                d.bay_id is None and d.stage not in ("picked_up", "served")
                for d in dishes
            ),
            "Dish already assigned or delivered",
        )
        bay.assignment_version += 1
        bay.order_id, bay.course = dishes[0].order_id, dishes[0].course
        bay.dish_ids = [d.id for d in dishes]
        for dish in dishes:
            dish.bay_id = bay.id

    def _apply(self, e: c.Command, actor: c.Actor) -> dict:
        p, s = e.payload, self.state
        if isinstance(p, c.Start):
            require(actor.role in ("server", "lead"), "Server session required")
            require(p.table_id is None or p.table_id in s.tables, "Unknown table")
            order = c.Order(id=e.id, owner=actor.id, table_id=p.table_id)
            s.orders[order.id] = order
            result = {"order_id": order.id}
            if p.use_positioning:
                result["positioning"] = self.positioning.suggest(actor.id)
            return result
        if isinstance(p, c.Edit):
            order = self._draft(p, actor)
            require(
                e.source == "manual", "Speech only proposes changes; use review/apply"
            )
            self._validate_lines(p.table_id, p.lines)
            order.table_id, order.lines = p.table_id, copy.deepcopy(p.lines)
            order.revision += 1
            order.proposal = None
            return {"revision": order.revision}
        if isinstance(p, c.Readback):
            order = self._draft(p, actor)
            order.proposal = self.readback.compare(order, p.transcript, p.line_id, e.id)
            return {"proposal": order.proposal.model_dump()}
        if isinstance(p, c.Accept):
            order = self._draft(p, actor)
            require(e.source == "manual", "Human review/apply is required")
            proposal = order.proposal
            require(
                proposal is not None
                and proposal.id == p.proposal_id
                and proposal.revision == order.revision,
                "Stale or missing proposal",
            )
            require(
                not proposal.question
                and proposal.line_id is not None
                and proposal.quantity is not None,
                "Clarify the target before applying",
            )
            line = next(entry for entry in order.lines if entry.id == proposal.line_id)
            line.quantity = proposal.quantity
            order.revision += 1
            order.proposal = None
            return {"revision": order.revision, "requires_confirmation": True}
        if isinstance(p, c.Send):
            order = self._draft(p, actor)
            require(
                e.source == "manual" and p.human_confirmed,
                "Human tap Confirm and send required; speech cannot submit",
            )
            require(
                order.proposal is None,
                "Apply or dismiss the proposal by editing, then review",
            )
            self._validate_lines(order.table_id, order.lines)
            order.status = "submitting"
            order.status_history.append("submitting")
            for line in order.lines:
                self._new_dishes(order, line, line.quantity, e.id)
            order.status = "submitted"
            order.status_history.append("submitted")
            self._allocate()
            return {"order_id": order.id, "status": order.status}
        if isinstance(p, c.Acknowledge):
            self._kitchen(actor)
            order = self._order(p.order_id)
            require(order.status == "submitted", "Order has not been sent")
            order.acknowledged = True
            return {"acknowledged": True}
        if isinstance(p, c.Amend):
            order = self._order(p.order_id)
            require(
                actor.id == order.owner or actor.role == "lead",
                "Order owner or lead required",
            )
            require(
                e.source == "manual"
                and order.status == "submitted"
                and order.revision == p.revision,
                "Review current submitted revision manually",
            )
            require(
                not any(not a.acknowledged for a in order.amendments),
                "Previous amendment awaits kitchen acknowledgment",
            )
            require(any(entry.id == p.line_id for entry in order.lines), "Unknown line")
            require(
                all(
                    d.stage == "queued"
                    for d in s.dishes.values()
                    if d.order_id == order.id and d.line_id == p.line_id
                ),
                "Prepared items need staff reconciliation; cannot silently amend",
            )
            order.revision += 1
            order.amendments.append(
                c.Amendment(
                    line_id=p.line_id, quantity=p.quantity, revision=order.revision
                )
            )
            return {"revision": order.revision, "pending_kitchen_ack": True}
        if isinstance(p, c.AckAmendment):
            self._kitchen(actor)
            order = self._order(p.order_id)
            require(
                order.revision == p.revision and bool(order.amendments),
                "Stale/missing amendment",
            )
            a = order.amendments[-1]
            require(not a.acknowledged, "Amendment already acknowledged")
            old = [
                d
                for d in s.dishes.values()
                if d.order_id == order.id and d.line_id == a.line_id
            ]
            require(
                all(d.stage == "queued" for d in old),
                "Prepared items need reconciliation",
            )
            require(
                all(
                    not s.bays[d.bay_id].occupied
                    and not s.bays[d.bay_id].unresolved_pickup
                    for d in old
                    if d.bay_id
                ),
                "Occupied bay requires reconciliation",
            )
            for d in old:
                if d.bay_id:
                    bay = s.bays[d.bay_id]
                    bay.dish_ids.remove(d.id)
                    bay.assignment_version += 1
                    if not bay.dish_ids:
                        bay.order_id = bay.course = None
                del s.dishes[d.id]
            line = next(entry for entry in order.lines if entry.id == a.line_id)
            line.quantity = a.quantity
            self._new_dishes(order, line, line.quantity, e.id)
            a.acknowledged = True
            self._allocate()
            return {"acknowledged": True}
        if isinstance(p, c.Advance):
            require(p.dish_id in s.dishes, "Unknown dish")
            dish = s.dishes[p.dish_id]
            if p.stage in ("picked_up", "served"):
                require(actor.role in ("server", "lead"), "Server confirms delivery")
                if p.stage == "picked_up":
                    task = next(
                        (
                            t
                            for t in s.tasks.values()
                            if dish.id in t.dish_ids and t.status == "claimed"
                        ),
                        None,
                    )
                    require(
                        task is not None
                        and task.owner == actor.id
                        and not blockers(self.state, task),
                        "Claim run and resolve food/helper blockers before pickup",
                    )
                else:
                    require(
                        dish.stage == "picked_up" and e.source == "manual",
                        "Explicit served confirmation after pickup required",
                    )
                    task = next(
                        (
                            t
                            for t in s.tasks.values()
                            if dish.id in t.dish_ids and t.status == "claimed"
                        ),
                        None,
                    )
                    require(
                        task is not None and task.owner == actor.id,
                        "Run owner confirms served",
                    )
            else:
                self._kitchen(actor)
                require(
                    self._order(dish.order_id).acknowledged,
                    "Kitchen must acknowledge before preparation",
                )
            advance(self.state, dish, p.stage, p.reason)
            return {"dish_id": dish.id, "stage": dish.stage}
        if isinstance(p, c.Assign):
            self._kitchen(actor)
            require(p.bay_id in s.bays, "Unknown bay")
            bay = s.bays[p.bay_id]
            require(
                bay.assignment_version == p.assignment_version, "Stale bay assignment"
            )
            require(all(k in s.dishes for k in p.dish_ids), "Unknown dish")
            self._assign(bay, [s.dishes[k] for k in p.dish_ids])
            return {"assignment_version": bay.assignment_version}
        if isinstance(p, c.ReleaseBay):
            self._kitchen(actor)
            require(p.bay_id in s.bays, "Unknown bay")
            bay = s.bays[p.bay_id]
            require(
                bay.assignment_version == p.assignment_version, "Stale bay assignment"
            )
            require(
                not bay.occupied and not bay.unresolved_pickup,
                "Food/unresolved pickup must be reconciled first",
            )
            require(
                all(s.dishes[k].stage in ("picked_up", "served") for k in bay.dish_ids),
                "Cannot reuse bay with undelivered food",
            )
            for k in bay.dish_ids:
                s.dishes[k].bay_id = None
            bay.order_id = bay.course = None
            bay.dish_ids = []
            bay.assignment_version += 1
            self._allocate()
            return {"assignment_version": bay.assignment_version}
        if isinstance(p, c.ReconcileBay):
            self._kitchen(actor)
            require(e.source == "manual", "Staff must review bay reconciliation")
            require(p.bay_id in s.bays, "Unknown bay")
            bay = s.bays[p.bay_id]
            require(
                bay.assignment_version == p.assignment_version, "Stale bay assignment"
            )
            if not p.occupied:
                require(
                    all(
                        s.dishes[k].stage in ("picked_up", "served")
                        for k in bay.dish_ids
                    ),
                    "Confirm claimed pickup before clearing food from bay",
                )
            bay.occupied = p.occupied
            bay.unresolved_pickup = False
            for observation in s.observations.values():
                if (
                    observation.target_id == bay.id
                    and observation.assignment_version == bay.assignment_version
                    and observation.kind in ("plate_removal", "plate_return")
                ):
                    observation.disposition = "reconciled_by_staff"
            return {"reconciled": True}
        if isinstance(p, c.SelectPrep):
            self._kitchen(actor)
            order = self._order(p.order_id)
            require(
                order.status == "submitted" and order.acknowledged,
                "Select an acknowledged ticket",
            )
            s.active_prep[actor.id] = order.id
            return {"active_prep_order_id": order.id}
        if isinstance(p, c.Observe):
            return observe(self.state, e, p)
        if isinstance(p, c.Stock):
            self._kitchen(actor)
            require(
                p.zone_id in s.zones and p.quantity != 0,
                "Known zone and nonzero count required",
            )
            require(
                p.order_id is None or p.order_id in s.orders,
                "Unknown attribution ticket",
            )
            if p.observation_id:
                require(p.observation_id in s.observations, "Unknown observation")
                obs = s.observations[p.observation_id]
                require(
                    obs.kind == "ingredient_change" and obs.target_id == p.zone_id,
                    "Observation zone/type mismatch",
                )
                require(
                    not any(m.observation_id == p.observation_id for m in s.movements),
                    "Observation already accepted; record a correction instead",
                )
                obs.disposition = "accepted"
            if p.kind != "correction":
                require(
                    p.quantity > 0,
                    "Quantity must be positive; correction can be signed",
                )
            delta = -p.quantity if p.kind in ("consume", "waste") else p.quantity
            balance = s.zones[p.zone_id].initial + sum(
                m.delta for m in s.movements if m.zone_id == p.zone_id
            )
            require(
                balance + delta >= 0,
                "Count exceeds accepted balance; reconcile inventory",
            )
            s.movements.append(
                c.Movement(
                    id=e.id,
                    zone_id=p.zone_id,
                    kind=p.kind,
                    delta=delta,
                    observation_id=p.observation_id,
                    order_id=p.order_id,
                    actor_id=actor.id,
                    reason=p.reason,
                )
            )
            return {"balance": balance + delta}
        if isinstance(p, c.CreateTask):
            require(p.table_id in s.tables, "Unknown table")
            task = c.Task(
                id=e.id,
                table_id=p.table_id,
                section=s.tables[p.table_id].section,
                type=p.type,
                priority_reason=p.reason,
            )
            s.tasks[task.id] = task
            return {"task_id": task.id}
        if isinstance(p, c.TaskAction):
            return task_action(self.state, p, actor)
        raise Conflict("Unsupported command")

    def snapshot(self, section: str | None = None):
        with self.lock:
            s = self.state
            result = s.model_dump(mode="json")
            balances = {
                k: z.initial + sum(m.delta for m in s.movements if m.zone_id == k)
                for k, z in s.zones.items()
            }
            expected = {k: 0 for k in s.zones}
            for order in s.orders.values():
                if order.status == "submitted":
                    for line in order.lines:
                        for ingredient, count in s.menu[line.menu_id].recipe.items():
                            expected[ingredient] += count * line.quantity
            stage_order = [
                "queued",
                "preparing",
                "partially_plated",
                "plated",
                "ready",
                "picked_up",
                "served",
            ]
            aggregates = {}
            for order in s.orders.values():
                dishes = [d for d in s.dishes.values() if d.order_id == order.id]
                stages = {d.stage for d in dishes}
                if not dishes:
                    label = order.status
                elif len(stages) == 1:
                    label = next(iter(stages))
                else:
                    label = (
                        "mixed ("
                        + ", ".join(x for x in stage_order if x in stages)
                        + ")"
                    )
                if dishes and any(
                    d.bay_id is None and d.stage == "queued" for d in dishes
                ):
                    label += " · waiting_for_zone"
                aggregates[order.id] = label
            current = datetime.now(UTC)

            def score(t):
                age = max(
                    0, (current - datetime.fromisoformat(t.created_at)).total_seconds()
                )
                return (
                    (1_000_000 if t.urgency else 0)
                    + (300 if t.type == "food_run" else 0)
                    + age
                    + (10 if t.vip else 0)
                )

            available = [
                t
                for t in s.tasks.values()
                if t.status == "available"
                and not blockers(self.state, t)
                and (section is None or t.section == section)
            ]
            ranked = []
            for task in sorted(
                available, key=lambda t: (-score(t), t.created_at, t.id)
            )[:3]:
                item = task.model_dump()
                item["priority_reason"] = (
                    (
                        "Shift lead override: "
                        if task.urgency
                        else "Hot food ready + wait time"
                        if task.type == "food_run"
                        else "Request aging"
                    )
                    + "; "
                    + task.priority_reason
                )
                ranked.append(item)
            result["computed"] = {
                "balances": balances,
                "expected_consumption": expected,
                "ticket_stages": aggregates,
                "ranked_tasks": ranked,
                "task_blockers": {
                    t.id: blockers(self.state, t) for t in s.tasks.values()
                },
            }
            return result
