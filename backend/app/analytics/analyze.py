"""Portable calculations over canonical events; no cloud dependency.

python -m app.analytics.analyze ../backend/fixtures/analytics/ten_scripted_orders.jsonl
Missing endpoints and invalid chronology yield None, never a zero duration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

from app.analytics.events import CanonicalEvent

ELIGIBLE_AUTOMATION_ACTIONS = {
    "order.acknowledged",
    "dish.started",
    "dish.ready",
    "dish.picked_up",
}


def load(path: str | Path) -> list[CanonicalEvent]:
    return [
        CanonicalEvent.model_validate_json(line)
        for line in Path(path).read_text().splitlines()
        if line.strip()
    ]


def analyze(events: list[CanonicalEvent]) -> dict:
    unique: dict[str, CanonicalEvent] = {}
    for event in events:
        if event.event_id in unique and event != unique[event.event_id]:
            raise ValueError("Conflicting duplicate event_id")
        unique[event.event_id] = event
    rows = list(unique.values())
    if len({(event.run_id, event.simulated) for event in rows}) > 1:
        raise ValueError(
            "Analyze one run_id and simulated label at a time; filter mixed exports first"
        )
    accepted = [event for event in rows if event.outcome == "accepted"]
    order_ids = sorted({event.order_id for event in accepted if event.order_id})
    dish_orders = {event.dish_id: event.order_id for event in accepted if event.dish_id}
    for event in accepted:
        if event.type == "order.submitted":
            for dish in event.payload.get("dishes", []):
                if isinstance(dish, dict) and dish.get("dish_id"):
                    dish_orders[dish["dish_id"]] = event.order_id
    dish_ids = sorted(dish_orders)

    def first(records, event_type):
        times = [event.time for event in records if event.type == event_type]
        return min(times) if times else None

    def seconds(start, end):
        return (
            (end - start).total_seconds()
            if start is not None and end is not None and end >= start
            else None
        )

    order_timelines = []
    for order_id in order_ids:
        records = [event for event in accepted if event.order_id == order_id]
        times = {
            key: first(records, event_type)
            for key, event_type in {
                "submitted": "order.submitted",
                "acknowledged": "order.acknowledged",
                "zones_waiting": "zones.waiting",
                "zones_assigned": "zones.assigned",
                "first_started": "dish.started",
                "all_ready": "order.ready",
                "all_picked_up": "order.picked_up",
                "delivered": "order.delivered",
            }.items()
        }
        order_timelines.append(
            {
                "order_id": order_id,
                "simulated": all(e.simulated for e in records),
                **{
                    key: value.isoformat() if value else None
                    for key, value in times.items()
                },
                "submit_to_ack_s": seconds(times["submitted"], times["acknowledged"]),
                "ack_to_first_start_s": seconds(
                    times["acknowledged"], times["first_started"]
                ),
                "first_start_to_all_ready_s": seconds(
                    times["first_started"], times["all_ready"]
                ),
                "all_ready_to_all_pickup_s": seconds(
                    times["all_ready"], times["all_picked_up"]
                ),
                "zone_wait_s": seconds(times["zones_waiting"], times["zones_assigned"]),
                "delivery_censored": times["delivered"] is None,
            }
        )
    dish_timelines = []
    for dish_id in dish_ids:
        records = [event for event in accepted if event.dish_id == dish_id]
        start, ready, pickup = [
            first(records, key)
            for key in ("dish.started", "dish.ready", "dish.picked_up")
        ]
        dish_timelines.append(
            {
                "dish_id": dish_id,
                "order_id": dish_orders[dish_id],
                "started": start.isoformat() if start else None,
                "ready": ready.isoformat() if ready else None,
                "picked_up": pickup.isoformat() if pickup else None,
                "started_to_ready_s": seconds(start, ready),
                "ready_to_pickup_s": seconds(ready, pickup),
                "ready_censored": ready is None,
                "pickup_censored": pickup is None,
                "invalid_chronology": bool(
                    (ready and start and ready < start)
                    or (pickup and ready and pickup < ready)
                ),
            }
        )
    eligible = [
        event for event in accepted if event.type in ELIGIBLE_AUTOMATION_ACTIONS
    ]
    tap = [event for event in eligible if event.source == "tap"]
    known = [
        event
        for event in eligible
        if event.payload.get("automation_available") is not None
    ]
    unavailable_taps = [
        event for event in tap if event.payload.get("automation_available") is False
    ]
    confirmed = [event for event in accepted if event.type == "order.submitted"]
    voice_confirmed = [
        event
        for event in confirmed
        if event.payload.get("capture_mode") in ("mock_voice", "live_voice")
    ]
    corrected = sum(
        event.payload.get("corrected_draft_lines", 0) for event in voice_confirmed
    )
    baseline = sum(
        event.payload.get("initial_voice_draft_line_count", 0)
        for event in voice_confirmed
    )

    def metric(values):
        observed = [value for value in values if value is not None]
        return {
            "n_observed": len(observed),
            "n_censored_or_missing": len(values) - len(observed),
            "median_seconds": median(observed) if observed else None,
        }

    waiting_rows = [row for row in order_timelines if row["zones_waiting"] is not None]
    stage_metrics = {
        key: metric([row[key] for row in order_timelines])
        for key in (
            "submit_to_ack_s",
            "ack_to_first_start_s",
            "first_start_to_all_ready_s",
            "all_ready_to_all_pickup_s",
        )
    }
    stage_metrics["zone_wait_s"] = {
        **metric([row["zone_wait_s"] for row in waiting_rows]),
        "n_not_waiting": len(order_timelines) - len(waiting_rows),
    }
    return {
        "dataset": "SIMULATED"
        if rows and all(e.simulated for e in rows)
        else "NOT_LABELLED_SIMULATED",
        "event_count": len(rows),
        "input_duplicate_count": len(events) - len(rows),
        "order_count": len(order_ids),
        "dish_count": len(dish_ids),
        "order_timelines": order_timelines,
        "dish_timelines": dish_timelines,
        "stage_metrics": stage_metrics,
        "ready_to_pickup": metric([row["ready_to_pickup_s"] for row in dish_timelines]),
        "voice_corrections": {
            "orders": len(voice_confirmed),
            "corrected_draft_lines": corrected,
            "initial_voice_draft_lines": baseline,
            "corrections_per_initial_voice_line": corrected / baseline
            if baseline
            else None,
        },
        "automation": {
            "eligible_actions": len(eligible),
            "tap_actions": len(tap),
            "manual_action_share": len(tap) / len(eligible) if eligible else None,
            "availability_known_actions": len(known),
            "confirmed_unavailable_tap_actions": len(unavailable_taps),
            "confirmed_unavailable_tap_share": len(unavailable_taps) / len(known)
            if known
            else None,
            "unknown_availability_tap_actions": sum(
                event.payload.get("automation_available") is None for event in tap
            ),
        },
        "camera": {
            "blocked_status_events": sum(
                e.type == "camera.status" and e.payload.get("status") == "blocked"
                for e in rows
            ),
            "offline_status_events": sum(
                e.type == "camera.status" and e.payload.get("status") == "offline"
                for e in rows
            ),
            "unexpected_zone_events": sum(e.type == "zone.unexpected" for e in rows),
        },
        "inventory_recipe_comparison": "not_computed: ingredient detection remains a reviewed scaffold",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--summary", action="store_true", help="Omit detailed timelines"
    )
    args = parser.parse_args()
    report = analyze(load(args.path))
    if args.summary:
        report.pop("order_timelines")
        report.pop("dish_timelines")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
