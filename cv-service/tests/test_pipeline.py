"""Full per-frame pipeline on synthetic frames (no camera, no threads)."""
import cv2
import numpy as np
import pytest

from cvsvc.config import BayConfig, CameraConfig, CVConfig, IngredientConfig, PlatingConfig, SlotGrid, ZoneConfig
from cvsvc.context import ActiveTicket, BayAssignment, Claim, ContextStore
from cvsvc.emitter import Emitter
from cvsvc.events import EventBus, EventIds, utcnow_iso
from cvsvc.pipeline import CameraPipelines

W, H = 640, 480
FPS = 15
ZONE_POLY = [(40, 60), (360, 60), (360, 220), (40, 220)]  # 2 x 4 slots of 80 x 80
BAY_POLY = [(380, 240), (630, 240), (630, 470), (380, 470)]


def base():
    img = np.full((H, W, 3), 70, np.uint8)
    img += np.random.default_rng(1).integers(0, 5, (H, W, 3), dtype=np.uint8)
    return img


def slot_center(i):
    r, c = divmod(i, 4)
    return 40 + c * 80 + 40, 60 + r * 80 + 40


def scene(tokens=(), plates=(), hand=None, img=None):
    img = base() if img is None else img
    for i in tokens:
        cv2.circle(img, slot_center(i), 28, (30, 30, 220), -1)  # red tokens
    for c in plates:
        cv2.circle(img, c, 50, (235, 235, 235), -1)
    if hand is not None:
        x, y = hand
        cv2.rectangle(img, (x, y), (x + 120, y + 260), (120, 160, 220), -1)  # arm
    return img


@pytest.fixture
def setup(tmp_path):
    cfg = CVConfig(
        cameras={"cam": CameraConfig(source=0, fps_target=FPS)},
        ingredient=IngredientConfig(camera="cam", settle_s=0.5, zones=[
            ZoneConfig(id="Z1", ingredient="token", polygon=ZONE_POLY, slots=SlotGrid(rows=2, cols=4))]),
        plating=PlatingConfig(camera="cam", debounce_s=0.5, bays=[
            BayConfig(id="A", polygon=BAY_POLY, min_plate_area_px=4000, max_plate_area_px=20000)]),
        calibration_dir=str(tmp_path),
    )
    ctx = ContextStore()
    bus = EventBus(EventIds("t"))
    pipes = CameraPipelines(cfg, bus, ctx, Emitter(bus.ids, ctx, "cam", "cam"))
    w = pipes.workers["cam"]
    events = []
    w.emit = lambda ev: events.append(ev.model_dump(mode="json"))
    w._build(scene())  # empty reference
    clock = {"t": 1000.0}

    def feed(img, seconds):
        for _ in range(int(seconds * FPS)):
            clock["t"] += 1 / FPS
            w.process(clock["t"], img)

    return w, ctx, events, feed, clock


def of(events, t):
    return [e for e in events if e["type"] == t]


def test_ingredient_pick_attribution_and_no_event_on_wave(setup):
    w, ctx, events, feed, clock = setup
    stocked = scene(tokens=range(8))
    feed(stocked, 1.0)
    assert of(events, "ZONE_SNAPSHOT")[0]["payload"]["count"] == 8
    # wave a hand over the zone without taking anything
    feed(scene(tokens=range(8), hand=(150, 0)), 1.0)
    feed(stocked, 2.0)
    assert of(events, "INGREDIENT_PICKED") == []
    # set active ticket, take 2 tokens
    ctx.set_active_ticket(ActiveTicket(ticket_id="T-7", set_at=utcnow_iso()))  # TTL uses wall time
    feed(scene(tokens=range(8), hand=(150, 0)), 0.7)
    feed(scene(tokens=range(6), hand=(150, 0)), 0.5)
    feed(scene(tokens=range(6)), 2.0)
    picks = of(events, "INGREDIENT_PICKED")
    assert len(picks) == 1
    p = picks[0]
    assert p["payload"]["qty_delta"] == -2 and p["payload"]["count_after"] == 6
    assert p["attribution"]["ticket_id"] == "T-7"


