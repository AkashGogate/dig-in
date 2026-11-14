"""Deterministic small restaurant; no hidden ready orders or camera successes."""

from app.coordination.contracts import Actor, Bay, MenuItem, State, Table, Zone


def seed() -> State:
    return State(
        actors={
            a.id: a
            for a in [
                Actor(
                    id="server-1", name="Server One", role="server", section="window"
                ),
                Actor(id="server-2", name="Server Two", role="server", section="patio"),
                Actor(id="cook-1", name="Cook", role="cook", section="kitchen"),
                Actor(id="lead-1", name="Shift Lead", role="lead", section="all"),
            ]
        },
        tables={
            str(n): Table(
                id=str(n), section="window" if n < 3 else "patio", seats=[1, 2, 3, 4]
            )
            for n in range(1, 4)
        },
        menu={
            m.id: m
            for m in [
                MenuItem(
                    id="salmon",
                    name="Salmon & greens",
                    price_cents=2400,
                    modifiers=["no butter", "sauce on side"],
                    recipe={"salmon": 1, "greens": 1},
                ),
                MenuItem(
                    id="risotto",
                    name="Garden risotto",
                    price_cents=1800,
                    modifiers=["no cheese", "sauce on side"],
                    recipe={"rice": 1, "greens": 1},
                ),
            ]
        },
        bays={k: Bay(id=k) for k in "ABC"},
        zones={
            k: Zone(id=k, ingredient=k, initial=n)
            for k, n in [("salmon", 12), ("greens", 20), ("rice", 15)]
        },
        adapter_status={
            "speech": "mock transcript input; live Deepgram remains in legacy harness",
            "voice_response": "disabled; ElevenLabs candidate",
            "positioning": "mock suggestion only; manual always available",
            "ingredient_camera": "mock fixed-zone observations; no raw recording",
            "plating_camera": "mock bay observations; no content verification",
            "uno_q": "unverified hardware lane; disconnected",
            "analytics": "disabled optional Databricks lane",
            "payments": "not implemented",
        },
    )
