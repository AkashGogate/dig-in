"""Shared task ranking inputs, atomic claim/helper transition rules.

Caller owns the restaurant transaction lock. No browser or adapter bypasses it.
"""

from app.coordination.rules import require


def blockers(state, task):
    reasons = []
    if task.blocker:
        reasons.append(task.blocker)
    if any(
        state.dishes[k].stage not in ("ready", "picked_up", "served")
        for k in task.dish_ids
    ):
        reasons.append("Food not ready")
    missing = sum(x is None for x in task.helper_slots)
    if missing:
        reasons.append(f"Waiting for {missing} additional helper(s)")
    return reasons


def task_action(state, p, actor):
    require(p.task_id in state.tasks, "Unknown task")
    t = state.tasks[p.task_id]
    require(t.status not in ("cancelled", "completed"), "Task is closed")
    require(actor.role in ("server", "lead"), "Server/lead task session required")
    op = p.operation
    if op == "claim":
        require(
            t.status == "available" and t.owner is None,
            "Task already claimed or blocked",
        )
        require(
            actor.id not in t.helper_slots, "Leave helper slot before claiming lead"
        )
        t.owner, t.status = actor.id, "claimed"
    elif op == "join":
        require(
            t.owner is not None and t.owner != actor.id,
            "A different run lead must claim first",
        )
        require(
            actor.id not in t.helper_slots and None in t.helper_slots,
            "No open helper slot, or already joined",
        )
        t.helper_slots[t.helper_slots.index(None)] = actor.id
    elif op == "leave":
        require(actor.id in t.helper_slots, "Not a helper on this task")
        t.helper_slots[t.helper_slots.index(actor.id)] = None
    else:
        require(t.owner == actor.id or actor.role == "lead", "Task owner/lead required")
        if op == "release":
            require(
                not any(state.dishes[k].stage == "picked_up" for k in t.dish_ids),
                "Confirm served or reconcile picked-up food before releasing",
            )
            t.owner, t.status = None, "available"
            t.helper_slots = [None] * len(t.helper_slots)
            t.blocker = None
        elif op == "helpers":
            require(
                not any(
                    state.dishes[k].stage in ("picked_up", "served") for k in t.dish_ids
                ),
                "Set helper count before pickup",
            )
            require(
                not any(t.helper_slots),
                "Release joined helpers before changing count",
            )
            t.helper_slots = [None] * p.additional_helpers
        elif op == "split":
            require(bool(p.reason), "Record split-delivery decision")
            t.helper_slots = []
        elif op == "block":
            require(bool(p.reason), "Blocker reason required")
            t.blocker, t.status = p.reason, "blocked"
        elif op == "cancel":
            require(bool(p.reason), "Cancellation reason required")
            require(
                not any(state.dishes[k].stage == "picked_up" for k in t.dish_ids),
                "Reconcile pickup before cancellation",
            )
            t.status = "cancelled"
        elif op == "complete":
            require(
                not t.dish_ids
                or all(state.dishes[k].stage == "served" for k in t.dish_ids),
                "Food tasks complete only after explicit served confirmation",
            )
            require(not blockers(state, t), "Resolve blockers before completing")
            t.status = "completed"
        elif op == "urgent":
            require(
                actor.role == "lead" and bool(p.reason),
                "Shift lead override requires reason",
            )
            t.urgency, t.priority_reason = True, p.reason
    return {"task_id": t.id, "blockers": blockers(state, t)}
