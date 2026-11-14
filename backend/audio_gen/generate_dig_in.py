"""Generates the DIG IN voice eval corpus: Server orders and Kitchen callouts,
each rendered clean, over a kitchen noise bed, and with an overlapping second
speaker. macOS `say` + numpy/soundfile mixing, same approach as
generate_samples.py. No network or API key.

Synthetic TTS is not a real kitchen: these clips exercise the pipeline and give
a repeatable baseline, they do not establish noisy-hall accuracy.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000
OUT_DIR = Path(__file__).resolve().parents[2] / "audio-samples" / "dig-in"
MANIFEST_PATH = OUT_DIR / "manifest.json"
CHATTER = "can somebody grab a refill for table nine"

# (name, flow, transcript, selected_table, expected outcomes; any one passes)
SCENARIOS = [
    (
        "server_two_dishes_modifier",
        "server",
        "Table four, two bulldozers, hold the pickles, and one dirt site",
        "4",
        [
            {
                "table_id": "4",
                "lines": [
                    {
                        "menu_id": "bulldozer",
                        "quantity": 2,
                        "modifiers": ["no_pickles"],
                    },
                    {"menu_id": "dirt_site", "quantity": 1, "modifiers": []},
                ],
                "flag_codes": [],
            }
        ],
    ),
    (
        "server_internal_and",
        "server",
        "Table two, one mac and cheese and three tots",
        "2",
        [
            {
                "table_id": "2",
                "lines": [
                    {"menu_id": "cement_mixer_mac", "quantity": 1, "modifiers": []},
                    {"menu_id": "gravel_pit_tots", "quantity": 3, "modifiers": []},
                ],
                "flag_codes": [],
            }
        ],
    ),
    (
        "server_table_mismatch",
        "server",
        "Table three, one backhoe without slaw",
        "1",
        [
            {
                "table_id": "3",
                "lines": [
                    {"menu_id": "backhoe", "quantity": 1, "modifiers": ["no_slaw"]}
                ],
                "flag_codes": ["table_mismatch"],
            }
        ],
    ),
    (
        "server_misheard_name",
        "server",
        "Table one, one bull dozer",
        "1",
        [
            # Transcript keeps the split word: no guess, a review candidate.
            {
                "table_id": "1",
                "lines": [],
                "flag_codes": ["unknown_item", "no_items"],
                "candidates": ["bulldozer"],
            },
            # STT (keyterms) normalizes it: the exact match is also correct.
            {
                "table_id": "1",
                "lines": [{"menu_id": "bulldozer", "quantity": 1, "modifiers": []}],
                "flag_codes": [],
            },
        ],
    ),
    (
        "kitchen_heard",
        "kitchen",
        "Heard, table four",
        None,
        [{"action": "acknowledge", "table_id": "4", "menu_id": None}],
    ),
    (
        "kitchen_start",
        "kitchen",
        "Start table four bulldozer",
        None,
        [{"action": "start_dish", "table_id": "4", "menu_id": "bulldozer"}],
    ),
]


def _say(text: str, voice: str = "Samantha") -> np.ndarray:
    tmp = OUT_DIR / "_tmp_say.wav"
    subprocess.run(
        [
            "say",
            "-v",
            voice,
            "-o",
            str(tmp),
            "--file-format=WAVE",
            f"--data-format=LEI16@{SAMPLE_RATE}",
            text,
        ],
        check=True,
        capture_output=True,
    )
    audio, sr = sf.read(tmp, dtype="float32")
    assert sr == SAMPLE_RATE
    tmp.unlink()
    return audio


def _kitchen_noise(length: int, seed: int) -> np.ndarray:
    """Fan-like rumble (smoothed noise) plus short clatter bursts."""
    rng = np.random.default_rng(seed)
    rumble = np.convolve(rng.normal(0, 1, length), np.ones(40) / 40, mode="same")
    rumble *= 0.05 / (np.sqrt(np.mean(rumble**2)) + 1e-9)
    clatter = np.zeros(length)
    for start in rng.integers(0, max(1, length - 800), size=4):
        burst = rng.normal(0, 0.25, 800) * np.exp(-np.linspace(0, 6, 800))
        clatter[start : start + 800] += burst
    return (rumble + clatter).astype("float32")


def _render(text: str, condition: str, seed: int) -> np.ndarray:
    speech = _say(text)
    if condition == "noise":
        return np.clip(speech + _kitchen_noise(len(speech), seed), -1.0, 1.0)
    if condition == "overlap":
        other = _say(CHATTER, voice="Daniel") * 0.6
        start = int(len(speech) * 0.4)
        out = np.zeros(max(len(speech), start + len(other)), dtype="float32")
        out[: len(speech)] += speech
        out[start : start + len(other)] += other
        return np.clip(out, -1.0, 1.0)
    return speech


def generate() -> list[dict]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for n, (name, flow, transcript, table, expected) in enumerate(SCENARIOS):
        for condition in ("clean", "noise", "overlap"):
            clip = f"{name}__{condition}"
            audio = _render(transcript, condition, seed=n)
            sf.write(OUT_DIR / f"{clip}.wav", audio, SAMPLE_RATE, subtype="PCM_16")
            manifest.append(
                {
                    "name": clip,
                    "file": f"{clip}.wav",
                    "flow": flow,
                    "condition": condition,
                    "transcript": transcript,
                    "selected_table_id": table,
                    "seconds": round(len(audio) / SAMPLE_RATE, 2),
                    "expected_any": expected,
                }
            )
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    clips = generate()
    total = sum(c["seconds"] for c in clips)
    print(f"Generated {len(clips)} clips ({total:.1f}s audio) into {OUT_DIR}")
