"""Builds well-formed events (ids, timestamps, context-derived fields).

Shared by the real trackers and --mock mode so both emit identical shapes.
"""
from __future__ import annotations

import time

from cvsvc.context import ContextStore
from cvsvc.events import (
    Attribution,
    BayState,
    BayStatePayload,
    CameraStatus,
    CameraStatusPayload,
    EventIds,
    IngredientChangePending,
    IngredientChangePendingPayload,
    IngredientPicked,
    IngredientPickedPayload,
    IngredientReturned,
    IngredientReturnedPayload,
    IngredientTrip,
    IngredientTripPayload,
    PlateArrived,
    PlateArrivedPayload,
    PlateRemoved,
    PlateRemovedPayload,
    ZoneSnapshot,
    ZoneSnapshotPayload,
    utcnow_iso,
)


class Emitter:
    def __init__(self, ids: EventIds, context: ContextStore,
                 ingredient_camera: str = "ingredient_cam", plating_camera: str = "plating_cam") -> None:
        self.ids = ids
        self.context = context
        self.ingredient_camera = ingredient_camera
        self.plating_camera = plating_camera

    @staticmethod
    def _ts(ts: float | None) -> str:
        return utcnow_iso(ts if ts is not None else time.time())

    # ---- ingredient ----
    def picked(self, zone_id: str, ingredient: str, before: int, after: int, confidence: float,
               attribution: Attribution, ts: float | None = None) -> IngredientPicked:
        return IngredientPicked(
            event_id=self.ids.next(self.ingredient_camera, zone_id, "change"),
            source="cv.ingredient", camera_id=self.ingredient_camera, observed_at=self._ts(ts),
            zone_id=zone_id, confidence=round(confidence, 3), attribution=attribution,
            payload=IngredientPickedPayload(ingredient=ingredient, qty_delta=after - before,
                                            count_before=before, count_after=after),
        )

    def returned(self, zone_id: str, ingredient: str, before: int, after: int, confidence: float,
                 attribution: Attribution, ts: float | None = None) -> IngredientReturned:
        return IngredientReturned(
            event_id=self.ids.next(self.ingredient_camera, zone_id, "change"),
            source="cv.ingredient", camera_id=self.ingredient_camera, observed_at=self._ts(ts),
            zone_id=zone_id, confidence=round(confidence, 3), attribution=attribution,
            payload=IngredientReturnedPayload(ingredient=ingredient, qty_delta=after - before,
                                              count_before=before, count_after=after),
        )

    def pending(self, zone_id: str, ingredient: str, reason: str, before: int, estimate: int | None,
                confidence: float, attribution: Attribution, ts: float | None = None) -> IngredientChangePending:
        return IngredientChangePending(
            event_id=self.ids.next(self.ingredient_camera, zone_id, "change"),
            source="cv.ingredient", camera_id=self.ingredient_camera, observed_at=self._ts(ts),
            zone_id=zone_id, confidence=round(confidence, 3), attribution=attribution,
            payload=IngredientChangePendingPayload(ingredient=ingredient, reason=reason,  # type: ignore[arg-type]
                                                   count_before=before, count_after_estimate=estimate),
        )

    def trip(self, zone_id: str, ingredient: str, duration_s: float, confidence: float,
             attribution: Attribution, reason: str | None = None, ts: float | None = None) -> IngredientTrip:
        return IngredientTrip(
            event_id=self.ids.next(self.ingredient_camera, zone_id, "trip"),
            source="cv.ingredient", camera_id=self.ingredient_camera, observed_at=self._ts(ts),
            zone_id=zone_id, confidence=round(confidence, 3), attribution=attribution,
            status="pending_review" if reason else "observed",
            payload=IngredientTripPayload(ingredient=ingredient, duration_s=round(duration_s, 2),
                                          reason=reason),  # type: ignore[arg-type]
        )

    def zone_snapshot(self, zone_id: str, ingredient: str, count: int, confidence: float = 1.0,
                      ts: float | None = None) -> ZoneSnapshot:
        return ZoneSnapshot(
            event_id=self.ids.next(self.ingredient_camera, zone_id, "snapshot"),
            source="cv.ingredient", camera_id=self.ingredient_camera, observed_at=self._ts(ts),
            zone_id=zone_id, confidence=round(confidence, 3),
            payload=ZoneSnapshotPayload(ingredient=ingredient, count=count),
        )

    # ---- plating ----
    def _bay_attr(self, bay_id: str) -> Attribution:
        a = self.context.bay(bay_id)
        if a is None:
            return Attribution()
        return Attribution(ticket_id=a.ticket_id, method="bay_assignment")

    def plate_arrived(self, bay_id: str, before: int, after: int, confidence: float,
                      ts: float | None = None) -> PlateArrived:
        a = self.context.bay(bay_id)
        expected = a.expected_plates if a else None
        matches = None if a is None or expected is None else after == expected
        return PlateArrived(
            event_id=self.ids.next(self.plating_camera, bay_id, "change"),
            source="cv.plating", camera_id=self.plating_camera, observed_at=self._ts(ts),
            bay_id=bay_id, confidence=round(confidence, 3), attribution=self._bay_attr(bay_id),
            payload=PlateArrivedPayload(count_before=before, count_after=after, delta=after - before,
                                        expected_plates=expected, count_matches_expected=matches),
        )

    def plate_removed(self, bay_id: str, before: int, after: int, confidence: float,
                      ts: float | None = None) -> PlateRemoved:
        c = self.context.claim(bay_id)
        return PlateRemoved(
            event_id=self.ids.next(self.plating_camera, bay_id, "change"),
            source="cv.plating", camera_id=self.plating_camera, observed_at=self._ts(ts),
            bay_id=bay_id, confidence=round(confidence, 3), attribution=self._bay_attr(bay_id),
            payload=PlateRemovedPayload(count_before=before, count_after=after, delta=before - after,
                                        bay_now_empty=after == 0,
                                        claimed_task_id=c.task_id if c else None,
                                        claimed_by=c.server_id if c else None,
                                        unclaimed=c is None),
        )

    def bay_state(self, bay_id: str, plate_count: int, confidence: float = 1.0, note: str | None = None,
                  ts: float | None = None) -> BayState:
        a = self.context.bay(bay_id)
        return BayState(
            event_id=self.ids.next(self.plating_camera, bay_id, "state"),
            source="cv.plating", camera_id=self.plating_camera, observed_at=self._ts(ts),
            bay_id=bay_id, confidence=round(confidence, 3), attribution=self._bay_attr(bay_id),
            payload=BayStatePayload(plate_count=plate_count, occupied=plate_count > 0,
                                    assigned_ticket_id=a.ticket_id if a else None,
                                    assigned_table=a.table if a else None,
                                    assigned_course=a.course if a else None,
                                    expected_plates=a.expected_plates if a else None,
                                    note=note),
        )

    # ---- health ----
    def camera_status(self, camera_id: str, state: str, reason: str | None, since: float,
                      heartbeat: bool = False, ts: float | None = None) -> CameraStatus:
        source = "cv.plating" if camera_id == self.plating_camera else "cv.ingredient"
        return CameraStatus(
            event_id=self.ids.next(camera_id, None, "heartbeat" if heartbeat else "status"),
            source=source, camera_id=camera_id, observed_at=self._ts(ts),  # type: ignore[arg-type]
            payload=CameraStatusPayload(state=state, reason=reason, since=utcnow_iso(since),  # type: ignore[arg-type]
                                        heartbeat=heartbeat),
        )
