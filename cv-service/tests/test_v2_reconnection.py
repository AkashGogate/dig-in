"""Synthetic reconnect proofs: no hardware or private frames are opened."""

import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from cvsvc import sources
from cvsvc.config import CameraConfig, HealthConfig
from cvsvc.health import HealthMonitor
from cvsvc.v2 import EvidenceSampler
from pydantic import ValidationError

from tests.test_v2_adapter import context
from tests.test_v2_circle_integration import worker


def test_canonical_health_first_unsafe_frame_closes_gate_and_never_adapts():
    ref = np.random.default_rng(5).integers(40, 220, (360, 640, 3), dtype=np.uint8)
    cfg = HealthConfig(
        allow_rebaseline=False,
        allow_baseline_adaptation=False,
        degraded_hold_s=0,
        warmup_s=0,
        big_change_fraction=1,
    )
    monitor = HealthMonitor(cfg, ref)
    monitor.update(100, ref)
    initial = (monitor.ref_lum, monitor.ref_focus)
    soft = cv2.GaussianBlur(ref, (7, 7), 0)
    tr = monitor.update(100.1, soft)
    assert tr is not None and tr.state == "degraded"
    for ts in np.arange(100.2, 250, 0.1):
        monitor.update(float(ts), soft)
    assert monitor.state == "degraded"
    assert (monitor.ref_lum, monitor.ref_focus) == initial


def test_canonical_warmup_cannot_supply_ready_dwell(tmp_path):
    pipeline, w, _, frame = worker(tmp_path)
    clock = [0.0]
    packets = []
    sampler = EvidenceSampler(packets.append, "warmup", False, clock=lambda: clock[0])
    sampler.set_context(context())
    pipeline.v2_sampler = sampler.sample
    bay = w.bays["A"]
    bay.motion.update = lambda _: False
    from cvsvc.plating.bays import PlateCount

    bay.counter.count = lambda _: PlateCount(1, 0.9, [])
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    for i in range(39):
        clock[0] = i / 10
        sampler.context_at = clock[0]
        ts = 100 + clock[0]
        w.health.update(ts, frame)
        w._process_bay(ts, frame, gray, "A", bay)
        if i < 35:
            assert not packets
    assert len(packets) == 1


def fake_avf(monkeypatch, video, muxed=()):
    class Device:
        def __init__(self, uid, name):
            self.uid, self.name = uid, name

        def uniqueID(self):
            return self.uid

        def localizedName(self):
            return self.name

    avf = SimpleNamespace(AVMediaTypeVideo="video", AVMediaTypeMuxed="muxed")
    avf.AVCaptureDevice = SimpleNamespace(
        devicesWithMediaType_=lambda kind: [
            Device(*d) for d in (video if kind == "video" else muxed)
        ]
    )
    monkeypatch.setitem(sys.modules, "AVFoundation", avf)


def test_names_are_unambiguous_preserve_original_indices_and_never_fall_back(
    monkeypatch,
):
    fake_avf(monkeypatch, [("a", "Other"), ("b", "Brio")], [("a", "Other")])
    assert sources.resolve_camera("Brio") == (2, "b")
    assert sources.resolve_camera_index("missing") is None
    assert sources.resolve_camera_index("") is None
    fake_avf(monkeypatch, [("a", "Brio"), ("b", "Brio")])
    assert sources.resolve_camera_index("brio") is None
    with pytest.raises(ValidationError, match="capture_process"):
        CameraConfig(name="Brio", capture_process=False)
    with pytest.raises(ValidationError, match="numeric source"):
        CameraConfig(name="Brio", source="http://stream")
    opened = []
    monkeypatch.setattr(cv2, "VideoCapture", lambda *args: opened.append(args))
    monkeypatch.setattr(sources.time, "sleep", lambda _: None)
    sources._capture_child(123, None, 15, None, name="brio")
    assert opened == []


class Pipe:
    def __init__(self, records):
        self.records = list(records)

    def poll(self):
        return bool(self.records)

    def recv(self):
        return self.records.pop(0)


def process_source(records):
    src = sources.ProcessFrameSource.__new__(sources.ProcessFrameSource)
    src._parent = Pipe(records)
    src._last_sequence = 0
    src._last_capture = None
    src.captured_at = src.captured_monotonic = src.camera_identity = None
    return src


