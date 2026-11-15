"""Record a clip and press keys to log ground-truth moments.

    python tools/label.py --source 1 --out recordings/run1   (writes run1.mp4 + run1.labels.jsonl)

Keys:  a/b/c  plate placed on bay A/B/C       z/x/v  plate removed from bay A/B/C
       1-4    one portion picked from Z1-Z4   5-8    one portion returned to Z1-Z4
       o      obstruction starts              k      obstruction ends
       u      undo last label                 q/Esc  stop
Repeated pick/return presses for the same zone within 1.5 s merge into one label with qty.
Times are seconds from the clip start (matches tools/replay.py output).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2

KEYS = {
    "a": ("plate_in", "A"), "b": ("plate_in", "B"), "c": ("plate_in", "C"),
    "z": ("plate_out", "A"), "x": ("plate_out", "B"), "v": ("plate_out", "C"),
    "1": ("pick", "Z1"), "2": ("pick", "Z2"), "3": ("pick", "Z3"), "4": ("pick", "Z4"),
    "5": ("return", "Z1"), "6": ("return", "Z2"), "7": ("return", "Z3"), "8": ("return", "Z4"),
    "o": ("obstruct_start", None), "k": ("obstruct_end", None),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0")
    ap.add_argument("--out", required=True, help="path prefix, e.g. recordings/run1")
    ap.add_argument("--fps", type=float, default=15)
    args = ap.parse_args()

    src = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(src)
    ok, frame = cap.read()
    if not ok:
        raise SystemExit("cannot read from source")
    prefix = Path(args.out)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    h, w = frame.shape[:2]
    vw = cv2.VideoWriter(str(prefix) + ".mp4", cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (w, h))
    labels: list[dict] = []
    n = 0
    period = 1 / args.fps
    while True:
        t0 = time.time()
        ok, frame = cap.read()
        if not ok:
            break
        vw.write(frame)
        t = n / args.fps  # clip time, frame-accurate
        n += 1
        show = frame.copy()
        last = labels[-1] if labels else None
        txt = f"t={t:6.1f}s  labels={len(labels)}" + (f"  last: {last['kind']} {last['target'] or ''} x{last.get('qty', 1)}" if last else "")
        cv2.putText(show, txt, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imshow("dig-in label", show)
        k = cv2.waitKey(1) & 0xFF
        if k in (ord("q"), 27):
            break
        ch = chr(k) if k < 128 else ""
        if ch == "u" and labels:
            labels.pop()
        elif ch in KEYS:
            kind, target = KEYS[ch]
            if kind in ("pick", "return") and last and last["kind"] == kind and last["target"] == target \
                    and t - last["t_last"] <= 1.5:
                last["qty"] += 1
                last["t_last"] = t
            else:
                labels.append({"t": round(t, 2), "t_last": t, "kind": kind, "target": target, "qty": 1})
        dt = period - (time.time() - t0)
        if dt > 0:
            time.sleep(dt)
    vw.release()
    cap.release()
    cv2.destroyAllWindows()
    with open(str(prefix) + ".labels.jsonl", "w") as f:
        for lab in labels:
            lab.pop("t_last", None)
            f.write(json.dumps(lab) + "\n")
    print(f"{n} frames, {len(labels)} labels -> {prefix}.mp4 / {prefix}.labels.jsonl")


if __name__ == "__main__":
    main()
