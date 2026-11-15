"""BACKEND_SPEC acceptance criteria 1-6, 11 and B0/B2 rules."""
import pytest

from kbackend.service import Conflict, Invalid


def kinds(k):
    return [r["kind"] for r in k.review_items()]


# ---- B0: ingest ----

def test_duplicate_event_changes_nothing(k, cv):  # AC1
    t = k.create_ticket("12", "main")
    ev = cv.arrived("A", 0, 1, expected=1)
    r1 = k.ingest([ev])
    snap = k.state()
    r2 = k.ingest([ev])
    assert r1["accepted"] == [ev["event_id"]] and r2["duplicates"] == [ev["event_id"]]
    assert k.state()["tickets"] == snap["tickets"] and len(k.task_queue()) == 1
    assert k.ticket(t["id"])["status"] == "ready"


def test_malformed_event_rejected(k, cv):
    bad = cv.arrived("A", 0, 1) | {"status": "confirmed"}
    r = k.ingest([bad])
    assert r["rejected"] and not r["accepted"]
    assert k.observations() == []


def test_every_observation_stored(k, cv):
    k.ingest([cv.heartbeat(), cv.bay_state("A", 0), cv.snapshot("Z1", 8)])
    assert len(k.observations()) == 3


# ---- B2: bays ----

def test_submit_allocates_free_bay_and_bumps_context(k):  # AC2
    v = k.context_version
    t = k.create_ticket("12", "main", plates_expected=2)
    assert t["bay_id"] == "A"
    assert k.context_version > v
    assert k.bays_context()["bays"]["A"] == {"ticket_id": t["id"], "table": "12", "course": "main",
                                              "expected_plates": 2}


def test_queue_when_no_bay_free_then_auto_assign(k, cv):  # AC3
    ts = [k.create_ticket(str(i)) for i in range(4)]
    assert [t["bay_id"] for t in ts[:3]] == ["A", "B", "C"]
    assert k.ticket(ts[3]["id"])["bay_id"] is None
    assert k.state()["waiting_for_bay"] == [ts[3]["id"]]
    # serve ticket in bay B through the camera path
    k.ingest([cv.arrived("B", 0, 1, expected=1)])
    task = k.task_queue()[0]
    k.claim_task(task["id"], "s1")
    k.ingest([cv.removed("B", 1, 0, task=task["id"], server="s1")])
    assert k.ticket(ts[3]["id"])["bay_id"] == "B"
    assert k.state()["waiting_for_bay"] == []


def test_bay_with_plates_not_free(k, cv):  # AC4
    k.ingest([cv.bay_state("A", 1)])  # stray plate in A
    t = k.create_ticket("5")
    assert t["bay_id"] == "B"


def test_override_requires_confirm_and_is_logged(k, cv):  # AC4
    t = k.create_ticket("5")
    k.ingest([cv.arrived("A", 0, 1, expected=1)])
    with pytest.raises(Invalid):
        k.override_bay("A", "clear")
    k.override_bay("A", "clear", staff_id="mgr", confirm=True)
    assert k.ticket(t["id"])["bay_id"] is None
    log = [e for e in k.event_log() if e["entity"] == "bay" and e["action"] == "override:clear"]
    assert log and log[0]["source"] == "staff" and log[0]["data"]["plate_count"] == 1


# ---- B2: readiness ----

def test_single_plate_ready_creates_task(k, cv):  # AC5
    t = k.create_ticket("12")
    k.ingest([cv.arrived("A", 0, 1, expected=1)])
    assert k.ticket(t["id"])["status"] == "ready"
    q = k.task_queue()
    assert len(q) == 1 and q[0]["ticket_id"] == t["id"] and q[0]["bay_id"] == "A" and q[0]["status"] == "open"


def test_two_plate_ready_only_at_second(k, cv):  # AC5
    t = k.create_ticket("12", plates_expected=2)
    k.ingest([cv.arrived("A", 0, 1, expected=2)])
    tt = k.ticket(t["id"])
    assert tt["status"] == "submitted" and "partially plated (1 of 2)" in tt["badges"]
    assert k.task_queue() == []
    k.ingest([cv.arrived("A", 1, 2, expected=2)])
    tt = k.ticket(t["id"])
    assert tt["status"] == "ready" and not any(b.startswith("partially") for b in tt["badges"])


