"""Account for item input identities without selecting item facts a second time."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from erenshor.domain.value_objects.item_provenance import ProvenanceEvidence

InputIdentity = tuple[str, str]


class ProvenanceSelection(Protocol):
    """The input rows used by selected facts and the reasons for unused inputs."""

    @property
    def input_exclusions(self) -> Mapping[InputIdentity, str]: ...

    @property
    def fact_evidence(self) -> Mapping[str, tuple[ProvenanceEvidence, ...]]: ...


# A filter defines which rows are item inputs, not which facts should be selected.
CLEAN_INPUTS: dict[str, tuple[tuple[str, ...], str]] = {
    "items": (("stable_key",), "1"),
    "item_classes": (("item_stable_key", "class_name"), "1"),
    "code_facts": (("fact_id", "key"), "1"),
    "loot_drops": (("character_stable_key", "item_stable_key"), "1"),
    "special_world_drops": (("item_stable_key", "pool"), "1"),
    "vendor_offers": (("copy_stable_key", "offer_kind", "offer_slot"), "1"),
    "character_dialogs": (("character_stable_key", "dialog_index"), "give_item_stable_key IS NOT NULL"),
    "character_quest_manager_quests": (("character_stable_key", "quest_slot"), "1"),
    "quest_variants": (("resource_name",), "item_on_complete_stable_key IS NOT NULL"),
    "quest_required_items": (("quest_variant_resource_name", "required_slot"), "1"),
    "crafting_rewards": (("recipe_item_stable_key", "reward_slot"), "1"),
    "crafting_recipes": (("recipe_item_stable_key", "material_slot"), "1"),
    "mining_node_items": (("mining_node_stable_key", "item_stable_key"), "1"),
    "water_fishables": (("water_stable_key", "type", "item_stable_key"), "1"),
    "fishing_bonus_catches": (("item_stable_key",), "1"),
    "item_bags": (("stable_key",), "item_stable_key IS NOT NULL"),
    "item_drops": (("source_item_stable_key", "dropped_item_stable_key", "pool_stable_key"), "1"),
    "spell_created_items": (("source_item_stable_key", "created_item_stable_key"), "1"),
    "item_conversions": (("input_item_stable_key", "output_item_stable_key", "mechanic"), "1"),
    "item_zone_restrictions": (("item_stable_key", "zone_stable_key"), "1"),
    "quality_offerings": (("character_stable_key",), "1"),
    "class_starting_items": (("class_name", "sort_order"), "1"),
    "auction_house_items": (("item_stable_key", "route"), "1"),
    "ui_item_sources": (("stable_key",), "1"),
    "ui_item_access_targets": (("stable_key",), "1"),
    "item_access_observations": (("component_type", "slot", "assembly_sha256"), "1"),
    "authored_sims": (("stable_key",), "1"),
    "authored_sim_references": (("source_component_key", "reference_index"), "1"),
    "authored_sim_equipment": (("authored_sim_stable_key", "position"), "1"),
    "encounter_placements": (("encounter_key", "member_spawn_stable_key"), "1"),
    "encounter_conditions": (("encounter_key", "state_scope", "state_key"), "1"),
    "encounter_completions": (("encounter_key", "event_kind", "state_scope", "state_key"), "1"),
    "encounter_event_conditions": (("encounter_key", "event_kind", "state_scope", "state_key"), "1"),
}

# Direct export identities share their key with the corresponding clean relation.
# Raw field values remain the producer's responsibility, not a second selector's.
DIRECT_NATIVE_INPUTS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "Items": ("items", ("StableKey",), ("stable_key",)),
    "ItemClasses": ("item_classes", ("ItemStableKey", "ClassName"), ("item_stable_key", "class_name")),
    "Spells": ("spells", ("StableKey",), ("stable_key",)),
    "CraftingRecipes": (
        "crafting_recipes",
        ("RecipeItemStableKey", "MaterialSlot"),
        ("recipe_item_stable_key", "material_slot"),
    ),
    "CraftingRewards": (
        "crafting_rewards",
        ("RecipeItemStableKey", "RewardSlot"),
        ("recipe_item_stable_key", "reward_slot"),
    ),
    "ClassStartingItems": ("class_starting_items", ("ClassName", "SortOrder"), ("class_name", "sort_order")),
    "ItemBags": ("item_bags", ("StableKey",), ("stable_key",)),
    "CharacterVendorItems": (
        "character_vendor_items",
        ("CharacterStableKey", "ItemSlot"),
        ("character_stable_key", "item_slot"),
    ),
    "CharacterVendorQuestUnlocks": (
        "character_vendor_quest_unlocks",
        ("CharacterStableKey", "QuestSlot"),
        ("character_stable_key", "quest_slot"),
    ),
    "CharacterDialogs": (
        "character_dialogs",
        ("CharacterStableKey", "DialogIndex"),
        ("character_stable_key", "dialog_index"),
    ),
    "CharacterQuestManagerQuests": (
        "character_quest_manager_quests",
        ("CharacterStableKey", "QuestSlot"),
        ("character_stable_key", "quest_slot"),
    ),
    "QuestVariants": ("quest_variants", ("ResourceName",), ("resource_name",)),
    "QuestRequiredItems": (
        "quest_required_items",
        ("QuestVariantResourceName", "RequiredSlot"),
        ("quest_variant_resource_name", "required_slot"),
    ),
    "AuthoredSims": ("authored_sims", ("StableKey",), ("stable_key",)),
    "AuthoredSimReferences": (
        "authored_sim_references",
        ("SourceComponentKey", "ReferenceIndex"),
        ("source_component_key", "reference_index"),
    ),
    "AuthoredSimEquipment": (
        "authored_sim_equipment",
        ("AuthoredSimStableKey", "Position"),
        ("authored_sim_stable_key", "position"),
    ),
    "TreasureLocations": ("treasure_locations", ("StableKey",), ("stable_key",)),
    "TreasureHunting": ("treasure_hunting", ("ZoneName",), ("zone_name",)),
    "UiItemSources": ("ui_item_sources", ("StableKey",), ("stable_key",)),
    "UiItemAccessTargets": ("ui_item_access_targets", ("StableKey",), ("stable_key",)),
}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class _Coverage:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def rows(self, table: str) -> list[dict[str, Any]]:
        cursor = self.connection.execute(f'SELECT * FROM "{table}"')
        columns = [column[0] for column in cursor.description or ()]
        return [dict(zip(columns, row, strict=True)) for row in cursor]

    def identities(self, table: str, columns: tuple[str, ...], where: str = "1") -> set[InputIdentity]:
        cursor = self.connection.execute(f'SELECT {",".join(columns)} FROM "{table}" WHERE {where}')
        identities: set[InputIdentity] = set()
        for row in cursor:
            identity = table, _json(tuple(row))
            if identity in identities:
                raise ValueError(f"Duplicate item input identity: {identity!r}")
            identities.add(identity)
        return identities

    def validate_dispositions(self, lifecycle_path: Path | None) -> int:
        items = {r["stable_key"]: r for r in self.rows("items")}
        dispositions = {r["item_stable_key"]: r for r in self.rows("item_dispositions")}
        missing = items.keys() - dispositions.keys()
        if missing:
            raise ValueError(f"Missing item provenance dispositions: {sorted(missing)!r}")
        for key, row in dispositions.items():
            if row["disposition"] not in ("current", "removed", "unobtainable", "unused"):
                raise ValueError(f"Invalid item provenance disposition: {key}")
            current_pages, former_pages = json.loads(row["current_pages"]), json.loads(row["former_pages"])
            if not all(
                isinstance(pages, list)
                and all(isinstance(page, str) and page for page in pages)
                and pages == sorted(set(pages))
                for pages in (current_pages, former_pages)
            ) or set(current_pages) & set(former_pages):
                raise ValueError(f"Invalid item provenance disposition pages: {key}")
            page = items.get(key, {}).get("wiki_page_name")
            if page and page not in current_pages:
                raise ValueError(f"Missing current item disposition page: {key}")
            if (row["disposition"] != "current" or key not in items) and not (row["reason"] and row["evidence"]):
                raise ValueError(f"Unreviewed item provenance disposition: {key}")
        if lifecycle_path is not None:
            from erenshor.infrastructure.content_lifecycle import load_content_lifecycle

            lifecycle = load_content_lifecycle(lifecycle_path)
            reviewed: dict[str, list[Any]] = defaultdict(list)
            for fact in lifecycle.pages.values():
                if fact.stable_key is not None and fact.stable_key.startswith("item:"):
                    reviewed[fact.stable_key].append(fact)
            keys = items.keys() | reviewed.keys()
            if dispositions.keys() != keys:
                raise ValueError("Item provenance disposition identities differ from lifecycle inputs")
            current = {key: {row["wiki_page_name"]} if row["wiki_page_name"] else set() for key, row in items.items()}
            former: dict[str, set[str]] = defaultdict(set)
            evidence: dict[str, set[str]] = defaultdict(set)
            for rename in lifecycle.renames.values():
                if rename.stable_key in keys:
                    current.setdefault(rename.stable_key, set()).add(rename.current_title)
                    former[rename.stable_key].add(rename.old_title)
                    evidence[rename.stable_key].add(rename.source)
            for split in lifecycle.splits.values():
                for title, key in zip(split.current_titles, split.stable_keys, strict=True):
                    if key in keys:
                        current.setdefault(key, set()).add(title)
                        former[key].add(split.old_title)
                        evidence[key].add(split.source)
            for key in keys:
                states = {fact.state for fact in reviewed[key]}
                if len(states) > 1:
                    raise ValueError(f"Conflicting native item lifecycle states: {key}")
                state = next(iter(states), "current")
                for fact in reviewed[key]:
                    evidence[key].add(fact.source)
                    former[key].add(fact.title)
                expected = {
                    "item_stable_key": key,
                    "disposition": state,
                    "reason": f"Reviewed {state} lifecycle" if reviewed[key] else None,
                    "evidence": "\n".join(sorted(evidence[key])) or None,
                    "current_pages": sorted(current.get(key, set())),
                    "former_pages": sorted(former[key] - current.get(key, set())),
                }
                actual = dict(dispositions[key])
                for column in ("current_pages", "former_pages"):
                    actual[column] = json.loads(actual[column])
                if actual != expected:
                    raise ValueError(f"Item provenance disposition differs from lifecycle input: {key}")
        return len(dispositions)


def validate_item_provenance(
    connection: sqlite3.Connection,
    selection: ProvenanceSelection,
    *,
    require_all_native_tables: bool,
    raw: sqlite3.Connection | None = None,
    lifecycle_path: Path | None = None,
) -> dict[str, object]:
    """Reject input rows that no selected fact uses and no recorded reason excludes."""
    from .native_item_inputs import _PRIMARY_KEYS

    if require_all_native_tables and raw is None:
        raise ValueError("Full native item coverage requires a raw database")
    coverage = _Coverage(connection)
    inputs: set[InputIdentity] = set()
    counts: dict[str, int] = {}
    for relation, (columns, where) in CLEAN_INPUTS.items():
        rows = coverage.identities(relation, columns, where)
        inputs.update(rows)
        counts[relation] = len(rows)
    unsupported: list[str] = []
    direct_counts: dict[str, int] = {}
    if raw is not None:
        native = _Coverage(raw)
        present = {row[0] for row in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        declarations = {**_PRIMARY_KEYS, "NativeItemBindings": ("BindingKey",)}
        declarations.update({table: spec[1] for table, spec in DIRECT_NATIVE_INPUTS.items()})
        for table, columns in declarations.items():
            if table not in present:
                unsupported.append(table)
                continue
            available = {row[1] for row in raw.execute(f'PRAGMA table_info("{table}")')}
            if missing := set(columns) - available:
                unsupported.append(f"{table} missing {','.join(sorted(missing))}")
                continue
            rows = {(f"raw.{table}", primary) for _, primary in native.identities(table, columns)}
            inputs.update(rows)
            counts[f"raw.{table}"] = direct_counts[f"raw.{table}"] = len(rows)
        # These item references are metadata or access requirements, not item grants.
        non_grants = {"Doors", "ChessboardItems", "ArenaRounds", "ItemStats", "CosmeticItems", "DynamicCharacterSpawns"}
        for table in present - declarations.keys() - non_grants:
            candidate_columns = {row[1] for row in raw.execute(f'PRAGMA table_info("{table}")')}
            if (
                any("Item" in column and "StableKey" in column for column in candidate_columns)
                and raw.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            ):
                raise ValueError(f"Unsupported populated native item input table: {table}")
        if require_all_native_tables and unsupported:
            raise ValueError(f"Unsupported native input tables: {sorted(unsupported)!r}")
    fact_keys = {
        row[0]
        for row in connection.execute(
            "SELECT acquisition_key FROM item_acquisitions UNION ALL SELECT use_key FROM item_uses"
        )
    }
    if orphaned := selection.fact_evidence.keys() - fact_keys:
        raise ValueError(f"Item provenance evidence has no fact: {sorted(orphaned)!r}")
    used = {
        (entry.input_relation, entry.input_primary_key)
        for entries in selection.fact_evidence.values()
        for entry in entries
    }
    exclusions = dict(selection.input_exclusions)
    if invalid := sorted(
        identity for identity, reason in exclusions.items() if not isinstance(reason, str) or not reason.strip()
    ):
        raise ValueError(f"Item provenance exclusions require a reason: {invalid!r}")
    if overlap := used & exclusions.keys():
        raise ValueError(f"Item provenance inputs both used and excluded: {sorted(overlap)!r}")
    if missing_inputs := inputs - used - exclusions.keys():
        raise ValueError(f"Unaccounted item provenance inputs: {sorted(missing_inputs)!r}")
    # Supporting rows need not all be item inputs, but recorded identities must exist.
    recorded: dict[str, set[str]] = defaultdict(set)
    for relation, primary in used | exclusions.keys():
        recorded[relation].add(primary)
    for relation, primary_keys in recorded.items():
        database, table = (raw, relation[4:]) if relation.startswith("raw.") else (connection, relation)
        if database is None:
            continue
        declared = CLEAN_INPUTS.get(table) if database is connection else None
        native_columns = declarations.get(table) if database is raw else None
        columns = (
            declared[0]
            if declared
            else native_columns
            or tuple(
                row[1]
                for row in sorted(database.execute(f'PRAGMA table_info("{table}")'), key=lambda row: row[5])
                if row[5]
            )
        )
        if not columns:
            raise ValueError(f"Invalid item provenance evidence relation: {relation}")
        available = {primary for _, primary in _Coverage(database).identities(table, columns)}
        if missing_evidence := primary_keys - available:
            raise ValueError(f"Missing item provenance evidence inputs: {relation}{sorted(missing_evidence)!r}")
        counts.setdefault(relation, len(primary_keys))
    contract_counts = {
        "acquisitions": connection.execute("SELECT COUNT(*) FROM item_acquisitions").fetchone()[0],
        "uses": connection.execute("SELECT COUNT(*) FROM item_uses").fetchone()[0],
        "dispositions": coverage.validate_dispositions(lifecycle_path),
    }
    return {
        "input_counts": dict(sorted(counts.items())),
        "contract_counts": contract_counts,
        "direct_native_counts": dict(sorted(direct_counts.items())),
        "unsupported_native_tables": sorted(unsupported),
        "direct_native_exclusions": [
            {"relation": relation, "primary_key": primary, "reason": reason}
            for (relation, primary), reason in sorted(exclusions.items())
            if relation.startswith("raw.") and relation[4:] in DIRECT_NATIVE_INPUTS
        ],
        "exclusions": [
            {"relation": relation, "primary_key": primary, "reason": reason}
            for (relation, primary), reason in sorted(exclusions.items())
        ],
    }
