"""FrameSource: webcam index | RTSP/HTTP URL | video file | image directory."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


class FrameSource:
    """Yields (timestamp, BGR frame). `read()` returns None when no frame is available."""

    def __init__(
        self,
        source: int | str,
        resolution: tuple[int, int] | None = None,
        fps_target: int = 15,
        loop: bool = False,
    ) -> None:
        self.source = source
        self.resolution = resolution
        self.fps_target = fps_target
        self.loop = loop
        self._cap: cv2.VideoCapture | None = None
        self._images: list[Path] | None = None
        self._img_idx = 0
        self._is_file = False
        self.open()

    def open(self) -> None:
        src = self.source
        if isinstance(src, str) and src.isdigit():
            src = int(src)
        if isinstance(src, str) and Path(src).is_dir():
            self._images = sorted(
                p for p in Path(src).iterdir() if p.suffix.lower() in IMAGE_EXTS
            )
            return
        self._is_file = isinstance(src, str) and Path(src).is_file()
        self._cap = cv2.VideoCapture(src)
        if self.resolution and not self._is_file:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])

    def read(self) -> np.ndarray | None:
        if self._images is not None:
            if self._img_idx >= len(self._images):
                if not self.loop or not self._images:
                    return None
                self._img_idx = 0
            frame = cv2.imread(str(self._images[self._img_idx]))
            self._img_idx += 1
            return frame
        assert self._cap is not None
        ok, frame = self._cap.read()
        if not ok:
            if self._is_file and self.loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self._cap.read()
            if not ok:
                return None
        return frame

    @property
    def finite(self) -> bool:
        return self._images is not None or self._is_file

    def frames(
        self, realtime: bool = True
    ) -> Iterator[tuple[float, np.ndarray | None]]:
        period = 1.0 / max(self.fps_target, 1)
        while True:
            t0 = time.time()
            frame = self.read()
            if frame is None and self.finite and not self.loop:
                return
            yield t0, frame
            if realtime:
                dt = period - (time.time() - t0)
                if dt > 0:
                    time.sleep(dt)

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()


class ReconnectingSource:
    """Wraps a live source (webcam / stream) and reopens it after a dropout.

    Cameras need a moment after opening before the first frame arrives (macOS AVFoundation:
    ~1-2 s, plus ~1 s to start a capture process), so after each (re)open we keep reading for `grace_s` before trying again, and
    back off 1, 2, 4 ... `max_backoff_s` seconds between failed attempts. Any frame resets it.
    """

    def __init__(
        self,
        factory,
        clock=time.monotonic,
        grace_s: float = 5.0,
        max_backoff_s: float = 10.0,
    ) -> None:
        self.factory = factory
        self.clock = clock
        self.grace_s = grace_s
        self.max_backoff_s = max_backoff_s
        self.src = factory()
        self.opened_at = clock()
        self.last_frame_at: float | None = None
        self.backoff = 0.0
        self.reopens = 0
        self.camera_identity: str | None = None
        self.identity_changed = False

    @property
    def finite(self) -> bool:
        return getattr(self.src, "finite", False)

    @property
    def loop(self) -> bool:
        return getattr(self.src, "loop", False)

    def read(self):
        frame = self.src.read()
        now = self.clock()
        if frame is not None:
            identity = getattr(self.src, "camera_identity", None)
            if self.camera_identity is None:
                self.camera_identity = identity
            if self.identity_changed or identity != self.camera_identity:
                # A same-model replacement is not the calibrated camera. Staff
                # must restart/recalibrate explicitly; never silently rebind.
                self.identity_changed = True
                return None
            self.last_frame_at = now
            self.backoff = 0.0
            return frame
        # reopen only after no frames for the whole grace period (a single dropped frame is normal)
        quiet_since = max(self.opened_at, self.last_frame_at or 0.0)
        if now - quiet_since >= self.grace_s + self.backoff:
            try:
                self.src.release()
            except (OSError, cv2.error):
                logging.getLogger(__name__).warning(
                    "Capture release failed during reconnect"
                )
            self.src = self.factory()
            self.opened_at = self.clock()
            self.reopens += 1
            self.backoff = min(max(1.0, self.backoff * 2), self.max_backoff_s)
        return None

    @property
    def captured_at(self):
        return getattr(self.src, "captured_at", None)

    @property
    def captured_monotonic(self):
        return getattr(self.src, "captured_monotonic", None)

    def release(self) -> None:
        self.src.release()


def resolve_camera(name: str) -> tuple[int, str] | None:
    """Unambiguous AVFoundation identity and its original OpenCV list index.

    OpenCV sorts video + muxed devices without deduplicating. Preserve those
    indices, but count unique identities for ambiguity (one device may appear
    in both lists). Empty/missing/multiple substring matches never pick a camera.
    """
    if not name.strip():
        return None
    try:
        import AVFoundation as AVF
    except ImportError:
        return None
    devs = list(AVF.AVCaptureDevice.devicesWithMediaType_(AVF.AVMediaTypeVideo)) + list(
        AVF.AVCaptureDevice.devicesWithMediaType_(AVF.AVMediaTypeMuxed)
    )
    devs.sort(key=lambda d: str(d.uniqueID()))
    matches = {}
    for i, device in enumerate(devs):
        if name.lower() in str(device.localizedName()).lower():
            matches.setdefault(str(device.uniqueID()), i)
    if len(matches) != 1:
        return None
    identity, index = next(iter(matches.items()))
    return index, identity


def resolve_camera_index(name: str) -> int | None:
    """Unique named-camera index, or None; never a first-match fallback."""
    match = resolve_camera(name)
    return None if match is None else match[0]


def list_cameras() -> list[str]:
    try:
        import AVFoundation as AVF
    except ImportError:
        return []
    devs = list(AVF.AVCaptureDevice.devicesWithMediaType_(AVF.AVMediaTypeVideo)) + list(
        AVF.AVCaptureDevice.devicesWithMediaType_(AVF.AVMediaTypeMuxed)
    )
    devs.sort(key=lambda d: str(d.uniqueID()))
    return [str(d.localizedName()) for d in devs]


def _capture_child(
    source, resolution, fps_target, conn, quality: int = 90, name: str | None = None
) -> None:
    """Runs in a child process: open the camera, stream JPEG frames to the parent.
    Exits when the parent goes away or the camera stops delivering for a while."""
    import cv2 as _cv2  # fresh import in the child

    identity = None
    if name is not None:
        match = resolve_camera(name)
        if match is None:
            # camera not connected (yet), e.g. mid re-plug: never fall back to another camera
            print(
                f"[capture] camera {name!r} not found among {list_cameras()}; will retry",
                flush=True,
            )
            time.sleep(1.0)
            return
        source, identity = match
    # Named indices model AVFoundation specifically, not an arbitrary backend.
    cap = (
        _cv2.VideoCapture(source, _cv2.CAP_AVFOUNDATION)
        if name is not None
        else _cv2.VideoCapture(source)
    )
    if resolution:
        cap.set(_cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
        cap.set(_cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    period = 1.0 / max(fps_target, 1)
    last_ok = time.time()
    sequence = 0
    try:
        while True:
            t0 = time.time()
            captured_mono = time.monotonic()
            ok, frame = cap.read()
            if ok:
                last_ok = t0
                if resolution and (frame.shape[1], frame.shape[0]) != tuple(resolution):
                    frame = _cv2.resize(
                        frame, tuple(resolution), interpolation=_cv2.INTER_AREA
                    )
                good, buf = _cv2.imencode(
                    ".jpg", frame, [_cv2.IMWRITE_JPEG_QUALITY, quality]
                )
                if good:
                    sequence += 1
                    # Capture-side clocks survive buffering/process stalls. The
                    # parent never relabels an old JPEG as a newly seen frame.
                    conn.send((sequence, t0, captured_mono, identity, buf.tobytes()))
            elif t0 - last_ok > 5.0:
                return  # dead device; the parent will respawn us
            dt = period - (time.time() - t0)
            if dt > 0:
                time.sleep(dt)
    except (BrokenPipeError, EOFError, OSError):
        return
    finally:
        cap.release()


class ProcessFrameSource:
    """A webcam read in a child process.

    On macOS a long-running process never sees a camera that was unplugged and plugged back
    in (the device list is only refreshed through notifications delivered to a Cocoa run
    loop, which this server doesn't run). A fresh child process sees the current devices, so
    reconnecting = kill the child and start a new one (see ReconnectingSource)."""

    finite = False
    loop = False

    def __init__(
        self,
        source: int | str,
        resolution: tuple[int, int] | None = None,
        fps_target: int = 15,
        name: str | None = None,
    ) -> None:
        import multiprocessing as mp

        self.captured_at = None
        self.captured_monotonic = None
        self.camera_identity = None
        self._last_sequence = 0
        self._last_capture = None
        ctx = mp.get_context("spawn")
        self._parent, child = ctx.Pipe(duplex=False)
        self._proc = ctx.Process(
            target=_capture_child,
            args=(source, resolution, fps_target, child, 90, name),
            daemon=True,
        )
        self._proc.start()
        child.close()

    def read(self) -> np.ndarray | None:
        data = None
        try:
            while self._parent.poll():  # drain to the newest frame
                data = self._parent.recv()
        except (EOFError, OSError):
            return None
        if data is None:
            return None
        sequence, captured_at, captured_mono, identity, jpeg = data
        age = time.monotonic() - captured_mono
        if (
            sequence <= self._last_sequence
            or not math.isfinite(captured_at)
            or not math.isfinite(captured_mono)
            or not -0.01 <= age <= 0.35
            or (self._last_capture is not None and captured_mono <= self._last_capture)
        ):
            return None
        frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return None
        self._last_sequence, self._last_capture = sequence, captured_mono
        self.captured_at, self.captured_monotonic = captured_at, captured_mono
        self.camera_identity = identity
        return frame

    def release(self) -> None:
        try:
            self._parent.close()
        except OSError:
            pass
        if self._proc.is_alive():
            self._proc.terminate()
        self._proc.join(timeout=2)
