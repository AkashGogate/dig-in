"""Active ticket advances automatically when the active order is fully plated."""


def active(k):
    a = k.active_ticket()
    return a["ticket_id"] if a else None


def test_first_order_becomes_active_and_advances_on_plate(k, cv):
    t1 = k.create_ticket("4", dishes=["salad"])
    t2 = k.create_ticket("9", plates_expected=2)
    t3 = k.create_ticket("15")
    assert active(k) == t1["id"]
    k.ingest([cv.arrived("A", 0, 1, expected=1)])          # T1 plated in bay A
    assert active(k) == t2["id"]
    k.ingest([cv.arrived("B", 0, 1, expected=2)])          # T2 only partially plated
    assert active(k) == t2["id"]
    k.ingest([cv.arrived("B", 1, 2, expected=2)])          # T2 fully plated
    assert active(k) == t3["id"]
    k.ingest([cv.arrived("C", 0, 1, expected=1)])
    assert active(k) is None
    log = [e for e in k.event_log() if e["entity"] == "active_ticket"]
    assert all(e["source"] == "system" for e in log)


def test_manual_choice_is_not_overridden(k, cv):
    t1 = k.create_ticket("4")
    t2 = k.create_ticket("9")
    k.set_active_ticket(t2["id"], "cook_voice")
    k.ingest([cv.arrived("A", 0, 1, expected=1)])          # T1 plated, but T2 is the active one
    assert active(k) == t2["id"]


def test_new_order_fills_empty_slot_and_cancel_advances(k):
    t1 = k.create_ticket("4")
    k.clear_active_ticket()
    t2 = k.create_ticket("9")
    assert active(k) == t1["id"]  # oldest unplated order
    k.cancel_ticket(t1["id"])
    assert active(k) == t2["id"]


def test_declare_ready_advances(k):
    t1 = k.create_ticket("4")
    t2 = k.create_ticket("9")
    k.declare_ready(t1["id"])
    assert active(k) == t2["id"]


def test_disabled(make_kitchen, cv):
    k = make_kitchen(auto_advance_active_ticket=False)
    k.create_ticket("4")
    assert active(k) is None
