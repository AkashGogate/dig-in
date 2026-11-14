"""Dish and fixed-view kitchen observation rules, not computer vision.

Caller owns the restaurant transaction lock. Plate presence never verifies contents.
"""

from app.coordination import contracts as c
from app.coordination.rules import require
from app.coordination.tasks import blockers


def advance(state, dish, stage, reason=""):
    stages = {
        "queued": {"preparing"},
        "preparing": {"partially_plated", "plated"},
        "partially_plated": {"plated"},
        "plated": {"ready"},
        "ready": {"picked_up"},
        "picked_up": {"served"},
        "served": set(),
    }
    correction = (
        stage in ("preparing", "partially_plated", "plated")
        and dish.stage in ("partially_plated", "plated", "ready")
        and bool(reason)
    )
    require(
        stage in stages[dish.stage] or correction,
        "Invalid dish transition; staff correction needs a reason",
    )
    require(
        not any(not a.acknowledged for a in state.orders[dish.order_id].amendments),
        "Kitchen must acknowledge pending amendment",
    )
    if stage in ("partially_plated", "plated", "ready"):
        require(dish.bay_id is not None, "Waiting for a plating bay")
    if correction:
        require(
            not any(
                t.status == "claimed" and dish.id in t.dish_ids
                for t in state.tasks.values()
            ),
            "Release claimed run before correcting readiness",
        )
        for task in state.tasks.values():
            if dish.id in task.dish_ids and task.status in ("available", "blocked"):
                task.status = "cancelled"
    dish.stage = stage
    if stage in ("partially_plated", "plated", "ready"):
        state.bays[dish.bay_id].occupied = True
    if stage == "ready":
        order = state.orders[dish.order_id]
        key = f"run:{dish.id}:{len(state.events)}"
        state.tasks[key] = c.Task(
            id=key,
            table_id=order.table_id,
            section=state.tables[order.table_id].section,
            type="food_run",
            dish_ids=[dish.id],
            priority_reason="Hot food ready; oldest ready dishes first",
        )
    if stage == "picked_up" and dish.bay_id:
        bay = state.bays[dish.bay_id]
        if all(state.dishes[k].stage in ("picked_up", "served") for k in bay.dish_ids):
            bay.occupied = False
    if stage == "served":
        for task in state.tasks.values():
            if dish.id in task.dish_ids and all(
                state.dishes[k].stage == "served" for k in task.dish_ids
            ):
                task.status = "completed"


def observe(state, e, p):
    s = state
    require(
        e.source in ("mock_camera", "camera", "manual"),
        "Observation source invalid",
    )
    obs = c.Observation(
        id=e.id,
        kind=p.kind,
        target_id=p.target_id,
        assignment_version=p.assignment_version,
        quantity=p.quantity,
        order_id=p.order_id,
        source=e.source,
        device_id=e.device_id,
        occurred_at=e.occurred_at.isoformat(),
    )
    if p.kind == "ingredient_change":
        require(p.target_id in s.zones, "Unknown ingredient zone")
        require(
            p.order_id is None or p.order_id in s.orders,
            "Unknown prep ticket attribution",
        )
        # Never infer quantity, attribution, progress or stock acceptance from a hand/removal.
    else:
        require(p.target_id in s.bays, "Unknown physical bay")
        bay = s.bays[p.target_id]
        require(
            p.assignment_version == bay.assignment_version,
            "Stale camera event; bay assignment changed",
        )
        require(
            p.order_id is None or p.order_id == bay.order_id,
            "Observation belongs to another ticket",
        )
        if p.kind == "obstruction":
            obs.disposition = "needs_staff_review"
        elif p.kind == "plate_arrival":
            require(bool(bay.dish_ids), "Assign bay before interpreting arrival")
            bay.occupied = True
            candidates = [
                s.dishes[k] for k in bay.dish_ids if s.dishes[k].stage == "preparing"
            ]
            unambiguous = len(candidates) == 1 or p.quantity == len(candidates)
            if unambiguous:
                for dish in candidates:
                    advance(state, dish, "partially_plated")
            if (
                s.auto_ready_enabled
                and bay.convention == "complete_batches_only"
                and len(bay.dish_ids) == 1
                and p.quantity == 1
            ):
                dish = s.dishes[bay.dish_ids[0]]
                if dish.stage == "partially_plated":
                    advance(state, dish, "plated")
                    advance(state, dish, "ready")
                    obs.disposition = "conditional_auto_ready"
            else:
                obs.disposition = (
                    "staged_only_contents_unverified"
                    if unambiguous
                    else "clarify_staged_dish"
                )
        elif p.kind == "plate_return":
            bay.occupied = True
            bay.unresolved_pickup = True
            obs.disposition = "return_needs_reconciliation"
        elif p.kind == "plate_removal":
            pending = [
                s.dishes[k]
                for k in bay.dish_ids
                if s.dishes[k].stage not in ("picked_up", "served")
            ]
            tasks = [
                t
                for t in s.tasks.values()
                if t.status == "claimed"
                and set(t.dish_ids) == {d.id for d in pending}
                and not blockers(state, t)
            ]
            if (
                len(tasks) == 1
                and len(pending) == 1
                and p.quantity == 1
                and not bay.unresolved_pickup
            ):
                advance(state, pending[0], "picked_up")
                obs.disposition = "associated_with_claimed_run"
            else:
                bay.unresolved_pickup = True
                obs.disposition = "clarify_removed_dish_and_runner"
    s.observations[obs.id] = obs
    return {"observation_id": obs.id, "disposition": obs.disposition}
