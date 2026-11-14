"""Service handoff commands and deterministic role-scoped read projections.

Writes run only through Restaurant.execute's transaction/lock/receipt/outbox.
The kitchen task lineup is a projection of canonical physical Dish units; it has
no independent task status that could disagree with readiness/zone allocation.
Summaries are ephemeral presentation, never stored/exported or auto-spoken.
"""

from __future__ import annotations

from collections import Counter

from app.coordination.rules import require
from app.mvp import contracts as c
from app.mvp import service_contracts as s

TERMINAL = {"picked_up", "delivered"}


def apply_service_command(core, payload):
    """Return None for unrelated payloads; every handled command returns a dict."""
    state, command, actor = core.state, core._current, core._actor
    if isinstance(payload, s.PublishServiceUpdate):
        core._kitchen()
        require(command.source == "tap", "Author service updates explicitly by tap")
        order = core._order(payload.order_id)
        require(
            order.status != "draft" and order.status not in TERMINAL,
            "Kitchen updates require an active submitted order",
        )
        require(
            len(state.service_updates) < 1000, "Demo service update capacity reached"
        )
        if payload.kind == "pickup_request":
            require(
                any(d.stage == "ready" for d in core._dishes(order)),
                "No plates are currently ready for pickup",
            )
        update = s.ServiceUpdate(
            id=command.event_id,
            order_id=order.id,
            kind=payload.kind,
            note=payload.note,
            sender_id=actor.id,
            recipient_id=order.owner,
            created_at=command.time,
            received_at=core._received,
        )
        state.service_updates[update.id] = update
        core._emit(
            "service.update_published",
            order.id,
            payload={
                "update_id": update.id,
                "kind": update.kind,
                "sender_id": actor.id,
                "recipient_id": order.owner,
                "revision": update.revision,
            },
        )
        return {"update_id": update.id, "revision": update.revision}
    if isinstance(payload, s.RespondServiceUpdate):
        require(command.source == "tap", "Review service updates explicitly by tap")
        require(payload.update_id in state.service_updates, "Unknown service update")
        update = state.service_updates[payload.update_id]
        require(
            actor.id == update.recipient_id or actor.role == "lead",
            "Only the recipient or lead may respond to this update",
        )
        require(
            payload.revision == update.revision,
            "Stale service update; refresh and review",
        )
        if payload.action == "acknowledge_service_update":
            require(update.status == "unread", "Service update is already acknowledged")
            update.status, update.acknowledged_at = "acknowledged", command.time
            event_type = "service.update_acknowledged"
        else:
            require(
                update.status == "acknowledged",
                "Acknowledge the service update before resolving it",
            )
            update.status, update.resolved_at = "resolved", command.time
            event_type = "service.update_resolved"
        update.revision += 1
        core._emit(
            event_type,
            update.order_id,
            payload={
                "update_id": update.id,
                "recipient_id": update.recipient_id,
                "revision": update.revision,
            },
        )
        return {
            "update_id": update.id,
            "revision": update.revision,
            "status": update.status,
        }
    return None


def _next_dish_action(dish, order, audience, zone):
    if audience == "server":
        return "pickup_dish" if dish.stage == "ready" else None
    if order.acknowledged_at is None:
        return "acknowledge"
    # Cooking can start after acknowledgment even while ready-only plating
    # zones are FIFO-waiting. Zone capacity guards readiness, not actual start.
    if dish.stage == "queued":
        return "start_dish"
    if dish.stage == "started":
        if zone is None:
            return "wait_for_zones"
        return None if zone.needs_review else "ready_dish"
    return None


def _order_action(order, audience):
    if audience == "kitchen":
        if order.acknowledged_at is None:
            return "acknowledge"
        return "retry_zones" if order.zone_status == "waiting" else None
    return "deliver_order" if order.status == "picked_up" else None