def test_confirm_mode_arrival_is_observation_only(make_kitchen, cv):
    k = make_kitchen(readiness_mode="confirm")
    t = k.create_ticket("12")
    k.ingest([cv.arrived("A", 0, 1, expected=1)])
    tt = k.ticket(t["id"])
    assert tt["status"] == "submitted" and "plated (observed)" in tt["badges"]
    k.declare_ready(t["id"])
    assert k.ticket(t["id"])["status"] == "ready" and k.ticket(t["id"])["status_source"] == "staff"


def test_plate_in_unassigned_bay_is_review(k, cv):
    k.ingest([cv.arrived("B", 0, 1)])
    assert kinds(k) == ["plate_unassigned_bay"]


def test_extra_plate_ready_plus_review(k, cv):
    t = k.create_ticket("12")
    k.ingest([cv.arrived("A", 0, 2, expected=1)])
    assert k.ticket(t["id"])["status"] == "ready"
    assert "extra_plate" in kinds(k)


# ---- B2: claims + removal ----

def test_claim_and_duplicate_claim(k, cv):
    k.create_ticket("12")
    k.ingest([cv.arrived("A", 0, 1, expected=1)])
    task = k.task_queue()[0]
    v = k.context_version
    k.claim_task(task["id"], "s1")
    assert k.context_version > v
    assert k.claims_context()["claims"]["A"] == {"task_id": task["id"], "server_id": "s1"}
    k.claim_task(task["id"], "s1")  # idempotent
    with pytest.raises(Conflict) as e:
        k.claim_task(task["id"], "s2")
    assert e.value.detail["claimed_by"] == "s1"
    k.release_task(task["id"])
    assert k.claims_context()["claims"]["A"] is None


def test_claimed_removal_serves_and_clears(k, cv):  # AC6
    t = k.create_ticket("12")
    k.ingest([cv.arrived("A", 0, 1, expected=1)])
    task = k.task_queue()[0]
    k.claim_task(task["id"], "s1")
    k.ingest([cv.removed("A", 1, 0, task=task["id"], server="s1")])
    tt = k.ticket(t["id"])
    assert tt["status"] == "served" and tt["served_source"] == "cv"
    assert k.task_queue() == []
    assert k.bays_context()["bays"]["A"] is None
    assert k.claims_context()["claims"]["A"] is None


def test_unclaimed_removal_badge_and_review(k, cv):  # AC6
    t = k.create_ticket("12")
    k.ingest([cv.arrived("A", 0, 1, expected=1)])
    k.ingest([cv.removed("A", 1, 0)])
    tt = k.ticket(t["id"])
    assert tt["status"] == "served" and "served, unclaimed pickup" in tt["badges"]
    assert "unclaimed_pickup" in kinds(k)
    assert k.bays_context()["bays"]["A"] is None


def test_unclaimed_removal_without_auto_serve(make_kitchen, cv):
    k = make_kitchen(auto_serve_on_removal=False)
    t = k.create_ticket("12")
    k.ingest([cv.arrived("A", 0, 1, expected=1)])
    k.ingest([cv.removed("A", 1, 0)])
    assert k.ticket(t["id"])["status"] == "ready"
    assert "unexplained_removal" in kinds(k)
    # bay held until resolved
    assert k.create_ticket("13")["bay_id"] == "B"
    item = [r for r in k.review_items() if r["kind"] == "unexplained_removal"][0]
    k.resolve_review(item["id"], "accept", staff_id="mgr")
    assert k.ticket(t["id"])["status"] == "served" and k.ticket(t["id"])["served_source"] == "staff"
    assert k.bays_context()["bays"]["A"] is None


def test_partial_pickup_no_state_change(k, cv):
    t = k.create_ticket("12", plates_expected=2)
    k.ingest([cv.arrived("A", 0, 1, expected=2), cv.arrived("A", 1, 2, expected=2)])
    k.ingest([cv.removed("A", 2, 1)])
    tt = k.ticket(t["id"])
    assert tt["status"] == "ready" and "partially picked up (1 left)" in tt["badges"]
    assert k.bays_context()["bays"]["A"]["ticket_id"] == t["id"]


