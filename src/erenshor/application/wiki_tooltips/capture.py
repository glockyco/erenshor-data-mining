"""Capture tooltip evidence independently of the wiki renderer."""

from __future__ import annotations

import base64
import json
import sqlite3
import uuid
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any

from erenshor.application.eval.client import EvalClient
from erenshor.application.extract.database_comparison import recorded_build_id
from erenshor.domain.entities.item_kind import ItemKind, classify_item_kind

_SOURCE = Path(__file__).with_name("capture.cs")
_METHODS = {
    "item": "ItemInfoWindow.DisplayItem",
    "spell": "SpellbookSlot.ToggleSelect",
    "skill": "SkillbookSlot.ToggleSelect",
}
_QUALITIES = (1, 11, 12, 13, 14, 15, 2, 3)


def _decode(value: str) -> str:
    return base64.b64decode(value, validate=True).decode()


def decode_batch(raw: str) -> list[dict[str, Any]]:
    """Decode the evaluator's line protocol without transforming TMP text."""
    entries: list[dict[str, Any]] = []
    fields: dict[str, Any] | None = None
    for line in raw.splitlines():
        name, *columns = line.split("\t")
        if name in _METHODS:
            index, game_id, resource, *context = columns
            fields = {}
            entry = {
                "kind": name,
                "source": _METHODS[name],
                "index": int(index),
                "id": _decode(game_id),
                "resource": _decode(resource),
                "fields": fields,
            }
            if name == "item":
                entry["quantity"] = int(context[0])
            elif name == "skill":
                entry["stance_resource"] = _decode(context[0])
            entries.append(entry)
        elif name == "details" and fields is not None and name not in entries[-1]:
            game_id, worn, scaled = columns
            fields = {}
            entries[-1]["details"] = {
                "source": "ItemInfoWindow.LoadSpellDetails",
                "id": _decode(game_id),
                "worn": worn == "1",
                "level_scaled_mana": scaled == "1",
                "fields": fields,
            }
        elif name == "hover" and fields is not None and name not in entries[-1]:
            (method,) = columns
            if method not in {"Hotkeys.OnPointerEnter", "MouseOverSpellTooltip.OnPointerEnter"}:
                raise ValueError(f"Unknown tooltip hover source: {method}")
            fields = {}
            entries[-1]["hover"] = {"source": method, "fields": fields}
        elif fields is not None and name not in fields:
            active, color, face, italic, text = columns
            fields[name] = {
                "active": active == "1",
                "color": color,
                "face_color": face,
                "italic": italic == "1",
                "text": _decode(text),
            }
        else:
            raise ValueError(f"Invalid or duplicate tooltip field: {name}")
    return entries


def _equipment(row: sqlite3.Row) -> bool:
    return classify_item_kind(
        required_slot=row["required_slot"],
        teach_spell=row["teach_spell_stable_key"],
        teach_skill=row["teach_skill_stable_key"],
        template_flag=row["template"],
        click_effect=row["item_effect_on_click_stable_key"],
        disposable=row["disposable"],
        cosmetic=row["cosmetic_effect"] is not None,
    ) in (ItemKind.WEAPON, ItemKind.ARMOR)


