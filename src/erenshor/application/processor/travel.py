"""Travel between zones: zone lines and the scene switches of spells.

``travel_routes`` records each way that a player can take between zones, once
for every consumer. Only zone lines that players can use become routes
(``zone_lines.is_usable``), and each keeps its own gates in ``gate_conditions``. A
spell route needs its spell, and the requirement graph reaches the spell
through the items that cast or teach it. A route that returns to a saved place,
such as a bind point or the stored exit of the Reliquary Hall, has no fixed
destination.

The scene switches of spells come from the ``travel.spell_scene_changes`` code
fact, which lists every ``ChangeScene`` call of ``SpellVessel.DoMiscSpells``
with the conditions it runs under. A condition that this module cannot read
fails the build, so a changed spell is reviewed before its route is used.

Being jailed by the GM is recorded as well, with mechanism ``jail``. Consumers
never route through it, because a punishment is no plan, as with the Auction
House. Each jailing fact must keep the conditions that its note describes.

``teleports`` keeps its published shape: one landing for each spell that sends
the player to a fixed place from any zone, with the item that casts it.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable

    from .writer import Writer

_FACT = "travel.spell_scene_changes"
_SPELL = re.compile(r'^spell\.SpellName == "(?P<name>.+)"$')
_SCENE = re.compile(r'^SceneManager\.GetActiveScene \(\)\.name == "(?P<scene>[^"]+)"$')
_NOT_SCENE = re.compile(r'^!\(SceneManager\.GetActiveScene \(\)\.name == "(?P<scene>[^"]+)"\)$')
# Arguments that name a place the player saved or stands at, not a fixed one.
_SAVED_DESTINATION = "expr:GameData.BindZone"
_SAVED_LANDINGS = frozenset({"expr:GameData.BindLoc", "expr:transform.position"})
_SAVED_SUN = "expr:GameData.SunInBindZone"
# Each scene switch of a jailing: its fact and index, and the destination,
# conditions, and note that the shipped code keeps.
_JAILS: dict[tuple[str, str], tuple[str, tuple[str, ...], tuple[str, ...], str]] = {
    # code-fact: travel.jail_obscenities
    ("travel.jail_obscenities", "0"): (
        "Detention",
        ("warnings > 3 && GameData.Jail",),
        (),
        "Jailed by the GM after a fourth warning for obscenities in chat",
    ),
    # code-fact: travel.jail_off_navmesh
    ("travel.jail_off_navmesh", "0"): (
        "Detention",
        (
            '!(SceneManager.GetActiveScene ().name == "Stowaway" || SceneManager.GetActiveScene ().name == "Tutorial")',
            "OffNavWarnings == 3",
        ),
        ("!GameData.Jail",),
        "Jailed by the GM after a fourth warning for leaving the NPC paths outside the tutorial island",
    ),
    # code-fact: travel.jail_blessing_altar
    ("travel.jail_blessing_altar", "0"): (
        "Detention",
        ("BlessingIcon.MyItem == GameData.Misc.TMOGHIDE",),
        (),
        "Jailed for offering Transmog - Hide Slot at a blessing altar",
    ),
}
# JailTimer, which the Detention scene places, releases the player from Prison.
# code-fact: travel.jail_release
_RELEASES: dict[tuple[str, str], tuple[str, tuple[str, ...], tuple[str, ...], str]] = {
    ("travel.jail_release", "0"): (
        "Azure",
        ("Timer <= 1f", "!GameData.GM.JailedFromTutorial"),
        (),
        "Released after three minutes in jail, when jailed away from the tutorial island",
    ),
    ("travel.jail_release", "1"): (
        "Stowaway",
        ("Timer <= 1f",),
        ("!GameData.GM.JailedFromTutorial",),
        "Released after three minutes in jail, when jailed on the tutorial island",
    ),
}


@dataclass(frozen=True)
class SpellChange:
    """One scene switch of a spell, as ``SpellVessel.DoMiscSpells`` runs it."""

    spell_name: str
    to_scene: str | None
    landing: tuple[float, float, float] | None
    use_sun: int | None
    from_scene: str | None
    except_scene: str | None


def _float32(value: float) -> float:
    """The value as the game's float holds it, which the published keys round."""
    return float(struct.unpack("f", struct.pack("f", value))[0])


