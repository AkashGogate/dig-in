import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_metrics_table(tmp_path):
    def ev(t, type_, bay=None, zone=None, payload=None):
        s = f"1970-01-01T00:00:{t:06.3f}Z"
        return {"type": type_, "observed_at": s, "bay_id": bay, "zone_id": zone, "payload": payload or {}}
    events = [
        ev(10.5, "PLATE_ARRIVED", bay="A", payload={"delta": 1}),
        ev(20.4, "PLATE_REMOVED", bay="A", payload={"delta": 1}),
        ev(40.0, "PLATE_ARRIVED", bay="B", payload={"delta": 1}),  # false
        ev(30.6, "INGREDIENT_PICKED", zone="Z1", payload={"qty_delta": -2}),
        ev(50.9, "CAMERA_STATUS", payload={"state": "obstructed", "heartbeat": False}),
    ]
    labels = [
        {"t": 10.0, "kind": "plate_in", "target": "A", "qty": 1},
        {"t": 20.0, "kind": "plate_out", "target": "A", "qty": 1},
        {"t": 25.0, "kind": "plate_in", "target": "C", "qty": 1},  # missed
        {"t": 30.0, "kind": "pick", "target": "Z1", "qty": 2},
        {"t": 50.0, "kind": "obstruct_start", "target": None, "qty": 1},
        {"t": 55.0, "kind": "obstruct_end", "target": None, "qty": 1},
    ]
    (tmp_path / "e.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    (tmp_path / "l.jsonl").write_text("\n".join(json.dumps(l) for l in labels))
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "metrics.py"), str(tmp_path / "e.jsonl"),
                          str(tmp_path / "l.jsonl")], capture_output=True, text=True, check=True).stdout
    assert "| Plating | arrivals: missed | 1 (50%) |" in out
    assert "| Plating | arrivals: false | 1 |" in out
    assert "| Ingredient | picks: quantity errors | 0 of 1 matched |" in out
    assert "| Health | detection latency (mean / max) | 0.90 s / 0.90 s |" in out