def reconcile(database: Path, entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Join runtime rows to stable keys and require exact observation coverage."""
    exclusions: list[dict[str, str]] = []
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        by_kind[entry["kind"]].append(entry)
    with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        stances = {row["resource_name"]: row for row in db.execute("SELECT * FROM stances")}
        active_stances = Counter[str]()
        for kind, query in (
            ("item", "SELECT * FROM items"),
            ("spell", "SELECT * FROM spells"),
            ("skill", "SELECT * FROM skills"),
        ):
            identities = {row["id"]: row for row in db.execute(query)}
            seen: dict[str, set[int | None]] = defaultdict(set)
            indices: dict[str, int] = {}
            for entry in by_kind[kind]:
                game_id = entry["id"]
                row = identities.get(game_id)
                if row is None or row["resource_name"] != entry["resource"]:
                    raise ValueError(f"Unmatched {kind} identity: {game_id!r} ({entry['resource']})")
                key = row["stable_key"]
                quantity = entry.get("quantity")
                if quantity in seen[game_id] or indices.setdefault(game_id, entry["index"]) != entry["index"]:
                    raise ValueError(f"Duplicate runtime {kind} identity: {key} / {quantity}")
                seen[game_id].add(quantity)
                entry["stable_key"] = key
                if kind == "skill":
                    resource = entry["stance_resource"]
                    stance = stances.get(resource)
                    stance_key = stance["stable_key"] if stance is not None else None
                    if (resource and stance is None) or stance_key != row["stance_to_use_stable_key"]:
                        raise ValueError(f"Stance reference differs for {key}: {resource!r}")
                    if stance_key is not None:
                        entry["stance_key"] = stance_key
                        active_stances[stance_key] += 1
            for game_id, row in identities.items():
                key = row["stable_key"]
                expected = set(_QUALITIES if _equipment(row) else (1,)) if kind == "item" else {None}
                if seen[game_id] != expected:
                    raise ValueError(f"Incomplete {key}: found {seen[game_id]}, expected {expected}")
                if not row["is_wiki_generated"]:
                    exclusions.append({"stable_key": key, "reason": "not wiki-generated in the clean database"})
        for row in stances.values():
            key = row["stable_key"]
            if row["is_wiki_generated"] and active_stances[key] != 1:
                raise ValueError(f"Expected one activating skill for {key}, found {active_stances[key]}")
            if not row["is_wiki_generated"]:
                reason = "not wiki-generated in the clean database" if active_stances[key] else "no activating skill"
                exclusions.append({"stable_key": key, "reason": reason})
    return sorted(exclusions, key=lambda row: row["stable_key"])


async def _batch(client: EvalClient, kind: str, start: int, end: int) -> str:
    await client.reset()
    # Reset clears variables but Mono still sees previously emitted types.
    name = f"TooltipCapture{uuid.uuid4().hex}"
    await client.eval(_SOURCE.read_text().replace("TooltipCapture", name))
    result = await client.eval(f'{name}.Collect("{kind}", {start}, {end})', timeout_ms=15000)
    if not result.get("hasValue") or result.get("truncated") or not isinstance(result.get("value"), str):
        raise ValueError(f"Incomplete HotRepl reply for {kind} [{start}, {end})")
    if result["value"].startswith("error\t"):
        raise ValueError(result["value"].removeprefix("error\t"))
    return result["value"]


async def capture(database: Path, installed_build: str, output: Path) -> dict[str, int]:
    """Write evidence only after every expected runtime identity reconciles."""
    database = database.resolve()
    build = recorded_build_id(database)
    if installed_build != build:
        raise ValueError(f"Installed build {installed_build} does not match clean database build {build}")
    entries: list[dict[str, Any]] = []
    client = EvalClient()
    try:
        await client.connect()
        counts = tuple(int(value) for value in (await _batch(client, "counts", 0, 0)).split("\t"))
        for kind, count, size in zip(("items", "spells", "skills"), counts, (4, 8, 16), strict=True):
            for start in range(0, count, size):
                end = min(start + size, count)
                try:
                    batch = decode_batch(await _batch(client, kind, start, end))
                except Exception as exc:
                    raise ValueError(f"Capture failed for {kind} indices {start} through {end - 1}: {exc}") from exc
                if {row["index"] for row in batch} != set(range(start, end)):
                    raise ValueError(f"Capture did not return every {kind} index in [{start}, {end})")
                entries.extend(batch)
    finally:
        await client.close()
    exclusions = reconcile(database, entries)
    entries.sort(key=lambda row: (row["stable_key"], row.get("quantity", 0)))
    totals = dict(sorted(Counter(row["kind"] for row in entries).items()))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".partial")
    temporary.write_text(
        json.dumps(
            {
                "build": build,
                "installed_build": installed_build,
                "totals": totals,
                "entries": entries,
                "exclusions": exclusions,
                "failures": [],
            },
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    temporary.replace(output)
    return totals