def parse_spell_change(key: str, value: str) -> SpellChange:
    """Read one row of the code fact. Raise on a condition or argument it cannot read."""
    change = json.loads(value)
    where = f"{_FACT} {key}"
    names = [match["name"] for match in map(_SPELL.match, change["when"]) if match]
    if len(names) != 1:
        raise ValueError(f"{where}: expected one spell case, got {change['when']}")
    from_scenes = [match["scene"] for match in map(_SCENE.match, change["when"]) if match]
    not_scenes = [match["scene"] for match in map(_NOT_SCENE.match, change["when"]) if match]
    if len(names) + len(from_scenes) + len(not_scenes) != len(change["when"]):
        raise ValueError(f"{where}: unreadable condition in {change['when']}")
    if len(from_scenes) > 1 or (not_scenes and not from_scenes) or set(not_scenes) & set(from_scenes):
        # An else branch only narrows a scene that its own branch names.
        raise ValueError(f"{where}: unreadable scene conditions {change['when']}")
    excepted = [match["scene"] for match in map(_SCENE.match, change["unless"]) if match]
    if len(excepted) != len(change["unless"]) or len(excepted) > 1:
        raise ValueError(f"{where}: unreadable guard {change['unless']}")

    destination = change["to"]
    if destination == _SAVED_DESTINATION:
        to_scene = None
    elif destination.startswith("expr:"):
        raise ValueError(f"{where}: unreadable destination {destination}")
    else:
        to_scene = destination
    landing_text = change["landing"]
    if landing_text in _SAVED_LANDINGS:
        landing = None
    elif landing_text.startswith("expr:"):
        raise ValueError(f"{where}: unreadable landing {landing_text}")
    else:
        x, y, z = (float(part) for part in landing_text.split(","))
        landing = (x, y, z)
    sun_text = change["sun"]
    if sun_text in {"true", "false"}:
        use_sun: int | None = int(sun_text == "true")
    elif sun_text == _SAVED_SUN:
        use_sun = None
    else:
        raise ValueError(f"{where}: unreadable sun flag {sun_text}")
    if (to_scene is None) != (use_sun is None) or (to_scene is None and landing is not None):
        raise ValueError(f"{where}: a saved destination needs its saved landing and sun flag")
    return SpellChange(
        names[0],
        to_scene,
        landing,
        use_sun,
        from_scenes[0] if from_scenes else None,
        excepted[0] if excepted else None,
    )


def teleport_key(scene: str, landing: tuple[float, float, float]) -> str:
    """The stable key that the export gave each teleport landing."""
    coordinates = ":".join(f"{_float32(value):.2f}" for value in landing)
    return f"teleport:{scene.strip().lower()}:{coordinates}"


def process_travel(writer: Writer) -> int:
    """Write ``travel_routes`` and ``teleports``. Return the number of routes."""
    conn = writer.conn
    zones: dict[str, str] = {
        str(scene): str(key)
        for scene, key in conn.execute("SELECT scene_name, stable_key FROM zones WHERE scene_name IS NOT NULL")
    }

    def zone(scene: str, where: str) -> str:
        if scene not in zones:
            raise ValueError(f"{where}: scene {scene!r} has no clean zone")
        return zones[scene]

    routes = [*_zone_line_routes(conn, zone), *_jail_routes(conn, zone)]
    teleports: list[dict[str, object]] = []
    # code-fact: travel.spell_scene_changes
    rows = conn.execute("SELECT key, value FROM code_facts WHERE fact_id = ? ORDER BY CAST(key AS INTEGER)", (_FACT,))
    changes = [(key, parse_spell_change(key, value)) for key, value in rows]
    if not changes:
        raise ValueError(f"{_FACT}: missing code fact")
    for key, change in changes:
        where = f"{_FACT} {key}"
        spells = conn.execute("SELECT stable_key FROM spells WHERE spell_name = ?", (change.spell_name,)).fetchall()
        if len(spells) != 1:
            raise ValueError(f"{where}: expected one exported spell named {change.spell_name!r}")
        spell = spells[0][0]
        to_zone = zone(change.to_scene, where) if change.to_scene else None
        routes.append(
            {
                "route_key": f"travel:{spell}:{to_zone or 'saved'}",
                "mechanism": "spell",
                "source_stable_key": spell,
                "from_zone_stable_key": zone(change.from_scene, where) if change.from_scene else None,
                "except_zone_stable_key": zone(change.except_scene, where) if change.except_scene else None,
                "to_zone_stable_key": to_zone,
                "landing_x": change.landing[0] if change.landing else None,
                "landing_y": change.landing[1] if change.landing else None,
                "landing_z": change.landing[2] if change.landing else None,
                "use_sun": change.use_sun,
                "note": None,
            }
        )
        if change.to_scene is None or change.landing is None or change.from_scene is not None:
            continue
        items = [
            item
            for (item,) in conn.execute(
                "SELECT stable_key FROM items WHERE item_effect_on_click_stable_key = ? ORDER BY stable_key", (spell,)
            )
        ]
        if len(items) != 1:
            # The published table names one item for each landing.
            raise ValueError(f"{where}: expected one item that casts {spell}, got {items}")
        teleports.append(
            {
                "stable_key": teleport_key(change.to_scene, change.landing),
                "scene": change.to_scene,
                "x": _float32(change.landing[0]),
                "y": _float32(change.landing[1]),
                "z": _float32(change.landing[2]),
                "teleport_item_stable_key": items[0],
            }
        )
    keys = [str(route["route_key"]) for route in routes]
    if len(set(keys)) != len(keys):
        raise ValueError(f"travel routes share keys: {sorted({key for key in keys if keys.count(key) > 1})}")
    writer.insert_travel_routes(routes)
    writer.insert_teleports(teleports)
    return len(routes)