def test_plate_arrival_removal_with_context(setup):
    w, ctx, events, feed, _ = setup
    feed(scene(), 1.0)
    assert of(events, "BAY_STATE")[0]["payload"]["plate_count"] == 0
    ctx.set_bays({"A": BayAssignment(ticket_id="T-1", table="12", course="main", expected_plates=1)})
    feed(scene(hand=(450, 250)), 0.6)                 # arm reaching in
    feed(scene(plates=[(505, 355)], hand=(450, 250)), 0.4)
    feed(scene(plates=[(505, 355)]), 1.5)             # settled
    arr = of(events, "PLATE_ARRIVED")
    assert len(arr) == 1 and arr[0]["payload"]["count_matches_expected"] is True
    ctx.set_claims({"A": Claim(task_id="RUN-1", server_id="s1")})
    feed(scene(), 1.5)
    rem = of(events, "PLATE_REMOVED")
    assert len(rem) == 1 and rem[0]["payload"]["claimed_task_id"] == "RUN-1" and rem[0]["payload"]["bay_now_empty"]


def test_obstruction_freezes_and_reconciles(setup):
    w, ctx, events, feed, _ = setup
    feed(scene(tokens=range(8)), 1.0)
    n = len(events)
    dark = np.full((H, W, 3), 5, np.uint8)
    feed(dark, 0.2)
    status = of(events[n:], "CAMERA_STATUS")
    assert status and status[0]["payload"]["state"] == "obstructed"
    feed(dark, 2.0)
    assert {e["type"] for e in events[n:]} == {"CAMERA_STATUS"}  # nothing else while obstructed
    # tokens were taken while covered and a plate was put down
    feed(scene(tokens=range(5), plates=[(505, 355)]), 3.0)
    pend = of(events, "INGREDIENT_CHANGE_PENDING")
    assert len(pend) == 1 and pend[0]["payload"]["reason"] == "post_obstruction_mismatch"
    assert pend[0]["payload"]["count_before"] == 8 and pend[0]["payload"]["count_after_estimate"] == 5
    recount = [e for e in of(events, "BAY_STATE") if e["payload"]["note"] == "post_obstruction_recount"]
    assert recount and recount[0]["payload"]["plate_count"] == 1
    assert of(events, "PLATE_ARRIVED") == []  # recount is not an arrival


def test_performance_two_modules_over_10fps(setup):
    import time
    w, *_ = setup
    img = scene(tokens=range(8), plates=[(505, 355)])
    t = time.time()
    for i in range(60):
        w.process(2000 + i / FPS, img)
    per_frame = (time.time() - t) / 60
    assert per_frame < 0.05, f"{per_frame * 1000:.1f} ms/frame"


def test_worker_thread_on_video_file(setup, tmp_path):
    """Run the real camera loop on a generated video: plate appears, events come out."""
    import threading
    import time

    w, ctx, events, _, _ = setup
    path = str(tmp_path / "clip.avi")
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))
    for _ in range(FPS):
        vw.write(scene())
    for _ in range(FPS * 6):
        vw.write(scene(plates=[(505, 355)]))
    vw.release()
    w.ccfg.source = path
    w.ccfg.fps_target = 45  # run faster than real time
    w.reference = None      # load reference from the first frame
    w.cfg.health.heartbeat_s = 0.2
    t = threading.Thread(target=w.run, daemon=True)
    t.start()
    end = time.time() + 5
    while time.time() < end and not of(events, "PLATE_ARRIVED"):
        time.sleep(0.05)
    w.stop.set()
    t.join(2)
    assert of(events, "PLATE_ARRIVED"), [e["type"] for e in events]
    assert of(events, "CAMERA_STATUS")
    assert w.overlay_seq > 0
