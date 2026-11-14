"""Trip mode: CV reports reaches, backend subtracts the recipe qty per trip."""
from kbackend.config import RecipeLine
from tests.conftest import trip


def zone(k, zid):
    return [z for z in k.state()["zones"] if z["id"] == zid][0]


def test_attributed_trip_subtracts_recipe_qty_and_reservation(make_kitchen, cv):
    k = make_kitchen(recipes={"burger": [RecipeLine(zone="Z1", qty=1), RecipeLine(zone="Z2", qty=1)]})
    t = k.create_ticket("12", dishes=["burger"])
    assert zone(k, "Z1")["reserved"] == 1
    k.ingest([trip(cv, "Z1", ticket=t["id"])])
    z = zone(k, "Z1")
    assert z["on_hand"] == 7 and z["reserved"] == 0
    assert [r["kind"] for r in k.review_items()] == []


def test_trip_qty_comes_from_recipe(make_kitchen, cv):
    k = make_kitchen(recipes={"salad": [RecipeLine(zone="Z1", qty=3)]})
    t = k.create_ticket("12", dishes=["salad"])
    k.ingest([trip(cv, "Z1", ticket=t["id"])])
    assert zone(k, "Z1")["on_hand"] == 5


def test_unattributed_trip_uses_default_and_flags(k, cv):
    k.ingest([trip(cv, "Z2")])
    assert zone(k, "Z2")["on_hand"] == 5
    assert [r["kind"] for r in k.review_items()] == ["unassigned_movement"]


def test_pending_trip_changes_nothing_until_accepted(k, cv):
    t = k.create_ticket("12", dishes=["salad"])
    k.ingest([trip(cv, "Z1", ticket=t["id"], reason="multi_zone"), trip(cv, "Z2", reason="long_occlusion")])
    assert zone(k, "Z1")["on_hand"] == 8 and zone(k, "Z2")["on_hand"] == 6
    a, b = k.review_items()
    assert a["kind"] == "ingredient_trip_pending" and "several zones" in a["reason"]
    k.resolve_review(a["id"], "accept", staff_id="mgr")
    k.resolve_review(b["id"], "reject", staff_id="mgr")
    assert zone(k, "Z1")["on_hand"] == 6  # salad recipe in conftest takes 2 from Z1
    assert zone(k, "Z2")["on_hand"] == 6


def test_zone_running_out_raises_review(make_kitchen, cv):
    from kbackend.config import ZoneSeed
    k = make_kitchen(zones={"Z1": ZoneSeed(ingredient="lettuce", on_hand=1)})
    k.ingest([trip(cv, "Z1"), trip(cv, "Z1")])
    assert zone(k, "Z1")["on_hand"] == -1
    assert [r["kind"] for r in k.review_items()].count("zone_empty") == 1
