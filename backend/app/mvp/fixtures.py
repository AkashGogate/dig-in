"""Small reproducible MVP. Six physical zones, one dish unit per zone."""

from app.mvp.contracts import Actor, Camera, IngredientZone, PlatingZone, State, Table
from app.mvp.menu import MenuDocument, load_menu


def seed(menu: MenuDocument | None = None) -> State:
    menu = menu or load_menu()
    return State(
        actors={
            a.id: a
            for a in [
                Actor(id="server-1", name="Server One", role="server"),
                Actor(id="server-2", name="Server Two", role="server"),
                Actor(id="cook-1", name="Kitchen device", role="cook"),
                Actor(id="lead-1", name="Integration demo lead", role="lead"),
            ]
        },
        tables={str(n): Table(id=str(n)) for n in range(1, 4)},
        menu=menu,
        zones={
            name: PlatingZone(id=name, rectangle=(index * 160, 0, 150, 150))
            for index, name in enumerate("ABCDEF")
        },
        cameras={name: Camera(id=name) for name in ("plating-cam", "ingredient-cam")},
        ingredient_zones={
            zone_id: IngredientZone(id=zone_id, ingredient=ingredient, initial=20)
            for ingredient, zone_id in menu.ingredient_zones.items()
            if zone_id is not None
        },
    )