def build_summary(state: c.State, actor: c.Actor, audience: s.Audience, generated_at):
    """Build from one copied state and one capture time; never query live fields."""
    require(
        actor.role == "lead"
        or (actor.role == "server" and audience == "server")
        or (actor.role == "cook" and audience == "kitchen"),
        "Session role cannot request this service audience",
    )
    all_orders = [
        o
        for o in state.orders.values()
        if actor.role == "lead" or audience == "kitchen" or o.owner == actor.id
    ]
    active = sorted(
        (o for o in all_orders if o.status not in {"draft", "delivered"}),
        key=lambda o: (o.created_at, o.id),
    )
    order_ids = {o.id for o in active}
    by_order = {o.id: o for o in active}
    dishes = sorted(
        (d for d in state.dishes.values() if d.order_id in order_ids),
        key=lambda d: (by_order[d.order_id].created_at, d.order_id, d.id),
    )
    order_views = []
    for order in active:
        units = [d for d in dishes if d.order_id == order.id]
        order_views.append(
            s.ServiceOrder(
                order_id=order.id,
                table_id=order.table_id,
                status=order.status,
                zone_status=order.zone_status,
                total=len(units),
                ready=sum(d.ready_at is not None for d in units),
                picked_up=sum(d.picked_up_at is not None for d in units),
                ready_for_pickup=sum(d.stage == "ready" for d in units),
                next_action=_order_action(order, audience),
            )
        )
    lineup = []
    for dish in dishes:
        if dish.stage == "picked_up":
            continue
        elapsed = (
            (generated_at - dish.started_at).total_seconds()
            if dish.started_at
            else None
        )
        lineup.append(
            s.ServiceDish(
                dish_id=dish.id,
                order_id=dish.order_id,
                table_id=by_order[dish.order_id].table_id,
                item_name=dish.item_name,
                modifier_names=dish.modifier_names,
                modifiers=dish.modifiers,
                seat=dish.seat,
                requests=dish.requests,
                zone_needs_review=bool(state.zones[dish.zone_id].needs_review)
                if dish.zone_id
                else False,
                stage=dish.stage,
                station=dish.station,
                zone_id=dish.zone_id,
                started_at=dish.started_at,
                typical_minutes=dish.typical_minutes,
                elapsed_seconds=int(elapsed)
                if elapsed is not None and elapsed >= 0
                else None,
                next_action=_next_dish_action(
                    dish,
                    by_order[dish.order_id],
                    audience,
                    state.zones.get(dish.zone_id),
                ),
            )
        )
    update_views = []
    for update in sorted(
        state.service_updates.values(), key=lambda u: (u.created_at, u.id)
    ):
        if update.status == "resolved":
            continue
        if (
            actor.role != "lead"
            and audience == "server"
            and update.recipient_id != actor.id
        ):
            continue
        order = state.orders[update.order_id]
        ready = sum(
            d.order_id == order.id and d.stage == "ready" for d in state.dishes.values()
        )
        actionable = order.status not in TERMINAL
        reason = "Explicit staff update; review the current ticket before acting."
        if not actionable:
            reason = "Order is already picked up/delivered; this update is historical."
        elif update.kind == "pickup_request" and not ready:
            actionable = False
            reason = (
                "No plates are currently ready for pickup; recheck the current ticket."
            )
        elif update.kind == "pickup_request":
            reason = f"{ready} physical units are currently ready for pickup; this may be a partial order."
        update_views.append(
            s.ServiceUpdateView(
                **update.model_dump(),
                currently_actionable=actionable,
                actionability_reason=reason,
                current_ready_for_pickup=ready,
            )
        )
    counts = s.ServiceCounts(
        orders=len(active),
        awaiting_acknowledgment=sum(o.acknowledged_at is None for o in active),
        waiting_for_zones=sum(o.zone_status == "waiting" for o in active),
        cooking_units=sum(d.stage == "started" for d in dishes),
        ready_for_pickup=sum(d.stage == "ready" for d in dishes),
        unread_updates=sum(u.status == "unread" for u in update_views),
        open_updates=len(update_views),
    )
    paragraphs = [
        f"{audience.title()} summary for {actor.name}. {counts.orders} active orders. "
        f"{counts.awaiting_acknowledgment} awaiting kitchen acknowledgment; "
        f"{counts.waiting_for_zones} waiting for zones; {counts.cooking_units} units started; "
        f"{counts.ready_for_pickup} units currently ready for pickup."
    ]
    for order in order_views:
        # Full order IDs disambiguate same-table tickets on screen and in speech.
        paragraphs.append(
            f"Table {order.table_id}, ticket {order.order_id}: {order.status}; "
            f"{order.ready} of {order.total} reached ready, {order.picked_up} picked up, "
            f"{order.ready_for_pickup} currently ready for pickup."
        )
    for order in active:
        grouped = Counter(
            (d.item_name, d.stage) for d in dishes if d.order_id == order.id
        )
        details = "; ".join(
            f"{count} {name} {stage.replace('_', ' ')}"
            for (name, stage), count in sorted(grouped.items())
        )
        paragraphs.append(
            f"Table {order.table_id}, ticket {order.id}, dish lineup: {details}."
        )
        unknown = sum(
            d.order_id == order.id and d.ready_at is not None and d.started_at is None
            for d in dishes
        )
        if unknown:
            paragraphs.append(
                f"{unknown} ready unit start times are unknown; cooking durations are unavailable for those units."
            )
    for update in update_views:
        order = state.orders[update.order_id]
        paragraphs.append(
            f"Staff update for table {order.table_id}, ticket {order.id}, "
            f"from {state.actors[update.sender_id].name} at {update.created_at.isoformat()}: "
            f"{update.kind.replace('_', ' ')}, {update.status}. "
            f"{update.note + '. ' if update.note else ''}{update.actionability_reason}"
        )
    return s.ServiceSummary(
        audience=audience,
        actor_id=actor.id,
        generated_at=generated_at,
        counts=counts,
        orders=order_views,
        lineup=lineup,
        updates=update_views,
        text="\n".join(paragraphs),
    )
