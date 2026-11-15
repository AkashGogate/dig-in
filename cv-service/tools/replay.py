"""Run the full CV pipeline on a recorded clip and write events.jsonl.

    python tools/replay.py clip.mp4 [--camera plating_cam] [--speed 1] [--config config/cv.yaml]
                                    [--out logs/replay_events.jsonl] [--context context.json]

Timestamps are clip time: observed_at = 1970-01-01T00:00:00Z + frame_index / fps, so
the output lines up with tools/label.py labels (which are also clip-relative).
--speed 0 runs as fast as possible. --context is an optional JSON file with the same
bodies the backend would PUT ({"bays": {...}, "claims": {...}, "active_ticket": {...}}).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cvsvc.config import load_config  # noqa: E402
from cvsvc.context import ActiveTicket, BayAssignment, Claim, ContextStore  # noqa: E402
from cvsvc.emitter import Emitter  # noqa: E402
from cvsvc.events import EventBus, EventIds  # noqa: E402
from cvsvc.pipeline import CameraPipelines  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--camera", default=None, help="which configured camera this clip is (default: plating camera)")
    ap.add_argument("--config", default="config/cv.yaml")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--out", default="logs/replay_events.jsonl")
    ap.add_argument("--context", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    camera = args.camera or cfg.plating.camera
    if camera not in cfg.cameras:
        raise SystemExit(f"unknown camera {camera}")
    cfg.cameras[camera].source = args.clip
    # only run modules bound to this camera
    if cfg.ingredient.camera != camera:
        cfg.ingredient.zones = []
    if cfg.plating.camera != camera:
        cfg.plating.bays = []

    ctx = ContextStore(active_ticket_ttl_s=1e12, clock=lambda: 0.0)
    if args.context:
        c = json.loads(Path(args.context).read_text())
        ctx.set_bays({k: (BayAssignment(**v) if v else None) for k, v in c.get("bays", {}).items()})
        ctx.set_claims({k: (Claim(**v) if v else None) for k, v in c.get("claims", {}).items()})
        if c.get("active_ticket"):
            ctx.set_active_ticket(ActiveTicket(**c["active_ticket"]))

    bus = EventBus(EventIds("replay"))
    pipes = CameraPipelines(cfg, bus, ctx, Emitter(bus.ids, ctx, cfg.ingredient.camera, cfg.plating.camera))
    w = pipes.workers[camera]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    f = out.open("w")
    n_events = 0

    def emit(ev):
        nonlocal n_events
        n_events += 1
        f.write(json.dumps(ev.model_dump(mode="json")) + "\n")

    w.emit = emit  # type: ignore[method-assign]
    cap = cv2.VideoCapture(args.clip)
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    idx, t_start = 0, time.time()
    proc_time = 0.0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if w.reference is None:
            w._build(w._load_reference(frame))
        ts = idx / fps
        t0 = time.perf_counter()
        w.process(ts, frame)
        proc_time += time.perf_counter() - t0
        idx += 1
        if args.speed > 0:
            lag = idx / fps / args.speed - (time.time() - t_start)
            if lag > 0:
                time.sleep(lag)
    f.close()
    print(f"{idx} frames, {n_events} events -> {out}; processing {idx / proc_time if proc_time else 0:.1f} FPS")


if __name__ == "__main__":
    main()
