"""Attach serialized acquisition inputs without inventing native pool positions."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from erenshor.domain.value_objects.item_provenance import ProvenanceEvidence

# These are native record identities, not semantic acquisition identities.
_PRIMARY_KEYS = {
    "LootDrops": ("LootTableStableKey", "ItemStableKey"),
    "LootTableSources": ("StableKey",),
    "LootTablePoolSlots": ("LootTableStableKey", "Pool", "Position"),
    "CommonWorldItems": ("Position",),
    "SpecialWorldDropItems": ("Pool", "Position"),
    "SpecialWorldDropFlags": ("Name",),
    "MiningNodes": ("StableKey",),
    "MiningNodeItems": ("MiningNodeStableKey", "ItemStableKey"),
    "MiningNodePoolSlots": ("MiningNodeStableKey", "Pool", "Position"),
    "MiningFallbackItems": ("SourceKey",),
    "Waters": ("StableKey",),
    "WaterFishables": ("WaterStableKey", "Type", "Position"),
    "ItemDrops": ("SourceItemStableKey", "DroppedItemStableKey", "PoolStableKey"),
    "ItemDropPools": ("PoolStableKey",),
    "ItemDropPoolSlots": ("PoolStableKey", "Position"),
}
_REQUIRED_COLUMNS = {
    "LootDrops": ("CharacterStableKey",),
    "LootTableSources": (
        "CharacterStableKey",
        "MiningNodeStableKey",
        "ComponentIndex",
        "ComponentIsEnabled",
        "MaxNumberDrops",
        "MaxNonCommonDrops",
        "NumberOfGuaranteedDrops",
        "UltraRareDropCount",
        "LegendaryDropCount",
        "RareDropCount",
        "UncommonDropCount",
        "CommonDropCount",
        "GuaranteeOneDropCount",
        "ActualDropsCount",
    ),
    "LootTablePoolSlots": ("ItemStableKey",),
    "CommonWorldItems": ("ItemStableKey",),
    "SpecialWorldDropItems": ("ItemStableKey",),
    "SpecialWorldDropFlags": ("Value",),
    "MiningNodes": ("CommonCount", "RareCount", "LegendCount"),
    "MiningNodePoolSlots": ("ItemStableKey",),
    "MiningFallbackItems": ("ItemStableKey",),
    "WaterFishables": ("ItemStableKey",),
    "ItemDropPools": ("SourceComponentKey", "SlotCount"),
    "ItemDropPoolSlots": ("ItemStableKey",),
    "Characters": ("StableKey", "DestroyOnDeath", "DoNotLeaveCorpse", "IsSimPlayer"),
}
_LOOT_POOLS = {
    "UltraRareDrop": "UltraRareDropCount",
    "LegendaryDrop": "LegendaryDropCount",
    "RareDrop": "RareDropCount",
    "UncommonDrop": "UncommonDropCount",
    "CommonDrop": "CommonDropCount",
    "GuaranteeOneDrop": "GuaranteeOneDropCount",
    "ActualDrops": "ActualDropsCount",
}
_SPECIAL_FLAGS = {"Masks": "DropMasks", "MoloraiMask": "DropMasks", "Empty2": "DemoBuild"}
_FALLBACK = "GameManager.GuaranteeMine"


def _encoded(primary: tuple[object, ...]) -> str:
    return json.dumps(primary, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class NativeItemInputs:
    """Resolve semantic outcomes to complete native configuration and slot evidence.

    Call once for each selected outcome, including non-acquirable loot outcomes.
    Call finalize before merging input_exclusions so omitted native outputs fail.
    Unselected loot hosts do not enter global common-item source membership.
    The caller supplies loot-ineligible copies after resolving native death exceptions.
    """

    def __init__(self, raw: sqlite3.Connection, *, unavailable_loot_copies: frozenset[str] = frozenset()) -> None:
        self.input_exclusions: dict[tuple[str, str], str] = {}
        self._unconsumed: set[tuple[str, str]] = set()
        self._rows: dict[str, list[dict[str, Any]]] = {}
        self._by_key: dict[str, dict[tuple[object, ...], dict[str, Any]]] = {}
        required = set(_PRIMARY_KEYS) | set(_REQUIRED_COLUMNS)
        present = {row[0] for row in raw.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if missing := sorted(required - present):
            raise ValueError(
                f"Native item inputs require refreshed export tables: {', '.join(missing)}. Run extract export."
            )
        for table in sorted(required):
            cursor = raw.execute(f'SELECT * FROM "{table}"')
            columns = [column[0] for column in cursor.description or ()]
            expected = set(_PRIMARY_KEYS.get(table, ())) | set(_REQUIRED_COLUMNS.get(table, ()))
            if missing_columns := sorted(expected - set(columns)):
                raise ValueError(f"Native item input table {table} lacks {missing_columns}. Run extract export.")
            rows = [dict(zip(columns, row, strict=True)) for row in cursor]
            self._rows[table] = rows
            if table not in _PRIMARY_KEYS:
                continue
            indexed = {}
            for row in rows:
                primary = self._primary(table, row)
                if primary in indexed:
                    raise ValueError(f"Duplicate native item input {table}{primary!r}")
                indexed[primary] = row
            self._by_key[table] = indexed
        self._loot_by_copy_item: dict[tuple[object, ...], list[dict[str, Any]]] = defaultdict(list)
        self._slots: dict[tuple[str, object], list[dict[str, Any]]] = defaultdict(list)
        for row in self._rows["LootDrops"]:
            source = self._require("LootTableSources", (row["LootTableStableKey"],))
            if row["CharacterStableKey"] != source["CharacterStableKey"]:
                raise ValueError(f"LootDrops host does not match native LootTableSources binding: {row!r}")
            self._loot_by_copy_item[row["CharacterStableKey"], row["ItemStableKey"]].append(row)
        for table, column in (
            ("LootTablePoolSlots", "LootTableStableKey"),
            ("MiningNodePoolSlots", "MiningNodeStableKey"),
            ("WaterFishables", "WaterStableKey"),
            ("SpecialWorldDropItems", "Pool"),
            ("ItemDropPoolSlots", "PoolStableKey"),
        ):
            for row in self._rows[table]:
                self._slots[table, row[column]].append(row)
        hosts = {row["StableKey"]: row for row in self._rows["Characters"]}
        loot_sources_with_drops = {row["LootTableStableKey"] for row in self._rows["LootDrops"]}
        self._loot_reasons: dict[str, str] = {}
        for source in self._rows["LootTableSources"]:
            host = hosts.get(source["CharacterStableKey"])
            mining_node = source["MiningNodeStableKey"]
            if mining_node is not None:
                if source["CharacterStableKey"] is not None:
                    raise ValueError(f"Native loot source links both world and mining hosts: {source['StableKey']!r}")
                self._require("MiningNodes", (mining_node,))
                if source["StableKey"] in loot_sources_with_drops or any(
                    row["ItemStableKey"] is not None for row in self._slots["LootTablePoolSlots", source["StableKey"]]
                ):
                    raise ValueError(f"Native mining loot source has world loot grants: {source['StableKey']!r}")
                host_reason = "non_world_mining_host"
            elif host is None:
                host_reason = "loot_host_missing"
            elif host["DestroyOnDeath"]:
                host_reason = "loot_host_destroy_on_death"
            elif host["DoNotLeaveCorpse"]:
                host_reason = "loot_host_do_not_leave_corpse"
            elif host["IsSimPlayer"]:
                host_reason = "non_player_host"
            elif source["StableKey"] not in loot_sources_with_drops:
                host_reason = "empty_native_loot_configuration"
            elif source["CharacterStableKey"] in unavailable_loot_copies:
                host_reason = "loot_host_undamageable"
            else:
                host_reason = "unencountered_copy"
            self._loot_reasons[source["StableKey"]] = host_reason
        flags = {row["Name"]: row["Value"] for row in self._rows["SpecialWorldDropFlags"]}
        maps_have_items = any(
            row["Position"] < 4 and row["ItemStableKey"] is not None
            for row in self._slots["SpecialWorldDropItems", "Maps"]
        )
        productive_waters = {
            row["WaterStableKey"]
            for row in self._rows["WaterFishables"]
            if row["ItemStableKey"] is not None or maps_have_items
        }
        productive_item_pools = {
            row["PoolStableKey"] for row in self._rows["ItemDropPoolSlots"] if row["ItemStableKey"] is not None
        }
        fallback_needed = any(
            row["Pool"] == "guarantee" and row["ItemStableKey"] is None for row in self._rows["MiningNodePoolSlots"]
        )
        for table in _PRIMARY_KEYS:
            for row in self._rows[table]:
                origin = self._identity(table, row)
                self._unconsumed.add(origin)
                reason: str | None = None
                if table in ("LootDrops", "LootTablePoolSlots", "LootTableSources"):
                    source_key = row["StableKey"] if table == "LootTableSources" else row["LootTableStableKey"]
                    if source_key not in self._loot_reasons:
                        raise ValueError(f"Native {table} references missing loot source {source_key!r}")
                    reason = self._loot_reasons[source_key]
                elif table == "CommonWorldItems":
                    reason = "unused_common_world_pool"
                elif table == "SpecialWorldDropItems":
                    if flag := _SPECIAL_FLAGS.get(row["Pool"]):
                        self._require("SpecialWorldDropFlags", (flag,))
                        if not flags[flag]:
                            reason = "native_world_drop_gate_disabled"
                elif table == "SpecialWorldDropFlags":
                    if not row["Value"]:
                        reason = "native_world_drop_gate_disabled"
                    elif not any(
                        _SPECIAL_FLAGS.get(slot["Pool"]) == row["Name"] and slot["ItemStableKey"] is not None
                        for slot in self._rows["SpecialWorldDropItems"]
                    ):
                        reason = "empty_native_world_drop_configuration"
                elif table == "MiningFallbackItems" and not fallback_needed:
                    reason = "unused_mining_fallback"
                elif table == "Waters" and row["StableKey"] not in productive_waters:
                    reason = "empty_native_fishing_configuration"
                elif table == "ItemDropPools" and row["PoolStableKey"] not in productive_item_pools:
                    reason = "empty_native_item_drop_configuration"
                if reason is None and "ItemStableKey" in row and row["ItemStableKey"] is None:
                    reason = "empty_native_pool_slot"
                if reason is not None:
                    self.input_exclusions[origin] = reason

    @property
    def input_tables(self) -> Mapping[str, list[dict[str, Any]]]:
        """Expose captured native payloads for the builder's input digest."""
        return MappingProxyType(self._rows)

    @staticmethod
    def _primary(table: str, row: dict[str, Any]) -> tuple[object, ...]:
        return tuple(row[column] for column in _PRIMARY_KEYS[table])

    def _identity(self, table: str, row: dict[str, Any]) -> tuple[str, str]:
        return "raw." + table, _encoded(self._primary(table, row))

    def _require(self, table: str, primary: tuple[object, ...]) -> dict[str, Any]:
        try:
            return self._by_key[table][primary]
        except KeyError as error:
            raise ValueError(f"Missing native item input {table}{primary!r}") from error

    @staticmethod
    def _positions(table: str, rows: list[dict[str, Any]], count: object) -> None:
        if count is None:
            raise ValueError(f"Native item input {table} has a null list prerequisite")
        if not isinstance(count, int) or count < 0 or sorted(row["Position"] for row in rows) != list(range(count)):
            raise ValueError(f"Native item input {table} positions do not match serialized count {count!r}")

    def _maps(self) -> list[dict[str, Any]]:
        rows = self._slots["SpecialWorldDropItems", "Maps"]
        selected = [row for row in rows if row["Position"] < 4]
        self._positions("SpecialWorldDropItems.Maps fishing draw", selected, 4)
        return selected

    def finalize(self) -> None:
        """Reject native outputs or required configuration omitted by selection."""
        missing = sorted(self._unconsumed - self.input_exclusions.keys())
        if missing:
            rendered = ", ".join(f"{relation}{primary}" for relation, primary in missing[:10])
            raise ValueError(
                f"Unconsumed mandatory native item inputs ({len(missing)}): {rendered}. "
                "Attach every native outcome to a canonical fact."
            )

    def evidence_for(self, kind: str, primary: tuple[object, ...]) -> tuple[ProvenanceEvidence, ...]:
        """Return raw-prefixed evidence and remove its inputs from exclusions.

        Common-world facts use character_drop for each selected clean copy/item
        contributor. Unsupported families have their own evidence adapters.
        """
        attachments: list[tuple[str, dict[str, Any]]] = []
        if kind == "character_drop":
            if len(primary) != 2:
                raise ValueError(f"Native character_drop expects (copy, item), got {primary!r}")
            outcomes = self._loot_by_copy_item.get(primary, [])
            if len(outcomes) != 1:
                raise ValueError(
                    f"Native character_drop requires one actual LootTable binding for {primary!r}, "
                    f"found {len(outcomes)}"
                )
            outcome = outcomes[0]
            source = self._require("LootTableSources", (outcome["LootTableStableKey"],))
            slots = self._slots["LootTablePoolSlots", source["StableKey"]]
            if {row["Pool"] for row in slots} - _LOOT_POOLS.keys():
                raise ValueError(f"Unknown native loot pool for {source['StableKey']!r}")
            for pool, column in _LOOT_POOLS.items():
                self._positions(
                    f"LootTablePoolSlots {source['StableKey']} {pool}",
                    [row for row in slots if row["Pool"] == pool],
                    source[column],
                )
            attachments = [("LootDrops", outcome), ("LootTableSources", source)]
            attachments.extend(("LootTablePoolSlots", row) for row in slots)
            if source["CommonDropCount"] > 0:
                common = self._rows["CommonWorldItems"]
                if not common:
                    raise ValueError("Native common loot substitution requires CommonWorldItems")
                self._positions("CommonWorldItems", common, len(common))
                attachments.extend(("CommonWorldItems", row) for row in common)
        elif kind == "mining":
            if len(primary) != 2:
                raise ValueError(f"Native mining expects (node, item), got {primary!r}")
            node, _ = primary
            outcome = self._require("MiningNodeItems", primary)
            source = self._require("MiningNodes", (node,))
            slots = self._slots["MiningNodePoolSlots", node]
            if {row["Pool"] for row in slots} - {"guarantee", "Common", "Rare", "Legend"}:
                raise ValueError(f"Unknown native mining pool for {node!r}")
            guarantee = [row for row in slots if row["Pool"] == "guarantee"]
            self._positions(f"MiningNodePoolSlots {node} guarantee", guarantee, 1)
            for pool in ("Common", "Rare", "Legend"):
                self._positions(
                    f"MiningNodePoolSlots {node} {pool}",
                    [row for row in slots if row["Pool"] == pool],
                    source[pool + "Count"],
                )
            attachments = [("MiningNodeItems", outcome), ("MiningNodes", source)]
            attachments.extend(("MiningNodePoolSlots", row) for row in slots)
            if guarantee[0]["ItemStableKey"] is None:
                fallback = self._require("MiningFallbackItems", (_FALLBACK,))
                if fallback["ItemStableKey"] is None:
                    raise ValueError(f"Native mining {node!r} requires non-null {_FALLBACK}")
                attachments.append(("MiningFallbackItems", fallback))
        elif kind == "fishing":
            if len(primary) != 3:
                raise ValueError(f"Native fishing expects (water, period, item), got {primary!r}")
            water, period, item = primary
            if period not in ("DayFishable", "NightFishable"):
                raise ValueError(f"Unknown native fishing period {period!r}")
            source = self._require("Waters", (water,))
            slots = self._slots["WaterFishables", water]
            selected = [row for row in slots if row["Type"] == period]
            if period == "NightFishable" and not selected:
                selected = [row for row in slots if row["Type"] == "DayFishable"]
            if not selected:
                raise ValueError(f"Native fishing {primary!r} has no eligible local pool")
            self._positions(f"WaterFishables {water} {period}", selected, len(selected))
            maps = self._maps()
            if not any(row["ItemStableKey"] == item for row in (*selected, *maps)):
                raise ValueError(f"Native fishing {primary!r} has no contributing item slot")
            attachments = [("Waters", source)]
            attachments.extend(("WaterFishables", row) for row in selected)
            attachments.extend(("SpecialWorldDropItems", row) for row in maps)
        elif kind == "fishing_bonus":
            if len(primary) != 1:
                raise ValueError(f"Native fishing_bonus expects (item,), got {primary!r}")
            slots = self._maps()
            if not any(row["ItemStableKey"] == primary[0] for row in slots):
                raise ValueError(f"Native fishing_bonus {primary!r} has no selected map slot")
            attachments = [("SpecialWorldDropItems", row) for row in slots]
        elif kind == "special_world_drop":
            if len(primary) != 2:
                raise ValueError(f"Native special_world_drop expects (item, pool), got {primary!r}")
            item, special_pool = primary
            slots = self._slots["SpecialWorldDropItems", special_pool]
            if not any(row["ItemStableKey"] == item for row in slots):
                raise ValueError(f"Native special_world_drop {primary!r} has no contributing slot")
            self._positions(f"SpecialWorldDropItems {special_pool}", slots, len(slots))
            attachments = [("SpecialWorldDropItems", row) for row in slots]
            if flag := _SPECIAL_FLAGS.get(str(special_pool)):
                flag_row = self._require("SpecialWorldDropFlags", (flag,))
                if not flag_row["Value"]:
                    raise ValueError(f"Native special_world_drop {primary!r} is disabled by {flag}")
                attachments.append(("SpecialWorldDropFlags", flag_row))
        elif kind == "item_drop":
            if len(primary) != 3:
                raise ValueError(f"Native item_drop expects (source, item, pool), got {primary!r}")
            outcome = self._require("ItemDrops", primary)
            item_pool = primary[2]
            source = self._require("ItemDropPools", (item_pool,))
            if not source["SourceComponentKey"]:
                raise ValueError(f"Native item drop pool {item_pool!r} lacks its source component binding")
            slots = self._slots["ItemDropPoolSlots", item_pool]
            self._positions(f"ItemDropPoolSlots {item_pool}", slots, source["SlotCount"])
            if not slots or not any(row["ItemStableKey"] == primary[1] for row in slots):
                raise ValueError(f"Native item_drop {primary!r} has no contributing pool slot")
            attachments = [("ItemDrops", outcome), ("ItemDropPools", source)]
            attachments.extend(("ItemDropPoolSlots", row) for row in slots)
        evidence = tuple(
            sorted(
                {ProvenanceEvidence(*self._identity(table, row)) for table, row in attachments},
                key=lambda entry: (entry.input_relation, entry.input_primary_key),
            )
        )
        for entry in evidence:
            self.input_exclusions.pop((entry.input_relation, entry.input_primary_key), None)
            self._unconsumed.discard((entry.input_relation, entry.input_primary_key))
        return evidence
