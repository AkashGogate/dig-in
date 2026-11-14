"""FrameSource: webcam index | RTSP/HTTP URL | video file | image directory."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


class FrameSource:
    """Yields (timestamp, BGR frame). `read()` returns None when no frame is available."""

    def __init__(self, source: int | str, resolution: tuple[int, int] | None = None,
                 fps_target: int = 15, loop: bool = False) -> None:
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
            self._images = sorted(p for p in Path(src).iterdir() if p.suffix.lower() in IMAGE_EXTS)
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

    def frames(self, realtime: bool = True) -> Iterator[tuple[float, np.ndarray | None]]:
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
