"""BACKEND_SPEC acceptance criteria 7-10 and B3/B4 rules."""


def zone(k, zid):
    return [z for z in k.state()["zones"] if z["id"] == zid][0]


def kinds(k):
    return [r["kind"] for r in k.review_items()]


# ---- B3 ----

def test_attributed_pick_no_double_count(k, cv):  # AC7
    t = k.create_ticket("12", dishes=["salad"])
    assert zone(k, "Z1")["reserved"] == 2 and zone(k, "Z1")["available"] == 6
    k.ingest([cv.picked("Z1", 8, 6, ticket=t["id"])])
    z = zone(k, "Z1")
    assert z["on_hand"] == 6 and z["reserved"] == 0 and z["available"] == 6
    mv = k.db.execute("SELECT * FROM inventory_movements").fetchall()
    assert len(mv) == 1 and mv[0]["qty_delta"] == -2 and mv[0]["ticket_id"] == t["id"]
    assert k.ticket(t["id"])["status"] == "submitted"  # a pick is not cooking progress


def test_unattributed_and_ambiguous_picks(k, cv):
    t = k.create_ticket("12", dishes=["salad"])
    k.ingest([cv.picked("Z1", 8, 7), cv.picked("Z1", 7, 6, ticket=t["id"], ambiguous=True)])
    z = zone(k, "Z1")
    assert z["on_hand"] == 6 and z["reserved"] == 2
    items = [r for r in k.review_items() if r["kind"] == "unassigned_movement"]
    assert len(items) == 2
    k.resolve_review(items[0]["id"], "accept", ticket_id=t["id"])
    assert zone(k, "Z1")["reserved"] == 1


def test_return_reopens_reservation(k, cv):
    t = k.create_ticket("12", dishes=["salad"])
    k.ingest([cv.picked("Z1", 8, 6, ticket=t["id"]), cv.returned("Z1", 6, 7, ticket=t["id"])])
    z = zone(k, "Z1")
    assert z["on_hand"] == 7 and z["reserved"] == 1


def test_pending_change_no_inventory_change_until_resolved(k, cv):  # AC8
    k.ingest([cv.pending("Z1", 8, 6)])
    assert zone(k, "Z1")["on_hand"] == 8
    item = [r for r in k.review_items() if r["kind"] == "ingredient_change_pending"][0]
    k.resolve_review(item["id"], "correct", count=5, staff_id="mgr")
    assert zone(k, "Z1")["on_hand"] == 5
    assert k.cv_calls == [{"zone_id": "Z1", "count": 5}]
    mv = k.db.execute("SELECT kind, source, qty_delta FROM inventory_movements").fetchall()
    assert [tuple(m) for m in mv] == [("correction", "staff", -3)]


def test_pending_accept_and_reject(k, cv):
    k.ingest([cv.pending("Z1", 8, 6), cv.pending("Z2", 6, 4, ingredient="cheese")])
    a, b = [r for r in k.review_items() if r["kind"] == "ingredient_change_pending"]
    k.resolve_review(a["id"], "accept")
    k.resolve_review(b["id"], "reject")
    assert zone(k, "Z1")["on_hand"] == 6 and zone(k, "Z2")["on_hand"] == 6
    assert {c["zone_id"]: c["count"] for c in k.cv_calls} == {"Z1": 6, "Z2": 6}


def test_snapshot_mismatch_is_review_never_overwrite(k, cv):
    k.ingest([cv.snapshot("Z1", 5)])
    assert zone(k, "Z1")["on_hand"] == 8 and zone(k, "Z1")["last_observed_count"] == 5
    k.ingest([cv.snapshot("Z1", 4)])
    items = [r for r in k.review_items() if r["kind"] == "zone_mismatch"]
    assert len(items) == 1 and "reads 4, recorded 8" in items[0]["reason"]  # deduped, updated
    k.correct("Z1", 4, "mgr")
    assert zone(k, "Z1")["on_hand"] == 4 and "zone_mismatch" not in kinds(k)


def test_restock_resolves_cv_baseline(k):
    k.restock("Z1", 4)
    assert zone(k, "Z1")["on_hand"] == 12
    assert k.cv_calls == [{"zone_id": "Z1", "count": 12}]
    k.waste("Z1", 1)
    assert k.cv_calls == [{"zone_id": "Z1", "count": 11}]


# ---- B4 ----

def test_obstruction_freezes_automation_manual_still_works(k, cv):  # AC9
    t = k.create_ticket("12")
    k.ingest([cv.heartbeat("plating_cam", "obstructed", "lens_covered")])
    assert k.state()["cameras"][0]["state"] == "obstructed"
    k.ingest([cv.arrived("A", 0, 1, expected=1)])  # should not arrive; stored, not acted on
    assert k.ticket(t["id"])["status"] == "submitted"
    obs = [o for o in k.observations() if o["type"] == "PLATE_ARRIVED"][0]
    assert obs["acted"] == 0 and obs["note"] == "camera obstructed"
    k.declare_ready(t["id"])
    k.confirm_served(t["id"])
    assert k.ticket(t["id"])["status"] == "served"


def test_recovery_recount_raises_review(k, cv):
    t = k.create_ticket("12")
    k.ingest([cv.heartbeat("plating_cam"), cv.arrived("A", 0, 1, expected=1)])
    k.ingest([cv.heartbeat("plating_cam", "obstructed", "lens_covered")])
    k.ingest([cv.heartbeat("plating_cam", "ok")])
    k.ingest([cv.bay_state("A", 0, note="post_obstruction_recount")])
    assert k.ticket(t["id"])["status"] == "ready"  # not auto-served
    assert "bay_recount" in kinds(k)


def test_stale_after_heartbeat_gap(k, cv, clock):  # AC10
    k.ingest([cv.heartbeat("plating_cam"), cv.heartbeat("ingredient_cam"), cv.bay_state("A", 0),
              cv.snapshot("Z1", 8)])
    s = k.state()
    assert not s["bays"][0]["plate_count_stale"] and not zone(k, "Z1")["observed_count_stale"]
    clock.tick(11)
    assert sorted(k.check_stale()) == ["ingredient_cam", "plating_cam"]
    assert k.check_stale() == []  # already lost
    s = k.state()
    assert s["bays"][0]["plate_count_stale"] and zone(k, "Z1")["observed_count_stale"]
    assert {c["state"] for c in s["cameras"]} == {"lost"}
    # heartbeat brings it back
    k.ingest([cv.heartbeat("plating_cam")])
    assert not k.state()["bays"][0]["plate_count_stale"]


def test_never_seen_camera_is_stale(k):
    assert k.state()["bays"][0]["plate_count_stale"]
