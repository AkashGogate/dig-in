"""Camera reconnection and health-state stability."""
import cv2
import numpy as np

from cvsvc.config import HealthConfig
from cvsvc.health import HealthMonitor
from cvsvc.sources import ReconnectingSource

FPS = 15


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeCam:
    """A webcam: dead while unplugged; after opening, needs `warmup` seconds before frames flow."""
    world = {"plugged": True}
    opens = 0

    def __init__(self, clock, warmup=1.5):
        FakeCam.opens += 1
        self.clock, self.warmup, self.opened = clock, warmup, clock()
        self.alive = FakeCam.world["plugged"]
        self.finite, self.loop = False, False

    def read(self):
        if not self.alive or not FakeCam.world["plugged"]:
            return None
        if self.clock() - self.opened < self.warmup:
            return None
        return np.zeros((4, 4, 3), np.uint8)

    def release(self):
        pass


def run(src, clock, seconds):
    got = 0
    for _ in range(int(seconds * FPS)):
        clock.t += 1 / FPS
        if src.read() is not None:
            got += 1
    return got


def test_reconnects_after_usb_dropout():
    clock = Clock()
    FakeCam.world["plugged"], FakeCam.opens = True, 0
    src = ReconnectingSource(lambda: FakeCam(clock), clock=clock)
    assert run(src, clock, 3) > 0                 # normal
    FakeCam.world["plugged"] = False              # USB hiccup: this handle is dead for good
    assert run(src, clock, 5) == 0
    FakeCam.world["plugged"] = True               # device back
    assert run(src, clock, 15) > 0, "should reopen and give the camera time to warm up"
    assert FakeCam.opens <= 6                     # backoff, not a reopen storm


def test_old_behaviour_would_never_recover():
    """Reopening every 0.5 s never lets a 1.5 s warm-up finish (the bug we hit live)."""
    clock = Clock()
    FakeCam.world["plugged"] = True
    cam, got = FakeCam(clock), 0
    for i in range(int(10 * FPS)):
        clock.t += 1 / FPS
        if cam.read() is not None:
            got += 1
        if i % int(0.5 * FPS) == 0:
            cam = FakeCam(clock)
    assert got == 0


def textured(seed=0):
    return np.random.default_rng(seed).integers(40, 220, (360, 640, 3), dtype=np.uint8)


def feed(hm, t, frame, seconds):
    states = []
    for _ in range(int(seconds * FPS)):
        t += 1 / FPS
        tr = hm.update(t, frame)
        if tr:
            states.append(tr.state)
    return t, states


def test_no_flicker_around_threshold():
    sharp = textured()
    soft = cv2.GaussianBlur(sharp, (7, 7), 0)  # focus well below 60% of the reference
    hm = HealthMonitor(HealthConfig(), reference=sharp)
    t, _ = feed(hm, 0.0, sharp, 3)
    transitions = []
    for i in range(20):                         # alternate every 0.5 s (plates on/off, hands...)
        t, s = feed(hm, t, soft if i % 2 else sharp, 0.5)
        transitions += s
    assert transitions == [], transitions


def test_sustained_drop_degrades_then_adapts():
    sharp = textured()
    soft = cv2.GaussianBlur(sharp, (7, 7), 0)
    hm = HealthMonitor(HealthConfig(baseline_tau_s=30), reference=sharp)
    t, _ = feed(hm, 0.0, sharp, 3)
    t, s = feed(hm, t, soft, 4)
    assert s == ["degraded"] and hm.reason == "focus_drop"
    t, s = feed(hm, t, soft, 60)                # the new scene becomes normal
    assert s == ["ok"]


def test_obstruction_still_immediate():
    hm = HealthMonitor(HealthConfig(), reference=textured())
    t, _ = feed(hm, 0.0, textured(), 3)
    t, s = feed(hm, t, np.full((360, 640, 3), 5, np.uint8), 0.2)
    assert s == ["obstructed"]


class Flaky(FakeCam):
    def __init__(self, clock):
        super().__init__(clock, warmup=0.0)
        self.n = 0

    def read(self):
        self.n += 1
        return None if self.n % 10 == 0 else np.zeros((4, 4, 3), np.uint8)  # drop every 10th frame


def test_single_dropped_frames_do_not_reopen():
    clock = Clock()
    FakeCam.world["plugged"], FakeCam.opens = True, 0
    src = ReconnectingSource(lambda: Flaky(clock), clock=clock)
    run(src, clock, 20)
    assert src.reopens == 0 and FakeCam.opens == 1


def test_process_source_streams_and_respawns(tmp_path):
    """Real child process reading a looping video; kill it and the wrapper brings it back."""
    import time

    from cvsvc.sources import ProcessFrameSource

    path = str(tmp_path / "clip.avi")
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 15, (320, 240))
    for i in range(30):
        vw.write(np.full((240, 320, 3), i * 8, np.uint8))
    vw.release()

    src = ReconnectingSource(lambda: ProcessFrameSource(path, (320, 240), 30), grace_s=3.0)

    def frames_within(seconds):
        n, end = 0, time.time() + seconds
        while time.time() < end:
            if src.read() is not None:
                n += 1
            time.sleep(0.02)
        return n

    assert frames_within(4) > 0          # child started and streams
    src.src._proc.kill()                # simulate the capture dying (USB dropout)
    assert frames_within(10) > 0, "should respawn the capture process"
    assert src.reopens >= 1
    src.release()


def test_resolve_camera_index_by_name(monkeypatch):
    import sys
    import types

    from cvsvc import sources

    class Dev:
        def __init__(self, name, uid):
            self._n, self._u = name, uid

        def localizedName(self):
            return self._n

        def uniqueID(self):
            return self._u

    def fake(devs):
        avf = types.SimpleNamespace(AVMediaTypeVideo="vide", AVMediaTypeMuxed="muxx")
        avf.AVCaptureDevice = types.SimpleNamespace(
            devicesWithMediaType_=lambda t: devs if t == "vide" else [])
        monkeypatch.setitem(sys.modules, "AVFoundation", avf)

    mac, brio = Dev("MacBook Air Camera", "6C70-0001"), Dev("Brio 105", "0x1110")
    fake([mac, brio])
    assert sources.resolve_camera_index("brio") == 0      # sorted by uniqueID, like OpenCV
    assert sources.resolve_camera_index("MacBook") == 1
    fake([mac])                                            # Brio mid re-plug
    assert sources.resolve_camera_index("Brio") is None    # never falls back to the MacBook
    assert sources.resolve_camera_index("MacBook") == 0