def test_process_frames_keep_capture_time_and_reject_stale_duplicate_and_out_of_order(
    monkeypatch,
):
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    _, jpeg = cv2.imencode(".jpg", frame)
    packet = lambda seq, mono: (seq, 1000 + mono, mono, "calibrated-id", jpeg.tobytes())
    monkeypatch.setattr(sources.time, "monotonic", lambda: 10.0)
    src = process_source([packet(1, 9.0)])
    assert src.read() is None
    src._parent = Pipe([packet(2, 9.8)])
    assert src.read() is not None
    assert src.captured_at == 1009.8 and src.captured_monotonic == 9.8
    assert src.camera_identity == "calibrated-id"
    for record in [packet(2, 9.9), packet(3, 9.7), packet(4, 11.0)]:
        src._parent = Pipe([record])
        assert src.read() is None


def test_reconnect_refuses_replacement_identity_and_explicitly_quarantines(tmp_path):
    frame = np.zeros((4, 4, 3), np.uint8)
    first = SimpleNamespace(
        read=lambda: frame, release=lambda: None, camera_identity="original"
    )
    other = SimpleNamespace(
        read=lambda: frame, release=lambda: None, camera_identity="replacement"
    )
    src = sources.ReconnectingSource(lambda: first)
    assert src.read() is not None
    src.src = other
    assert src.read() is None and src.identity_changed
    src.src = first
    assert src.read() is None
    pipeline, w, _, _ = worker(tmp_path)
    called = []
    pipeline.v2_quarantine = lambda: called.append("review")
    w.health.first_frame_ts = 99
    w._v2_capture_gap(100)
    assert called == ["review"] and w.health.state == "lost"
    assert w.health.first_frame_ts is None


def test_buffered_pre_binding_frames_cannot_form_fresh_proof():
    clock = [10.0]
    packets = []
    sampler = EvidenceSampler(packets.append, "capture", False, clock=lambda: clock[0])
    sampler.set_context(context())
    for i in range(17):
        clock[0] = 10 + i / 10
        sampler.context_at = clock[0]
        sampler.sample(
            "A", 100 + clock[0], 1, False, "ok", 0.9, captured_monotonic=clock[0] - 0.2
        )
    assert not packets
    clock[0] = 11.8
    sampler.set_context(context(2, "new-order", "new-unit"))
    sampler.sample("A", 111.7, 1, False, "ok", 0.9, captured_monotonic=11.7)
    assert "A" not in sampler.candidates
    for i in range(18):
        clock[0] = 11.9 + i / 10
        sampler.set_context(context(2, "new-order", "new-unit"))
        sampler.sample(
            "A", 100 + clock[0], 1, False, "ok", 0.9, captured_monotonic=clock[0]
        )
    assert len(packets) == 1 and packets[0]["binding"]["dish_id"] == "new-unit"
    assert packets[0]["event"]["observed_at"].endswith("Z")


def test_same_assignment_reconciliation_restarts_full_dwell():
    clock = [10.0]
    packets = []
    sampler = EvidenceSampler(
        packets.append, "reconcile", False, clock=lambda: clock[0]
    )
    sampler.set_context(context())
    for i in range(14):
        clock[0] = 10 + i / 10
        sampler.sample("A", 100 + clock[0], 1, False, "ok", 0.9)
    clock[0] = 11.35
    reviewed = context()
    reviewed["zones"]["A"]["reconciliation_id"] = "explicit-new-review"
    sampler.set_context(reviewed)
    assert "A" not in sampler.candidates
    for i in range(18):
        clock[0] = 11.4 + i / 10
        sampler.set_context(reviewed)
        sampler.sample("A", 100 + clock[0], 1, False, "ok", 0.9)
        if i < 15:
            assert not packets
    assert len(packets) == 1


def test_reconnect_warmup_keeps_explicit_calibrated_background():
    ref = np.random.default_rng(15).integers(30, 190, (180, 320, 3), dtype=np.uint8)
    moved = 255 - ref
    cfg = HealthConfig(
        allow_rebaseline=False,
        allow_baseline_adaptation=False,
        degraded_hold_s=0,
        big_change_hold_s=0,
        big_change_fraction=0.2,
        warmup_s=2,
    )
    monitor = HealthMonitor(cfg, ref)
    original = monitor.bg.copy()
    monitor.update(100, ref)
    monitor.first_frame_ts = None  # same operation as capture-discontinuity recovery
    for ts in np.arange(103, 105, 0.1):
        monitor.update(float(ts), moved)
        assert np.array_equal(monitor.bg, original)
        assert not monitor.qualified
    monitor.update(105.1, moved)
    assert monitor.state == "obstructed"
    assert np.array_equal(monitor.bg, original)
