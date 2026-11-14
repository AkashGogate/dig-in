"""Canonical export privacy, identity, retry and censored-metric invariants."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.analytics.analyze import analyze, load
from app.analytics.events import CanonicalEvent
from app.analytics.outbox import FakeAdapter, JsonlAdapter, Outbox

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "analytics"
    / "ten_scripted_orders.jsonl"
)


def event(event_id="one", **changes):
    return CanonicalEvent.model_validate(
        {
            "event_id": event_id,
            "order_id": "order-1",
            "dish_id": "dish-1",
            "type": "dish.ready",
            "source": "camera",
            "actor": "camera-device",
            "time": "2026-11-14T15:42:07-06:00",
            "received_at": "2026-11-14T21:42:07.100Z",
            "run_id": "sim-test",
            "simulated": True,
            "payload": {"zone_id": "A", "assignment_version": 1},
            **changes,
        }
    )


def test_canonical_event_preserves_source_time_identity_and_rejects_naive_time():
    original = event()
    exported = original.export()
    assert exported["event_id"] == "one"
    assert exported["time"] == "2026-11-14T15:42:07-06:00"
    assert exported["received_at"] != exported["time"]
    assert CanonicalEvent.model_validate(exported) == original
    with pytest.raises(ValidationError):
        event(time="2026-11-14T15:42:07")
    with pytest.raises(ValidationError):
        event(
            source="mock_camera"
        )  # v1 source must be mapped explicitly, not redefined


@pytest.mark.parametrize("key", ["transcript", "raw_audio", "video", "raw_text"])
def test_capture_content_cannot_enter_canonical_analytics(key):
    with pytest.raises(ValidationError, match="excluded"):
        event(payload={"metadata": [{key: "secret capture content"}]})


def test_outbox_retries_without_losing_rows_or_duplicating_sink():
    outbox = Outbox()
    original = event()
    outbox.enqueue([original, original])
    adapter = FakeAdapter(failures_remaining=1)
    failed = outbox.drain(adapter)
    assert failed["pending"] == 1
    assert failed["sent"] == 0
    assert failed["last_error"]
    assert failed["pending_attempts"]["one"] == 1
    assert outbox.pending() == [original.export()]
    healthy = outbox.drain(adapter)
    assert healthy["pending"] == 0
    assert healthy["sent"] == 1
    assert healthy["last_error"] is None
    assert adapter.events == {original.event_id: original.export()}
    outbox.enqueue([original])
    outbox.drain(adapter)
    assert outbox.health()["sent"] == 1


def test_changed_duplicate_id_rejected_atomically():
    outbox = Outbox()
    outbox.enqueue([event()])
    with pytest.raises(ValueError, match="changed"):
        outbox.enqueue([event("two"), event(payload={"zone_id": "wrong-zone"})])
    assert [row["event_id"] for row in outbox.pending()] == ["one"]


def test_slow_export_does_not_hold_enqueue_lock():
    started, release = threading.Event(), threading.Event()

    class SlowSink:
        def send(self, events):
            started.set()
            assert release.wait(2)

    outbox = Outbox()
    outbox.enqueue([event()])
    worker = threading.Thread(target=outbox.drain, args=(SlowSink(),))
    worker.start()
    assert started.wait(2)
    # This must complete while the external sink is still blocked.
    outbox.enqueue([event("two")])
    assert outbox.health()["pending"] == 2
    release.set()
    worker.join(2)
    assert not worker.is_alive()
    assert [row["event_id"] for row in outbox.pending()] == ["two"]


def test_jsonl_sink_retry_keeps_exact_canonical_rows(tmp_path):
    path = tmp_path / "events.jsonl"
    sink = JsonlAdapter(path)
    sink.send([event()])
    sink.send([event()])
    assert len(path.read_text().splitlines()) == 1
    assert load(path) == [event()]
    with pytest.raises(ValueError, match="Conflicting"):
        sink.send([event(payload={"zone_id": "changed"})])


def test_fixture_has_ten_labelled_orders_and_incomplete_units():
    events = load(FIXTURE)
    report = analyze(events)
    assert len(events) == report["event_count"] == 106
    assert report["dataset"] == "SIMULATED"
    assert report["order_count"] == 10
    assert report["dish_count"] == 20
    assert all(
        row.simulated and row.run_id and row.payload["scenario"] for row in events
    )
    assert report["ready_to_pickup"] == {
        "n_observed": 14,
        "n_censored_or_missing": 6,
        "median_seconds": 25.0,
    }
    queued = next(
        row for row in report["dish_timelines"] if row["dish_id"] == "sim-order-04-1"
    )
    assert queued["started"] is None and queued["ready_to_pickup_s"] is None
    assert report["stage_metrics"]["zone_wait_s"] == {
        "n_observed": 2,
        "n_censored_or_missing": 0,
        "median_seconds": 30.0,
        "n_not_waiting": 8,
    }


def test_required_confirmation_is_not_fallback_and_unknown_availability_is_separate():
    report = analyze(load(FIXTURE))
    assert report["automation"] == {
        "eligible_actions": 59,
        "tap_actions": 14,
        "manual_action_share": 14 / 59,
        "availability_known_actions": 52,
        "confirmed_unavailable_tap_actions": 7,
        "confirmed_unavailable_tap_share": 7 / 52,
        "unknown_availability_tap_actions": 7,
    }
    assert report["voice_corrections"] == {
        "orders": 8,
        "corrected_draft_lines": 4,
        "initial_voice_draft_lines": 16,
        "corrections_per_initial_voice_line": 0.25,
    }
    assert report["camera"] == {
        "blocked_status_events": 1,
        "offline_status_events": 1,
        "unexpected_zone_events": 1,
    }


def test_missing_or_out_of_order_stages_never_become_zero_duration():
    ready = event("ready", time="2026-11-14T21:42:07Z")
    pickup = event("pickup", type="dish.picked_up", time="2026-11-14T21:41:07Z")
    observed = event("raw", type="camera.observation", outcome="observed")
    report = analyze([ready, pickup, observed])
    dish = report["dish_timelines"][0]
    assert dish["started_to_ready_s"] is None
    assert dish["ready_to_pickup_s"] is None
    assert dish["invalid_chronology"]
    assert analyze([observed])["dish_count"] == 0


def test_duplicate_fixture_events_do_not_inflate_analysis_rows():
    events = load(FIXTURE)
    report = analyze(events + [events[0]])
    assert report["event_count"] == 106
    assert report["input_duplicate_count"] == 1
    with pytest.raises(ValueError, match="Conflicting"):
        analyze([event(), event(payload={"zone": "other"})])


def test_mixed_runs_are_not_silently_merged_into_timelines():
    with pytest.raises(ValueError, match="one run_id"):
        analyze([event("a"), event("b", run_id="different-run")])
    with pytest.raises(ValueError, match="simulated label"):
        analyze([event("a"), event("b", simulated=False)])