def _jail_routes(conn: sqlite3.Connection, zone: Callable[[str, str], str]) -> list[dict[str, object]]:
    """The jailings and releases, each checked against the conditions its note describes."""
    expected = {**_JAILS, **_RELEASES}
    facts = {fact for fact, _ in expected}
    found = {
        (fact, key): json.loads(value)
        for fact, key, value in conn.execute(
            f"SELECT fact_id, key, value FROM code_facts WHERE fact_id IN ({','.join('?' for _ in facts)})",
            tuple(sorted(facts)),
        )
    }
    if set(found) != set(expected):
        raise ValueError(f"jail scene changes changed: expected {sorted(expected)}, got {sorted(found)}")
    prisons = {_JAILS[key][0] for key in _JAILS}
    if len(prisons) != 1:
        raise ValueError(f"jailings send the player to several scenes: {sorted(prisons)}")
    prison = zone(next(iter(prisons)), "travel.jail")
    routes: list[dict[str, object]] = []
    for (fact, key), (scene, when, unless, note) in sorted(expected.items()):
        change = found[fact, key]
        where = f"{fact} {key}"
        if (change["to"], tuple(change["when"]), tuple(change["unless"])) != (scene, when, unless):
            raise ValueError(f"{where}: the jail rule changed: {change}")
        x, y, z = (float(part) for part in change["landing"].split(","))
        released = (fact, key) in _RELEASES
        routes.append(
            {
                "route_key": f"travel:jail:{fact.removeprefix('travel.jail_')}:{key}",
                "mechanism": "jail",
                "source_stable_key": fact,
                "from_zone_stable_key": prison if released else None,
                "except_zone_stable_key": None,
                "to_zone_stable_key": zone(scene, where),
                "landing_x": x,
                "landing_y": y,
                "landing_z": z,
                "use_sun": int(change["sun"] == "true"),
                "note": note,
            }
        )
    return routes


def _zone_line_routes(conn: sqlite3.Connection, zone: Callable[[str, str], str]) -> list[dict[str, object]]:
    """Usable zone lines that can send a player somewhere, with or without a fixed destination."""
    stored = {line for (line,) in conn.execute("SELECT zone_line_stable_key FROM zone_line_destination_contexts")}
    # A line that starts inactive works once an effect activates it, which its gate states.
    activated = {
        line
        for (line,) in conn.execute(
            "SELECT DISTINCT subject_stable_key FROM gate_conditions"
            " WHERE subject_kind = 'zone_line' AND gate LIKE 'activation:%'"
        )
    }
    routes: list[dict[str, object]] = []
    for line, scene, destination, active, x, y, z, use_sun in conn.execute(
        "SELECT stable_key, scene, destination_zone_stable_key, object_is_active,"
        " landing_position_x, landing_position_y, landing_position_z, use_sun_in_new_zone"
        " FROM zone_lines WHERE is_usable = 1 ORDER BY stable_key"
    ):
        saved = line in stored
        if not saved and not destination:
            continue
        # The controller that stores the return shows the exit, so it needs no activation gate.
        if not saved and not active and line not in activated:
            continue
        routes.append(
            {
                "route_key": line,
                "mechanism": "zone_line",
                "source_stable_key": line,
                "from_zone_stable_key": zone(scene, line),
                "except_zone_stable_key": None,
                "to_zone_stable_key": None if saved else destination,
                "landing_x": None if saved else x,
                "landing_y": None if saved else y,
                "landing_z": None if saved else z,
                "use_sun": None if saved else use_sun,
                "note": None,
            }
        )
    return routes
