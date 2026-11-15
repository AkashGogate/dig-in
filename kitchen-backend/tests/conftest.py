import itertools
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kbackend.config import RecipeLine, Settings, ZoneSeed
from kbackend.db import connect
from kbackend.service import Kitchen, iso

SCHEMA = str(Path(__file__).resolve().parents[2] / "schema" / "events.schema.json")


class Clock:
    def __init__(self) -> None:
        self.t = datetime(2026, 11, 14, 20, 0, tzinfo=timezone.utc).timestamp()

    def __call__(self) -> float:
        return self.t

    def tick(self, s: float = 1.0) -> None:
        self.t += s


@pytest.fixture
def clock():
    return Clock()


def make_settings(**kw) -> Settings:
    base = dict(
        db_path=":memory:", schema_path=SCHEMA, push_context=False, bays=["A", "B", "C"],
        zones={"Z1": ZoneSeed(ingredient="tomato", on_hand=8), "Z2": ZoneSeed(ingredient="cheese", on_hand=6)},
        recipes={"burger": [RecipeLine(zone="Z1", qty=2), RecipeLine(zone="Z2", qty=1)],
                 "salad": [RecipeLine(zone="Z1", qty=2)]},
    )
    base.update(kw)
    return Settings(**base)


@pytest.fixture
def make_kitchen(clock):
    def _make(**kw) -> Kitchen:
        s = make_settings(**kw)
        return Kitchen(s, connect(":memory:"), clock=clock)
    return _make


@pytest.fixture
def k(make_kitchen):
    return make_kitchen()


class CV:
    """Builds contract-valid CV events with the test clock."""

    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.n = itertools.count()

    def _base(self, type_, source, camera, payload, zone=None, bay=None, ticket=None, method="none",
              ambiguous=False, status="observed", at=None):
        return {
            "event_id": str(uuid.uuid4()), "type": type_, "source": source, "camera_id": camera,
            "observed_at": at or iso(self.clock()), "zone_id": zone, "bay_id": bay, "confidence": 0.9,
            "status": status,
            "attribution": {"ticket_id": ticket, "method": method, "ambiguous": ambiguous},
            "payload": payload,
        }

    def heartbeat(self, camera="plating_cam", state="ok", reason=None):
        src = "cv.plating" if camera == "plating_cam" else "cv.ingredient"
        return self._base("CAMERA_STATUS", src, camera,
                          {"state": state, "reason": reason, "since": iso(self.clock()), "heartbeat": True})

    def arrived(self, bay, before, after, expected=None):
        matches = None if expected is None else after == expected
        return self._base("PLATE_ARRIVED", "cv.plating", "plating_cam",
                          {"count_before": before, "count_after": after, "delta": after - before,
                           "expected_plates": expected, "count_matches_expected": matches}, bay=bay)

    def removed(self, bay, before, after, task=None, server=None):
        return self._base("PLATE_REMOVED", "cv.plating", "plating_cam",
                          {"count_before": before, "count_after": after, "delta": before - after,
                           "bay_now_empty": after == 0, "claimed_task_id": task, "claimed_by": server,
                           "unclaimed": task is None}, bay=bay)

    def bay_state(self, bay, count, note=None, at=None):
        return self._base("BAY_STATE", "cv.plating", "plating_cam",
                          {"plate_count": count, "occupied": count > 0, "assigned_ticket_id": None,
                           "assigned_table": None, "assigned_course": None, "expected_plates": None,
                           "note": note}, bay=bay, at=at)

    def picked(self, zone, before, after, ticket=None, ambiguous=False, ingredient="tomato"):
        return self._base("INGREDIENT_PICKED", "cv.ingredient", "ingredient_cam",
                          {"ingredient": ingredient, "qty_delta": after - before, "count_before": before,
                           "count_after": after, "unit": "portion"}, zone=zone, ticket=ticket,
                          method="active_ticket_context" if ticket else "none", ambiguous=ambiguous)

    def returned(self, zone, before, after, ticket=None, ingredient="tomato"):
        return self._base("INGREDIENT_RETURNED", "cv.ingredient", "ingredient_cam",
                          {"ingredient": ingredient, "qty_delta": after - before, "count_before": before,
                           "count_after": after}, zone=zone, ticket=ticket,
                          method="active_ticket_context" if ticket else "none")

    def pending(self, zone, before, estimate, reason="unstable_count", ingredient="tomato"):
        return self._base("INGREDIENT_CHANGE_PENDING", "cv.ingredient", "ingredient_cam",
                          {"ingredient": ingredient, "reason": reason, "count_before": before,
                           "count_after_estimate": estimate}, zone=zone, status="pending_review")

    def snapshot(self, zone, count, ingredient="tomato"):
        return self._base("ZONE_SNAPSHOT", "cv.ingredient", "ingredient_cam",
                          {"ingredient": ingredient, "count": count}, zone=zone)


@pytest.fixture
def cv(clock):
    return CV(clock)


def trip(cv, zone, ticket=None, reason=None, ingredient="tomato", ambiguous=False):
    return cv._base("INGREDIENT_TRIP", "cv.ingredient", "ingredient_cam",
                    {"ingredient": ingredient, "duration_s": 0.8, "reason": reason}, zone=zone, ticket=ticket,
                    method="active_ticket_context" if ticket else "none", ambiguous=ambiguous,
                    status="pending_review" if reason else "observed")
