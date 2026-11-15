"""Render a scripted utterance as a persona would say it (macOS `say` + numpy).

Free and local; only the deepgram runner calls it. Output is cached under
audio-samples/dig-in/generated/ (gitignored) keyed by persona + text, so the
same cases are re-used across runs and personas differ only in audio.
Synthetic TTS is not a real kitchen.
"""

from __future__ import annotations

import functools
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

GENERATED = (
    Path(__file__).resolve().parents[3] / "audio-samples" / "dig-in" / "generated"
)
BASE_RATE = 16000


def _validate_samples(samples: np.ndarray) -> None:
    if samples.ndim != 1 or not samples.size or not np.isfinite(samples).all():
        raise ValueError(
            "Synthetic audio is empty, nonfinite or not mono; no provider request was made. "
            "Check local speech synthesis permissions and regenerate the clip."
        )


@functools.cache
def _installed_voices() -> frozenset[str]:
    out = subprocess.run(
        ["say", "-v", "?"], capture_output=True, text=True, check=True
    ).stdout
    return frozenset(line.split()[0] for line in out.splitlines() if line.strip())


def _say(text: str, voice: str, rate_wpm: int) -> np.ndarray:
    if voice not in _installed_voices():
        voice = "Samantha"
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "say.wav"
        subprocess.run(
            [
                "say",
                "-v",
                voice,
                "-r",
                str(rate_wpm),
                "-o",
                str(wav),
                "--file-format=WAVE",
                f"--data-format=LEI16@{BASE_RATE}",
                text,
            ],
            check=True,
            capture_output=True,
        )
        audio, rate = sf.read(wav, dtype="float32")
    _validate_samples(audio)
    if rate != BASE_RATE:
        raise ValueError("Synthetic speech has an unexpected sample rate")
    return audio


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x**2)) + 1e-9)


def _kitchen_noise(length: int, seed: int) -> np.ndarray:
    """Fan-like rumble (smoothed noise) plus short pan-clatter bursts."""
    rng = np.random.default_rng(seed)
    noise = np.convolve(rng.normal(0, 1, length), np.ones(40) / 40, mode="same")
    for start in rng.integers(0, max(1, length - 800), size=4):
        noise[start : start + 800] += rng.normal(0, 3, 800) * np.exp(
            -np.linspace(0, 6, 800)
        )
    return noise.astype("float32")


def _band_limit_8k(audio: np.ndarray) -> np.ndarray:
    """Windowed-sinc low-pass at ~3.4 kHz, then decimate 16 kHz -> 8 kHz."""
    taps = np.arange(-32, 33)
    kernel = np.sinc(2 * 3400 / BASE_RATE * taps) * np.hamming(len(taps))
    return np.convolve(audio, kernel / kernel.sum(), mode="same")[::2].astype("float32")


def render(persona: dict, text: str, seed: int = 0) -> tuple[np.ndarray, int]:
    speech = _say(text, persona["say_voice"], persona["rate_wpm"])
    _validate_samples(speech)
    if persona["background"] == "kitchen_noise":
        noise = _kitchen_noise(len(speech), seed)
        noise *= _rms(speech) / _rms(noise) / 10 ** (persona["snr_db"] / 20)
        speech = speech + noise
    overlap = persona.get("overlap")
    if overlap:
        other = (
            _say(overlap["phrase"], overlap["say_voice"], persona["rate_wpm"])
            * overlap["gain"]
        )
        start = int(len(speech) * overlap["offset_fraction"])
        mixed = np.zeros(max(len(speech), start + len(other)), dtype="float32")
        mixed[: len(speech)] += speech
        mixed[start : start + len(other)] += other
        speech = mixed
    speech = np.clip(speech, -1.0, 1.0).astype("float32")
    _validate_samples(speech)
    if persona["sample_rate"] == 8000:
        return _band_limit_8k(speech), 8000
    return speech, BASE_RATE


def clip_path(case_id: str, persona: dict, text: str, root: Path = GENERATED) -> Path:
    key = hashlib.sha256(
        json.dumps([persona, text], sort_keys=True).encode()
    ).hexdigest()[:10]
    return root / persona["id"] / f"{case_id}-{key}.wav"


def ensure_clip(
    case_id: str, persona: dict, text: str, seed: int = 0
) -> tuple[Path, float]:
    path = clip_path(case_id, persona, text)
    if not path.exists():
        audio, rate = render(persona, text, seed)
        _validate_samples(audio)
        if rate not in (8000, BASE_RATE):
            raise ValueError("Synthetic audio has an unsupported sample rate")
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, audio, rate, subtype="PCM_16")
    info = sf.info(path)
    if (
        info.frames <= 0
        or info.channels != 1
        or info.samplerate not in (8000, BASE_RATE)
    ):
        raise ValueError(
            f"Invalid cached synthetic clip: {path}. Remove it and regenerate; no audio was sent."
        )
    samples, _ = sf.read(path, dtype="float32")
    _validate_samples(samples)
    return path, info.frames / info.samplerate
