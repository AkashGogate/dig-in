"""Entrypoint: `python -m cvsvc.main [--mock] [--config config/cv.yaml]`."""
from __future__ import annotations

import argparse
import logging
import os

import uvicorn

from cvsvc.api import Runtime, StateView, create_app
from cvsvc.config import CVConfig, load_config
from cvsvc.context import ContextStore
from cvsvc.emitter import Emitter
from cvsvc.events import EventBus, EventIds
from cvsvc.sinks import HttpPostSink, JsonlSink, StdoutSink, WebSocketSink


def build_runtime(cfg: CVConfig, mock: bool, backend_url: str | None = None, stdout: bool = False,
                  mock_auto: bool = True, seed: int | None = None) -> Runtime:
    bus = EventBus(EventIds())
    context = ContextStore(active_ticket_ttl_s=cfg.ingredient.active_ticket_ttl_s)
    ws_sink = WebSocketSink()
    state = StateView()
    bus.listeners.append(state)
    bus.add_sink(JsonlSink(cfg.events_log_path))
    bus.add_sink(ws_sink)
    if stdout or cfg.sinks.stdout:
        bus.add_sink(StdoutSink())
    url = backend_url or os.environ.get("BACKEND_URL") or cfg.sinks.backend_url
    if url:
        bus.add_sink(HttpPostSink(url, cfg.sinks.outbox_path))

    emitter = Emitter(bus.ids, context, cfg.ingredient.camera, cfg.plating.camera)
    rt = Runtime(cfg=cfg, bus=bus, context=context, ws_sink=ws_sink, state=state,
                 mode="mock" if mock else "camera")

    if mock:
        from cvsvc.mock import MockKitchen

        kitchen = MockKitchen(cfg, bus, context, emitter, seed=seed,
                              auto_plating=mock_auto, auto_ingredients=mock_auto)
        rt.mock = kitchen
        rt.resolve_zone = kitchen.resolve_zone
        rt.background.append(kitchen.run)
    else:
        from cvsvc.pipeline import CameraPipelines

        pipes = CameraPipelines(cfg, bus, context, emitter)
        rt.resolve_zone = pipes.resolve_zone
        rt.capture_reference = pipes.capture_reference
        rt.mjpeg = pipes.mjpeg
        rt.health = pipes.health
        rt.background.append(pipes.run)
    return rt


def main() -> None:
    ap = argparse.ArgumentParser(description="dig-in CV service")
    ap.add_argument("--config", default="config/cv.yaml")
    ap.add_argument("--mock", action="store_true", help="emit simulated events; no cameras needed")
    ap.add_argument("--mock-manual", action="store_true",
                    help="with --mock: no automatic plates/picks; drive it via /mock/* endpoints")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--backend-url", default=None, help="POST events here (overrides config / BACKEND_URL)")
    ap.add_argument("--stdout", action="store_true", help="also print events to stdout")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--list-cameras", action="store_true", help="print connected cameras (OpenCV index order) and exit")
    args = ap.parse_args()
    if args.list_cameras:
        from cvsvc.sources import list_cameras
        for i, n in enumerate(list_cameras()):
            print(i, n)
        return

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config(args.config) if os.path.exists(args.config) else CVConfig()
    rt = build_runtime(cfg, mock=args.mock, backend_url=args.backend_url, stdout=args.stdout,
                       mock_auto=not args.mock_manual, seed=args.seed)
    uvicorn.run(create_app(rt), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