def test_staff_served_overrides_cv_and_returns_are_review(k, cv):
    t = k.create_ticket("12")
    k.ingest([cv.arrived("A", 0, 1, expected=1), cv.removed("A", 1, 0)])
    assert k.ticket(t["id"])["served_source"] == "cv"
    k.confirm_served(t["id"], "s1")
    tt = k.ticket(t["id"])
    assert tt["served_source"] == "staff" and "served, unclaimed pickup" not in tt["badges"]
    # bay was cleared; a new ticket takes it; plates "returning" to a different bay for a served ticket
    # are only possible while still assigned, so test the assigned case:
    t2 = k.create_ticket("14")
    k.ingest([cv.arrived("A", 0, 1, expected=1)])
    k.confirm_served(t2["id"])  # staff served while plate still in bay: bay stays assigned
    assert k.bays_context()["bays"]["A"]["ticket_id"] == t2["id"]
    k.ingest([cv.removed("A", 1, 0)])
    k.ingest([cv.arrived("A", 0, 1)])  # bay now cleared -> unassigned
    assert k.bays_context()["bays"]["A"] is None


def test_plates_returned_after_served_not_reopened(k, cv):
    t = k.create_ticket("12")
    k.ingest([cv.arrived("A", 0, 1, expected=1)])
    k.confirm_served(t["id"])  # staff served, plate still in bay
    k.ingest([cv.removed("A", 1, 1 - 1)])  # empties -> clears bay
    assert k.ticket(t["id"])["status"] == "served"
    t3 = k.create_ticket("15")
    k.ingest([cv.arrived("A", 0, 1, expected=1)])
    k.confirm_served(t3["id"])
    k.ingest([cv.arrived("A", 1, 2)])  # plate added after staff-served, bay still assigned
    assert k.ticket(t3["id"])["status"] == "served"
    assert "plate_returned" in kinds(k)


def test_event_log_sources(k, cv):  # AC11
    t = k.create_ticket("12")
    k.ingest([cv.arrived("A", 0, 1, expected=1)])
    k.confirm_served(t["id"])
    log = k.event_log()
    assert all(e["source"] in ("cv", "staff", "system") and e["at"] for e in log)
    ready = [e for e in log if e["entity_id"] == t["id"] and e["action"] == "status:ready"][0]
    served = [e for e in log if e["entity_id"] == t["id"] and e["action"] == "status:served"][0]
    assert ready["source"] == "cv" and ready["observation_event_id"]
    assert served["source"] == "staff" and served["observation_event_id"] is None


def test_out_of_order_flush_skips_regressions(k, cv, clock):
    t = k.create_ticket("12")
    a = cv.arrived("A", 0, 1, expected=1)
    clock.tick(1)
    hb = cv.heartbeat()
    clock.tick(1)
    r = cv.removed("A", 1, 0)
    clock.tick(1)
    stale_state = cv.bay_state("A", 1, at=a["observed_at"])  # older than the removal
    k.ingest([r, stale_state, hb, a])  # shuffled outbox flush
    assert k.ticket(t["id"])["status"] == "served"
    assert k.state()["bays"][0]["last_plate_count"] == 0


def test_cancel_frees_bay_and_releases_reservations(k):
    t = k.create_ticket("12", dishes=["burger"])
    z1 = [z for z in k.state()["zones"] if z["id"] == "Z1"][0]
    assert z1["reserved"] == 2 and z1["available"] == 6
    w = [k.create_ticket(str(i)) for i in range(3)][-1]
    assert w["bay_id"] is None
    k.cancel_ticket(t["id"])
    z1 = [z for z in k.state()["zones"] if z["id"] == "Z1"][0]
    assert z1["reserved"] == 0 and z1["on_hand"] == 8
    assert k.ticket(w["id"])["bay_id"] == "A"


def test_allocate_on_cooking_complete(make_kitchen):
    k = make_kitchen(allocate_on="cooking_complete")
    t = k.create_ticket("12")
    assert t["bay_id"] is None and k.state()["waiting_for_bay"] == []
    assert k.cooking_complete(t["id"])["bay_id"] == "A"
