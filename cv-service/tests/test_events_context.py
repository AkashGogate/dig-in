import json
from pathlib import Path

import jsonschema
import pytest

from cvsvc.context import ActiveTicket, BayAssignment, Claim, ContextStore
from cvsvc.emitter import Emitter
from cvsvc.events import Attribution, EventAdapter, EventIds, utcnow_iso

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "schema" / "events.schema.json").read_text())


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def ctx(clock):
    return ContextStore(active_ticket_ttl_s=120, clock=clock)


@pytest.fixture
def em(ctx):
    return Emitter(EventIds("boot1"), ctx)


def all_events(em, ctx):
    ctx.set_bays({"A": BayAssignment(ticket_id="T-1", table="12", course="main", expected_plates=2), "B": None})
    ctx.set_claims({"A": Claim(task_id="RUN-1", server_id="s2")})
    return [
        em.picked("Z1", "tomato", 5, 3, 0.9, Attribution(ticket_id="T-1", method="active_ticket_context")),
        em.returned("Z1", "tomato", 3, 4, 0.9, Attribution()),
        em.pending("Z1", "tomato", "unstable_count", 4, 2, 0.4, Attribution()),
        em.zone_snapshot("Z1", "tomato", 4),
        em.plate_arrived("A", 0, 1, 0.9),
        em.plate_arrived("A", 1, 2, 0.9),
        em.plate_removed("A", 2, 0, 0.9),
        em.plate_removed("B", 1, 0, 0.9),
        em.bay_state("A", 2),
        em.camera_status("plating_cam", "obstructed", "dark", 1_000_000.0),
        em.camera_status("ingredient_cam", "ok", None, 1_000_000.0, heartbeat=True),
    ]


def test_every_event_type_matches_committed_schema(em, ctx):
    evs = all_events(em, ctx)
    assert len({e.type for e in evs}) == 8
    for e in evs:
        data = e.model_dump(mode="json")
        jsonschema.validate(data, SCHEMA)
        assert EventAdapter.validate_python(data).event_id == e.event_id


def test_schema_file_is_up_to_date(tmp_path):
    from cvsvc.events import write_schema
    out = tmp_path / "s.json"
    write_schema(out)
    assert json.loads(out.read_text()) == SCHEMA, "run `python -m cvsvc.events` to regenerate the schema"


def test_camera_never_emits_confirmed(em, ctx):
    for e in all_events(em, ctx):
        assert e.status in ("observed", "pending_review")
    bad = all_events(em, ctx)[0].model_dump(mode="json") | {"status": "confirmed"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, SCHEMA)


def test_plate_fields_from_context(em, ctx):
    evs = all_events(em, ctx)
    first, second, removed_claimed, removed_unclaimed = evs[4], evs[5], evs[6], evs[7]
    assert first.payload.count_matches_expected is False and first.payload.expected_plates == 2
    assert second.payload.count_matches_expected is True
    assert removed_claimed.payload.claimed_task_id == "RUN-1" and removed_claimed.payload.unclaimed is False
    assert removed_claimed.payload.bay_now_empty is True
    assert removed_unclaimed.payload.unclaimed is True and removed_unclaimed.payload.claimed_task_id is None
    p = em.plate_arrived("C", 0, 1, 0.9).payload  # unassigned bay
    assert p.expected_plates is None and p.count_matches_expected is None


def test_event_ids_deterministic_and_unique():
    a, b = EventIds("boot1"), EventIds("boot1")
    seq_a = [a.next("cam", "Z1", "change") for _ in range(3)]
    seq_b = [b.next("cam", "Z1", "change") for _ in range(3)]
    assert seq_a == seq_b and len(set(seq_a)) == 3
    assert EventIds("boot2").next("cam", "Z1", "change") != seq_a[0]


def test_attribution_rules(ctx, clock):
    assert ctx.attribution() == Attribution(ticket_id=None, method="none", ambiguous=False)
    ctx.set_active_ticket(ActiveTicket(ticket_id="T-42", set_by="cook_voice", set_at=utcnow_iso(clock.t)))
    v = ctx.active_version()
    assert ctx.attribution(v).ticket_id == "T-42"
    assert ctx.attribution(v).method == "active_ticket_context"
    # repeat push (reconnect) is not a change
    ctx.set_active_ticket(ActiveTicket(ticket_id="T-42", set_by="cook_voice", set_at=utcnow_iso(clock.t)))
    assert ctx.attribution(v).ticket_id == "T-42"
    # ticket changed mid-interaction -> ambiguous, no ticket
    ctx.set_active_ticket(ActiveTicket(ticket_id="T-43", set_at=utcnow_iso(clock.t)))
    amb = ctx.attribution(v)
    assert amb.ambiguous and amb.ticket_id is None
    # TTL expiry
    clock.t += 121
    assert ctx.attribution().ticket_id is None
    ctx.clear_active_ticket()
    assert ctx.attribution().ticket_id is None
