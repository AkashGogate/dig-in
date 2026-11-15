"""Shape branch integration preserves canonical evidence and health boundaries."""

from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from cvsvc.config import BayConfig, CameraConfig, CVConfig, HealthConfig, PlatingConfig
from cvsvc.context import ContextStore
from cvsvc.emitter import Emitter
from cvsvc.events import EventBus
from cvsvc.health import HealthMonitor
from cvsvc.pipeline import CameraPipelines
from cvsvc.plating.bays import PlateCount
from cvsvc.plating.circles import Plate


def worker(tmp_path):
    cfg = CVConfig(
        cameras={"cam": CameraConfig()},
        plating=PlatingConfig(
            camera="cam",
            detector="circles",
            max_plates_per_bay=4,
            plate_min_radius_px=20,
            plate_max_radius_px=70,
            bays=[
                BayConfig(id="A", polygon=[(0, 0), (199, 0), (199, 199), (0, 199)]),
                BayConfig(id="B", polygon=[(200, 0), (399, 0), (399, 199), (200, 199)]),
            ],
        ),
        calibration_dir=str(tmp_path),
    )
    context = ContextStore()
    bus = EventBus()
    pipeline = CameraPipelines(
        cfg, bus, context, Emitter(bus.ids, context, "cam", "cam")
    )
    captures = []
    pipeline.v2_sampler = lambda *args: captures.append(args)
    result = pipeline.workers["cam"]
    result.emit = lambda _: None
    frame = np.full((200, 400, 3), 80, dtype=np.uint8)
    result._build(frame)
    result.v2_hand_present = False
    return pipeline, result, captures, frame


def test_circle_confidence_uses_same_frame_counter_and_withholds_disagreement(tmp_path):
    _pipeline, w, captures, frame = worker(tmp_path)
    bay = w.bays["A"]
    bay.counter.count = lambda _: PlateCount(1, 0.42, [])
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    w._process_bay(100, frame, gray, "A", bay, PlateCount(1, 1.0, []))
    assert captures[-1][-1] == 0.42
    w._process_bay(100.1, frame, gray, "A", bay, PlateCount(0, 1.0, []))
    assert captures[-1][-1] == 0.0
    # Real hand guard cannot be bypassed by motionless snapshots.
    w.v2_hand_present = None
    w._process_bay(100.2, frame, gray, "A", bay, PlateCount(1, 1.0, []))
    assert captures[-1][3] is True


def test_ambiguous_circle_footprint_and_overflow_are_not_relabelled_single_unit(
    tmp_path,
):
    _pipeline, w, captures, frame = worker(tmp_path)
    w.plate_finder = SimpleNamespace(find=lambda _: [Plate(180, 100, 45)])
    counts = w._circle_counts(frame)
    assert counts["A"].count == 1 and counts["B"].count == 0
    assert w.v2_circle_ambiguous == {"A", "B"}
    bay = w.bays["A"]
    bay.counter.count = lambda _: PlateCount(1, 0.95, [])
    w._process_bay(
        100, frame, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), "A", bay, counts["A"]
    )
    assert captures[-1][-1] == 0.0
    neighbour = w.bays["B"]
    neighbour.counter.count = lambda _: PlateCount(0, 0.95, [])
    w._process_bay(
        100, frame, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), "B", neighbour, counts["B"]
    )
    assert captures[-1][-1] == 0.0  # overlapping plate cannot establish neighbour empty
    w.plate_finder = SimpleNamespace(
        find=lambda _: [Plate(60, 60, 25), Plate(130, 130, 25)]
    )
    counts = w._circle_counts(frame)
    assert counts["A"].count == 2
    assert not w.v2_circle_ambiguous


def test_canonical_health_does_not_rebaseline_static_obstruction():
    rng = np.random.default_rng(10)
    empty = rng.integers(30, 190, (180, 320, 3), dtype=np.uint8)
    obstruction = 255 - empty

    def final_state(allow):
        cfg = HealthConfig(
            allow_rebaseline=allow,
            warmup_s=0.1,
            big_change_hold_s=0.1,
            rebaseline_s=0.5,
            big_change_fraction=0.2,
            dark_threshold=0,
            blur_threshold=0,
            degraded_light_shift=10,
            degraded_focus_drop=1,
        )
        monitor = HealthMonitor(cfg, empty)
        monitor.update(100, empty)
        monitor.update(100.2, empty)
        for ts in np.arange(100.3, 102, 0.1):
            monitor.update(float(ts), obstruction)
        return monitor

    strict = final_state(False)
    legacy = final_state(True)
    assert strict.state == "obstructed"
    assert legacy.state == "ok"


def test_canonical_cli_disables_rebaseline_and_refuses_plate_clamp(monkeypatch):
    import sys

    from cvsvc import v2

    cfg = CVConfig(plating=PlatingConfig(max_plates_per_bay=1))
    monkeypatch.setattr(v2, "load_config", lambda _: cfg)
    monkeypatch.setattr(sys, "argv", ["v2"])
    with pytest.raises(ValueError, match="overflow"):
        v2.main()
    assert cfg.health.allow_rebaseline is False
    assert cfg.health.allow_baseline_adaptation is False
    assert cfg.health.degraded_hold_s == 0


def test_circle_centred_in_gap_with_one_overlapped_zone_cannot_certify_empty(tmp_path):
    _pipeline, w, captures, frame = worker(tmp_path)
    w.bays["A"].cfg.polygon = [(0, 0), (159, 0), (159, 199), (0, 199)]
    w.bays["B"].cfg.polygon = [(240, 0), (399, 0), (399, 199), (240, 199)]
    w.plate_finder = SimpleNamespace(find=lambda _: [Plate(190, 100, 40)])
    counts = w._circle_counts(frame)
    assert counts["A"].count == 0 and w.v2_circle_ambiguous == {"A"}
    bay = w.bays["A"]
    bay.counter.count = lambda _: PlateCount(0, 0.95, [])
    w._process_bay(
        100, frame, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), "A", bay, counts["A"]
    )
    assert captures[-1][-1] == 0.0
