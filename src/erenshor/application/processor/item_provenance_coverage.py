"""Validate persisted item facts against independently enumerated native inputs."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from erenshor.domain.value_objects.item_provenance import (
    ItemAcquisition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceLocation,
)

InputIdentity = tuple[str, str]

_CHEST_LOOT_FACTS = ("treasure.chest_break_roll", "treasure.strike_melee", "treasure.strike_bolt")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _key(kind: str, *parts: object) -> str:
    return kind + ":" + _json(parts)


def _positive_count_bounds(distributions: tuple[str | None, ...]) -> tuple[int, int] | None:
    if any(encoded is None for encoded in distributions):
        return None
    support: set[int] = set()
    for encoded in distributions:
        if not isinstance(encoded, str):
            raise ValueError("Native copy counts require a serialized numeric distribution")
        probabilities = json.loads(encoded)
        if not isinstance(probabilities, list):
            raise ValueError("Native copy counts require a numeric distribution array")
        for count, probability in enumerate(probabilities):
            if (
                isinstance(probability, bool)
                or not isinstance(probability, (int, float))
                or not math.isfinite(probability)
                or probability < 0
            ):
                raise ValueError("Native copy-count probabilities must be finite nonnegative numbers")
            if count > 0 and probability > 0:
                support.add(count)
    return (min(support), max(support)) if support else None


class _Coverage:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.expected: dict[str, tuple[str, dict[str, Any]]] = {}
        self.inputs: set[InputIdentity] = set()
        self.excluded: dict[InputIdentity, str] = {}
        self.evidence: set[tuple[str, str, str]] = set()
        self.groups = {r["member_stable_key"]: r["group_key"] for r in self.rows("character_deduplications")}
        self.encountered = {r["member_stable_key"] for r in self.rows("character_fact_sources")}
        self.zones = {r["scene_name"]: r["stable_key"] for r in self.rows("zones")}
        self.characters = {row["stable_key"]: row for row in self.rows("characters")}
        self.items = {row["stable_key"]: row for row in self.rows("items")}
        self.direct_counts: dict[str, int] = {}
        self.unsupported_native_tables: list[str] = []
        self.direct_exclusions: list[dict[str, object]] = []
        self._placements: dict[str, tuple[dict[str, Any], ...]] = {}

    def rows(self, table: str) -> list[dict[str, Any]]:
        if table not in self.tables:
            cursor = self.connection.execute(f'SELECT * FROM "{table}"')
            columns = [column[0] for column in cursor.description or ()]
            self.tables[table] = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        return self.tables[table]

    def origin(self, table: str, *parts: object) -> InputIdentity:
        identity = table, _json(parts)
        self.inputs.add(identity)
        return identity

    def exclude(self, origin: InputIdentity, reason: str) -> None:
        self.excluded[origin] = reason

    def fact(
        self,
        family: str,
        kind: str,
        item: str,
        target: str | None,
        primary: tuple[object, ...],
        origins: tuple[InputIdentity, ...],
        *,
        quantity: float | None = None,
        chance: float | None = None,
        **dimensions: Any,
    ) -> str:
        owner = _key(family, kind, *primary)
        if family == "acquisition":
            data = asdict(ItemAcquisition(owner, item, kind, target))
            data.update(
                probability_kind="exact" if chance is not None else "unknown",
                probability_min=chance,
                probability_max=chance,
            )
        else:
            data = asdict(ItemUse(owner, item, target, kind))
        data.update(
            quantity_kind="exact" if quantity is not None else "unknown", quantity_min=quantity, quantity_max=quantity
        )
        data.update(dimensions)
        if family == "acquisition" and quantity is None and data["count_distribution"] is not None:
            count_bounds = _positive_count_bounds((data["count_distribution"],))
            if count_bounds is not None:
                low, high = count_bounds
                data.update(quantity_min=low, quantity_max=high, quantity_kind="exact" if low == high else "bounded")
        if family == "acquisition" and dimensions.get("probability_basis") == "not_applicable" and chance is None:
            data["probability_kind"] = "not_applicable"
        if family == "acquisition" and chance is not None and chance <= 0:
            data["player_access_state"] = "non_acquirable"
        if owner in self.expected:
            raise ValueError(f"Duplicate native item provenance identity: {owner}")
        self.expected[owner] = family, data
        self.inputs.update(origins)
        self.evidence.update((owner, relation, primary_key) for relation, primary_key in origins)
        return owner

    def gates(self, kind: str, key: str, item: str | None = None, scope: str = "source") -> tuple[dict[str, Any], ...]:
        rows = sorted(
            (
                r
                for r in self.rows("gate_conditions")
                if r["subject_kind"] == kind and r["subject_stable_key"] == key and r["item_stable_key"] in (None, item)
            ),
            key=_json,
        )
        indices: Counter[tuple[str, int]] = Counter()
        atoms = []
        for row in rows:
            gate = _key("gate", kind, key, item, row["gate"])
            group = gate, row["group_index"]
            atoms.append(
                self.condition(
                    gate,
                    row["atom_kind"],
                    row["atom_stable_key"],
                    group_index=row["group_index"],
                    atom_index=indices[group],
                    reference_slot=row["atom_slot"],
                    scope=scope,
                )
            )
            indices[group] += 1
        return tuple(atoms)

    @staticmethod
    def condition(gate: str, predicate: str, reference: str | None = None, **values: Any) -> dict[str, Any]:
        return asdict(
            ProvenanceCondition(
                gate, values.pop("group_index", 0), values.pop("atom_index", 0), predicate, reference, **values
            )
        )

    def entries(self, kind: str, key: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                r["zone_line_stable_key"]
                for r in self.rows("target_entries")
                if r["target_kind"] == kind and r["target_stable_key"] == key
            )
        )

    def location(
        self,
        row: Mapping[str, Any],
        key: str,
        relation: str,
        coordinate: str | None,
        conditions: tuple[dict[str, Any], ...] = (),
        entries: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        data = asdict(ProvenanceLocation(key, relation))
        data.update(
            scene=row.get("scene"),
            zone_stable_key=self.zones.get(row.get("scene")),
            placement_key=key,
            coordinate_stable_key=coordinate,
            x=row.get("x"),
            y=row.get("y"),
            z=row.get("z"),
            gate_scope=key if conditions else None,
            player_level_min=row.get("player_level_min"),
            player_level_max=row.get("player_level_max"),
            conditions=conditions,
            entry_zone_line_keys=entries,
        )
        return data

    def encounter_atoms(self, spawn: str, scope: str) -> tuple[dict[str, Any], ...]:
        atoms: list[dict[str, Any]] = []
        actor: str | None
        value: str | None
        quests = {row["stable_key"] for row in self.rows("quests")}
        for placement in self.rows("encounter_placements"):
            if placement["member_spawn_stable_key"] != spawn:
                continue
            encounter = placement["encounter_key"]
            for row in self.rows("encounter_conditions"):
                if row["encounter_key"] != encounter:
                    continue
                if row["required_value"] not in ("true", "false"):
                    raise ValueError(f"Unsupported native encounter state value: {encounter}")
                if row["state_scope"] == "account":
                    if row["state_key"] != "account_state:reliquary_claimed":
                        raise ValueError(f"Unsupported native account state: {row['state_key']}")
                    predicate, actor, value = "account_state", "account", row["required_value"]
                elif row["state_scope"] == "character" and row["state_key"] in quests:
                    predicate = "quest_done" if row["required_value"] == "true" else "quest_not_done"
                    actor, value = None, None
                else:
                    raise ValueError(f"Missing native encounter character quest: {row['state_key']}")
                atoms.append(
                    self.condition(
                        _key("encounter_availability", encounter, row["state_scope"], row["state_key"]),
                        predicate,
                        row["state_key"],
                        actor=actor,
                        value=value,
                        scope=scope,
                    )
                )
        return tuple(atoms)

    def placements(self, copy: str) -> tuple[dict[str, Any], ...]:
        if copy in self._placements:
            return self._placements[copy]
        locations = []
        for row in self.rows("character_spawns"):
            if row["character_stable_key"] != copy:
                continue
            spawn = row["spawn_point_stable_key"]
            key = _key("placement", copy, spawn, row["is_directly_placed"])
            conditions = self.gates("character", copy, scope=key)
            if spawn:
                conditions += self.gates("spawn_point", spawn, scope=key)
                conditions += self.encounter_atoms(spawn, key)
            if row.get("furniture_item_stable_key") and not any(a["predicate"] == "room_furnished" for a in conditions):
                conditions += (
                    self.condition(
                        "furniture",
                        "room_furnished",
                        row["furniture_item_stable_key"],
                        reference_slot=row["furniture_slot"],
                        scope=key,
                    ),
                )
            entries = tuple(sorted(set(self.entries("character", copy) + self.entries("spawn_point", str(spawn)))))
            locations.append(
                self.location(
                    row, key, "fixed" if row["is_directly_placed"] else "spawn", str(spawn or copy), conditions, entries
                )
            )
            locations[-1]["source_copy_stable_key"] = copy
        for row in self.rows("treasure_chest_possible_spawns"):
            if row["chest_character_stable_key"] == copy:
                key = row["treasure_location_stable_key"]
                locations.append(self.location(row, key, "possible_treasure", key))
                locations[-1]["source_copy_stable_key"] = copy
        result = tuple(locations) or (
            asdict(ProvenanceLocation(_key("unlocated", copy), "unlocated", source_copy_stable_key=copy)),
        )
        self._placements[copy] = result
        return result

    def required_facts(self, *fact_ids: str) -> tuple[InputIdentity, ...]:
        facts = {(row["fact_id"], row["key"]): row["value"] for row in self.rows("code_facts")}
        for fact_id in fact_ids:
            if facts.get((fact_id, "ok")) != "true":
                raise ValueError(f"Missing native item mechanic evidence: {fact_id}")
        return tuple(("code_facts", _json((fact_id, "ok"))) for fact_id in fact_ids)

    def ownership(self, item: str) -> tuple[tuple[dict[str, Any], ...], tuple[InputIdentity, ...]]:
        if not self.items[item]["is_unique"]:
            return (), ()
        if not any(
            row["fact_id"] == "loot.owned_unique_replacement" and row["key"] == "ok" and row["value"] == "true"
            for row in self.rows("code_facts")
        ):
            raise ValueError("Missing native owned unique-item replacement evidence")
        return (
            (
                self.condition(
                    "not_owned",
                    "item_not_owned",
                    item,
                    value="stored_slots_and_equipment_slots",
                    phase="source_initialization",
                ),
            ),
            (self.origin("code_facts", "loot.owned_unique_replacement", "ok"),),
        )

    def enumerate_loot(self) -> None:
        initialization_origins = self.required_facts(
            "loot.start_initialization_sequence",
            "loot.character_component_binding",
            "loot.corpse_component_binding",
        )
        context = tuple(
            self.condition(
                "probability_context",
                "formula_operand",
                atom_index=index,
                actor="player" if name in ("top_guild_bonus", "initial_owned_unique_item_count") else None,
                value=name,
                minimum=value,
                maximum=value,
                scope="probability",
                phase="source_initialization",
            )
            for index, (name, value) in enumerate(
                (
                    ("server_loot_rate", 1.0),
                    ("loot_bless_bonus", 0.0),
                    ("top_guild_bonus", 0.0),
                    ("initial_owned_unique_item_count", 0.0),
                )
            )
        )
        common: dict[str, list[tuple[dict[str, Any], InputIdentity]]] = defaultdict(list)
        native_flags = (
            "is_common",
            "is_uncommon",
            "is_rare",
            "is_legendary",
            "is_ultra_rare",
            "is_guaranteed",
            "is_actual",
        )
        for row in self.rows("loot_drops"):
            copy, item = row["character_stable_key"], row["item_stable_key"]
            origin = self.origin("loot_drops", copy, item)
            enabled = row["source_component_is_enabled"]
            if enabled not in (0, 1):
                raise ValueError("Native loot component enablement must be an explicit boolean")
            initializes = enabled == 1
            if not initializes and not row["is_actual"]:
                raise ValueError("Disabled native loot cannot execute initializer pools")
            if copy not in self.encountered:
                self.exclude(origin, "unencountered_copy")
            elif row["is_common_world_item"] and not any(row[k] for k in native_flags):
                if self.characters[copy]["can_be_damaged"] or self.characters[copy]["treasure_chest"]:
                    common[item].append((row, origin))
                else:
                    self.exclude(origin, "loot_host_undamageable")
            else:
                ownership_conditions, ownership_origins = self.ownership(item) if initializes else ((), ())
                death_origins = (
                    self.required_facts(*_CHEST_LOOT_FACTS)
                    if not self.characters[copy]["can_be_damaged"] and self.characters[copy]["treasure_chest"]
                    else ()
                )
                self.fact(
                    "acquisition",
                    "character_drop",
                    item,
                    self.groups[copy],
                    (copy, item),
                    (origin, *ownership_origins, *initialization_origins, *death_origins),
                    chance=row["drop_probability"],
                    probability_basis="per_kill",
                    source_group_key=self.groups[copy],
                    source_copy_stable_key=copy,
                    expected_quantity=row["expected_per_kill"],
                    count_distribution=row["drop_count_distribution"],
                    guarantee_scope="pool" if initializes and row["is_guaranteed"] else None,
                    guaranteed_roll_count=self.characters[copy]["guaranteed_drop_rolls"]
                    if initializes and row["is_guaranteed"]
                    else None,
                    player_access_state=(
                        "non_acquirable"
                        if not (self.characters[copy]["can_be_damaged"] or self.characters[copy]["treasure_chest"])
                        else "verified_player"
                        if initializes
                        else "unconfirmed_player"
                    ),
                    mechanic=None if initializes else "preseeded_before_start",
                    conditions=(
                        *self.gates("character", copy),
                        *ownership_conditions,
                        *(context if initializes else ()),
                    ),
                    locations=self.placements(copy),
                )
        for item, rows in common.items():
            death_origins = (
                self.required_facts(*_CHEST_LOOT_FACTS)
                if any(not self.characters[row["character_stable_key"]]["can_be_damaged"] for row, _ in rows)
                else ()
            )
            chances = [row["drop_probability"] for row, _ in rows]
            bounds: dict[str, Any] = {}
            count_bounds = _positive_count_bounds(tuple(row["drop_count_distribution"] for row, _ in rows))
            if count_bounds is not None:
                low, high = count_bounds
                bounds.update(quantity_min=low, quantity_max=high, quantity_kind="exact" if low == high else "bounded")
            if all(chance is not None for chance in chances):
                low, high = min(chances), max(chances)
                bounds.update(
                    probability_kind="exact" if low == high else "bounded",
                    probability_min=low,
                    probability_max=high,
                    player_access_state="non_acquirable" if high <= 0 else "verified_player",
                )
            self.fact(
                "acquisition",
                "common_world_item",
                item,
                None,
                (item,),
                (*tuple(origin for _, origin in rows), *initialization_origins, *death_origins),
                probability_basis="per_kill",
                conditions=context,
                **bounds,
            )
        for row in self.rows("special_world_drops"):
            item, pool = row["item_stable_key"], row["pool"]
            ownership_conditions, ownership_origins = self.ownership(item)
            self.fact(
                "acquisition",
                "special_world_drop",
                item,
                None,
                (item, pool),
                (self.origin("special_world_drops", item, pool), *ownership_origins, *initialization_origins),
                chance=row["drop_probability"],
                probability_basis="per_kill",
                variant_key=pool,
                mechanic="default_loot_rate_without_bonuses",
                conditions=(
                    *(
                        (
                            self.condition(
                                "enemy_level",
                                "actor_level",
                                actor="enemy",
                                minimum=row["min_level_exclusive"],
                                minimum_inclusive=False,
                                phase="source_initialization",
                            ),
                        )
                        if row["min_level_exclusive"] > 0
                        else ()
                    ),
                    *ownership_conditions,
                    *context,
                ),
            )

    def enumerate_characters(self) -> None:
        offers: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in self.rows("vendor_offers"):
            offers[row["copy_stable_key"], row["item_stable_key"]].append(row)
        for (copy, item), rows in sorted(offers.items()):
            unlock_gate = _key("gate", "vendor_item", copy, item, "vendor_unlock")
            conditions = self.gates("character", copy) + tuple(
                atom for atom in self.gates("vendor_item", copy, item) if atom["gate_key"] != unlock_gate
            )
            if not any(row["offer_kind"] == "base" for row in rows):
                quests = sorted({row["quest_stable_key"] for row in rows})
                conditions += tuple(
                    self.condition(unlock_gate, "quest_done", quest, group_index=index)
                    for index, quest in enumerate(quests)
                )
            self.fact(
                "acquisition",
                "vendor",
                item,
                self.groups[copy],
                (copy, item),
                tuple(self.origin("vendor_offers", copy, row["offer_kind"], row["offer_slot"]) for row in rows),
                source_group_key=self.groups[copy],
                source_copy_stable_key=copy,
                probability_basis="not_applicable",
                conditions=conditions,
                locations=self.placements(copy),
            )
        variants = {r["resource_name"]: r for r in self.rows("quest_variants")}
        for row in self.rows("character_dialogs"):
            if not row["give_item_stable_key"]:
                continue
            copy, slot, item = row["character_stable_key"], row["dialog_index"], row["give_item_stable_key"]
            origin = self.origin("character_dialogs", copy, slot)
            if copy not in self.encountered:
                self.exclude(origin, "unencountered_copy")
                continue
            conditions = (
                *self.gates("character", copy),
                self.condition("not_owned", "item_not_owned", item, value="stored_slots_and_equipment_slots"),
            )
            if row["required_quest_stable_key"]:
                conditions += (self.condition("dialog_prerequisite", "quest_done", row["required_quest_stable_key"]),)
            assigned = row["assign_quest_variant_resource_name"]
            if assigned and assigned not in variants:
                raise ValueError(f"Dialog assignment references absent quest variant: {assigned}")
            if assigned in variants and not variants[assigned]["repeatable"]:
                conditions += (
                    self.condition("dialog_assignment", "quest_not_done", variants[assigned]["quest_stable_key"]),
                )
            self.fact(
                "acquisition",
                "dialog",
                item,
                self.groups[copy],
                (copy, slot),
                (origin,),
                quantity=1,
                source_group_key=self.groups[copy],
                source_copy_stable_key=copy,
                variant_key=str(slot),
                probability_basis="not_applicable",
                conditions=conditions,
                locations=self.placements(copy),
            )

    def enumerate_crafting(self) -> None:
        forge_origins = self.required_facts(
            "smithing.template_flag",
            "smithing.fuel_flag",
            "smithing.single_template_amount",
            "smithing.single_fuel_amount",
            "smithing.fuel_quality",
        )
        for row in self.rows("crafting_rewards"):
            recipe, slot, item = row["recipe_item_stable_key"], row["reward_slot"], row["reward_item_stable_key"]
            origins = (self.origin("crafting_rewards", recipe, slot), *forge_origins)
            executable = (
                slot == 1
                and bool(self.items[recipe]["template"])
                and str(self.items[recipe]["id"]) not in ("31377423", "2298018", "2265228")
            )
            conditions: tuple[dict[str, Any], ...] = (
                () if executable else (self.condition("unexecuted_reward_slot", "never"),)
            )
            if self.items[item]["required_slot"] not in ("General", "Aura", "Charm"):
                conditions += (
                    self.condition(
                        "fuel_quality",
                        "formula_operand",
                        value="selected_fuel_level_plus_one",
                        phase="operation_outcome",
                    ),
                )
            dimensions: dict[str, Any] = {
                "variant_key": str(slot),
                "mechanic": _key("crafting", recipe),
                "conditions": conditions,
            }
            outcome = self.fact(
                "acquisition",
                "crafting",
                item,
                recipe,
                (recipe, slot),
                origins,
                quantity=row["reward_quantity"],
                probability_basis="per_use",
                player_access_state="verified_player" if executable else "non_acquirable",
                **dimensions,
            )
            self.fact(
                "use",
                "crafting_recipe",
                recipe,
                item,
                (recipe, slot),
                origins,
                quantity=1,
                outcome_key=outcome,
                **dimensions,
            )
        for row in self.rows("crafting_recipes"):
            recipe, slot = row["recipe_item_stable_key"], row["material_slot"]
            material = self.items[row["material_item_stable_key"]]
            conditions = ()
            if not self.items[recipe]["template"] or str(self.items[recipe]["id"]) in (
                "31377423",
                "2298018",
                "2265228",
            ):
                conditions = (self.condition("unexecuted_material_slot", "never"),)
            if material["required_slot"] not in ("General", "Aura") and row["material_quantity"] == 1:
                conditions += (self.condition("material_quality", "quality", value="normal", phase="operation_input"),)
            self.fact(
                "use",
                "crafting_material",
                row["material_item_stable_key"],
                recipe,
                (recipe, slot),
                (self.origin("crafting_recipes", recipe, slot), *forge_origins),
                quantity=row["material_quantity"],
                material_slot=slot,
                mechanic=_key("crafting", recipe),
                conditions=conditions,
            )

    def enumerate_quests(self) -> None:
        variants = {r["resource_name"]: r for r in self.rows("quest_variants")}
        routes: dict[str, list[tuple[dict[str, Any], InputIdentity]]] = defaultdict(list)
        for row in self.rows("character_quest_manager_quests"):
            origin = self.origin("character_quest_manager_quests", row["character_stable_key"], row["quest_slot"])
            variant = row["quest_variant_resource_name"]
            if row["character_stable_key"] not in self.encountered:
                self.exclude(origin, "unencountered_copy")
            elif variant not in variants or not variants[variant]["item_on_complete_stable_key"]:
                self.exclude(origin, "no_executed_item_grant")
            else:
                routes[variant].append((row, origin))
        for variant, row in variants.items():
            if not row["item_on_complete_stable_key"]:
                continue
            origin = self.origin("quest_variants", variant)
            if not routes[variant]:
                self.exclude(origin, "no_executed_item_grant")
            for route, route_origin in routes[variant]:
                copy, quest = route["character_stable_key"], row["quest_stable_key"]
                mechanic = _key("trade_reward", variant, copy, route["quest_slot"])
                conditions = self.gates("character", copy)
                if not row["repeatable"]:
                    conditions += (self.condition("quest_available", "quest_not_done", quest),)
                required: Counter[str] = Counter()
                for material in self.rows("quest_required_items"):
                    if material["quest_variant_resource_name"] == variant:
                        required[material["item_stable_key"]] += material["quantity"]
                conditions += tuple(
                    self.condition("turnin_items", "item_held", item, atom_index=index, minimum=quantity)
                    for index, (item, quantity) in enumerate(sorted(required.items()))
                )
                self.fact(
                    "acquisition",
                    "quest_reward",
                    row["item_on_complete_stable_key"],
                    quest,
                    (variant, mechanic),
                    (origin, route_origin),
                    quantity=1,
                    variant_key=variant,
                    mechanic=mechanic,
                    source_copy_stable_key=copy,
                    source_group_key=self.groups[copy],
                    probability_basis="not_applicable",
                    conditions=conditions,
                    locations=self.placements(copy),
                )
        for row in self.rows("quest_required_items"):
            variant, slot = row["quest_variant_resource_name"], row["required_slot"]
            self.fact(
                "use",
                "quest_requirement",
                row["item_stable_key"],
                variants[variant]["quest_stable_key"],
                (variant, slot),
                (self.origin("quest_required_items", variant, slot),),
                quantity=row["quantity"],
                variant_key=variant,
                material_slot=slot,
            )

    def enumerate_gathering(self) -> None:
        for table, kind, column, location_table, basis in (
            ("mining_node_items", "mining", "mining_node_stable_key", "mining_nodes", "per_node"),
            ("water_fishables", "fishing", "water_stable_key", "waters", "per_successful_catch"),
        ):
            locations = {r["stable_key"]: r for r in self.rows(location_table)}
            for row in self.rows(table):
                source, item, period = row[column], row["item_stable_key"], row.get("type")
                primary = (source, period, item) if period is not None else (source, item)
                conditions = (
                    ()
                    if period is None
                    else (
                        self.condition(
                            "time",
                            "time_of_day",
                            value={"DayFishable": "day", "NightFishable": "night"}[period],
                            phase="operation_input",
                        ),
                    )
                )
                self.fact(
                    "acquisition",
                    kind,
                    item,
                    source,
                    primary,
                    (self.origin(table, *primary),),
                    quantity=1,
                    chance=row["drop_chance"],
                    probability_basis=basis,
                    variant_key=period,
                    conditions=conditions,
                    locations=(self.location(locations[source], source, "fixed", source),),
                )
        for row in self.rows("fishing_bonus_catches"):
            item = row["item_stable_key"]
            self.fact(
                "acquisition",
                "fishing_bonus",
                item,
                None,
                (item,),
                (self.origin("fishing_bonus_catches", item),),
                chance=row["chance_per_catch"],
                quantity=1,
                probability_basis="per_successful_catch",
                probability_stage="native_pool",
                mechanic="fishing_global_replacement",
            )
        for row in self.rows("item_bags"):
            if row["item_stable_key"]:
                key = row["stable_key"]
                bag_origins = self.required_facts("item_bag.unique_initialization", "item_bag.single_pickup")
                bag_conditions = self.gates("item_bag", key)
                if self.items[row["item_stable_key"]]["is_unique"]:
                    bag_conditions += (
                        self.condition(
                            "initial_ownership",
                            "item_not_owned",
                            row["item_stable_key"],
                            value="stored_slots_and_equipment_slots",
                            phase="source_initialization",
                        ),
                    )
                self.fact(
                    "acquisition",
                    "item_bag",
                    row["item_stable_key"],
                    key,
                    (key,),
                    (self.origin("item_bags", key), *bag_origins),
                    quantity=1,
                    probability_basis="not_applicable",
                    conditions=bag_conditions,
                    locations=(self.location(row, key, "fixed", key, entries=self.entries("item_bag", key)),),
                )

    def enumerate_operations(self) -> None:
        pool_fact = "item.fossil_pool_grant"
        pool_operands = {row["key"]: row["value"] for row in self.rows("code_facts") if row["fact_id"] == pool_fact}
        if (
            set(pool_operands) != {"spell_name", "quantity", "pool", "rolls"}
            or not all(isinstance(value, str) and value for value in pool_operands.values())
            or int(pool_operands["quantity"]) != 1
            or int(pool_operands["rolls"]) != 1
        ):
            raise ValueError("Native uniform item draw requires single-item, single-roll switch operands")
        pool_origins = tuple(
            ("code_facts", _json((pool_fact, key))) for key in ("spell_name", "quantity", "pool", "rolls")
        )
        for row in self.rows("item_drops"):
            source, item, pool = row["source_item_stable_key"], row["dropped_item_stable_key"], row["pool_stable_key"]
            origins = (
                self.origin("item_drops", source, item, pool),
                *pool_origins,
                *self.required_facts("inventory.default_single_add", "inventory.default_single_force"),
            )
            mechanic = _key("item_drop", source, pool)
            outcome = self.fact(
                "acquisition",
                "item_drop",
                item,
                source,
                (source, item, pool),
                origins,
                chance=row["drop_probability"],
                quantity=1,
                expected_quantity=float(row["drop_probability"]) / 100,
                count_distribution=json.dumps(
                    [1.0 - float(row["drop_probability"]) / 100, float(row["drop_probability"]) / 100]
                ),
                probability_basis="per_use",
                mechanic=mechanic,
                guarantee_scope="pool",
                guaranteed_roll_count=1,
                variant_key=pool,
            )
            self.fact(
                "use",
                "item_drop",
                source,
                item,
                (source, item, pool),
                origins,
                quantity=1,
                mechanic=mechanic,
                variant_key=pool,
                outcome_key=outcome,
            )
        for row in self.rows("spell_created_items"):
            source, item, spell = row["source_item_stable_key"], row["created_item_stable_key"], row["spell_stable_key"]
            fact_id = row["grant_fact_id"]
            operands = {r["key"]: r["value"] for r in self.rows("code_facts") if r["fact_id"] == fact_id}
            spells = {r["stable_key"]: r for r in self.rows("spells")}
            if (
                set(operands) != {"spell_name", "created_item_id", "quantity"}
                or operands["created_item_id"] != str(self.items[item]["id"])
                or int(operands["quantity"]) != row["quantity"]
                or row["quantity"] <= 0
                or spell not in spells
                or spells[spell]["spell_name"] != operands["spell_name"]
                or self.items[source]["item_effect_on_click_stable_key"] != spell
            ):
                raise ValueError(f"Literal item grant differs from native click or extracted operands: {source}")
            origins = (
                self.origin("spell_created_items", source, item),
                *(self.origin("code_facts", fact_id, key) for key in ("spell_name", "created_item_id", "quantity")),
                *self.required_facts("inventory.default_single_add", "inventory.default_single_force"),
            )
            dimensions: dict[str, Any] = {"mechanic": _key("spell_created", source, spell), "variant_key": spell}
            outcome = self.fact(
                "acquisition",
                "spell_created",
                item,
                source,
                (source, spell, item),
                origins,
                quantity=row["quantity"],
                probability_basis="per_use",
                **dimensions,
            )
            self.fact(
                "use",
                "spell_created",
                source,
                item,
                (source, spell, item),
                origins,
                quantity=1,
                outcome_key=outcome,
                **dimensions,
            )
        for row in self.rows("item_conversions"):
            source, item, mechanic, zone = (
                row[k] for k in ("input_item_stable_key", "output_item_stable_key", "mechanic", "zone_stable_key")
            )
            origins = (self.origin("item_conversions", source, item, mechanic),)
            location = asdict(
                ProvenanceLocation(_key("mechanic_zone", mechanic, zone), "mechanic_zone", zone_stable_key=zone)
            )
            dimensions = {
                "quantity": 1,
                "mechanic": mechanic,
                "conditions": (self.condition("zone", "zone_use", zone),),
                "locations": (location,),
            }
            outcome = self.fact(
                "acquisition",
                "item_conversion",
                item,
                source,
                (source, item, mechanic),
                origins,
                probability_basis="per_use",
                **dimensions,
            )
            self.fact(
                "use",
                "item_conversion",
                source,
                item,
                (source, item, mechanic),
                origins,
                outcome_key=outcome,
                **dimensions,
            )
        for row in self.rows("item_zone_restrictions"):
            item, zone = row["item_stable_key"], row["zone_stable_key"]
            self.fact(
                "use",
                "zone_restriction",
                item,
                zone,
                (item, zone),
                (self.origin("item_zone_restrictions", item, zone),),
                mechanic=row["outcome"],
                conditions=(self.condition("zone", "zone_use", zone),),
            )
        for row in self.rows("quality_offerings"):
            copy = row["character_stable_key"]
            origin = self.origin("quality_offerings", copy)
            operation = (
                self.condition(
                    "stone_counts",
                    "formula_operand",
                    value="equal_positive_stone_counts",
                    minimum=1,
                    phase="operation_input",
                ),
                self.condition(
                    "offered_items", "formula_operand", value="all_offered_slots_consumed", phase="mechanic_parameter"
                ),
                self.condition(
                    "failure", "formula_operand", value="return_original_equipment_quality", phase="operation_outcome"
                ),
            )
            conditions = (
                self.condition("result_quality", "quality", value=row["result_quality"], phase="operation_outcome"),
                self.condition("enhanced_quality", "quality", value=row["enhanced_quality"], phase="operation_outcome"),
                self.condition(
                    "chance_per_pair",
                    "formula_operand",
                    value="chance_per_stone_pair",
                    minimum=row["chance_per_stone_pair"],
                    phase="mechanic_parameter",
                ),
                self.condition(
                    "chance_per_improvement",
                    "formula_operand",
                    value="chance_per_improvement_level",
                    minimum=row["chance_per_improvement_level"],
                    phase="mechanic_parameter",
                ),
                self.condition(
                    "enhance_chance",
                    "formula_operand",
                    value="enhance_chance_per_stone_pair",
                    minimum=row["enhance_chance_per_stone_pair"],
                    phase="mechanic_parameter",
                ),
                *operation,
            )
            for slot, column in enumerate(("first_item_stable_key", "second_item_stable_key")):
                self.fact(
                    "use",
                    "quality_offering",
                    row[column],
                    self.groups.get(copy, copy),
                    (copy, slot),
                    (origin,),
                    quantity_kind="bounded",
                    quantity_min=1,
                    quantity_max=None,
                    material_slot=slot,
                    mechanic=_key("quality_offering", copy),
                    conditions=conditions,
                    locations=self.placements(copy),
                )
            for gear in self.rows("items"):
                if gear["required_slot"] in ("General", "Aura"):
                    continue
                item = gear["stable_key"]
                self.fact(
                    "use",
                    "quality_offering",
                    item,
                    self.groups.get(copy, copy),
                    (copy, item, "equipment"),
                    (origin, self.origin("items", item)),
                    quantity=1,
                    material_slot=2,
                    mechanic=_key("quality_offering", copy),
                    locations=self.placements(copy),
                    conditions=(
                        *conditions,
                        self.condition("eligible_quality", "quality", minimum=1, maximum=1, phase="operation_input"),
                        self.condition(
                            "eligible_quality", "quality", group_index=1, minimum=11, phase="operation_input"
                        ),
                        self.condition(
                            "improvement",
                            "formula_operand",
                            value="max_quality_minus_ten_or_zero",
                            phase="mechanic_parameter",
                        ),
                        self.condition(
                            "success",
                            "formula_operand",
                            value="integer_roll_0_99_lt_pair_chance_plus_improvement_bonus",
                            phase="operation_outcome",
                        ),
                        self.condition(
                            "enhancement",
                            "formula_operand",
                            value="improved_input_and_second_integer_roll_0_99_lt_bonus_plus_pair_enhancement",
                            phase="operation_outcome",
                        ),
                    ),
                )

    def enumerate_starting_and_auctions(self) -> None:
        for row in self.rows("class_starting_items"):
            class_name, slot = row["class_name"], row["sort_order"]
            self.fact(
                "acquisition",
                "starting_class",
                row["item_stable_key"],
                "class:" + class_name.lower(),
                (class_name, slot),
                (self.origin("class_starting_items", class_name, slot),),
                quantity=1,
                variant_key=str(slot),
                probability_basis="not_applicable",
            )
        brokers = {r["character_stable_key"] for r in self.rows("auction_house_brokers")} & self.encountered
        locations = tuple(
            {**location, "relation": "interaction"} for copy in sorted(brokers) for location in self.placements(copy)
        )
        locations = locations or (asdict(ProvenanceLocation("auction_house:unlocated", "unlocated")),)
        for row in self.rows("auction_house_items"):
            item, route = row["item_stable_key"], row["route"]
            conditions = tuple(
                self.condition(
                    "level_" + actor,
                    "actor_level",
                    actor=actor,
                    minimum=row[f"min_{actor}_level"],
                    maximum=row[f"max_{actor}_level"],
                )
                for actor in ("sim", "player")
                if row[f"min_{actor}_level"] is not None or row[f"max_{actor}_level"] is not None
            )
            self.fact(
                "acquisition",
                "auction_house",
                item,
                "mechanic:auction_house",
                (item, route),
                (self.origin("auction_house_items", item, route),),
                variant_key=route,
                mechanic=_key("auction_house", route),
                probability_basis="per_listing_opportunity",
                conditions=conditions,
                locations=locations,
            )

    def enumerate_ui(self) -> None:
        builds = self.rows("code_facts_meta")
        observations = {}
        support = {}
        for row in self.rows("item_access_observations"):
            origin = self.origin("item_access_observations", row["component_type"], row["slot"], row["assembly_sha256"])
            support[origin] = "unused_access_observation"
            replenishment = {"ReplenishTMOGHide": "while_source_active", "PlanningTableUI": "none_observed"}
            if (
                row["component_type"] not in replenishment
                or row["player_access_state"] != "verified_player"
                or row["transfer"] != "normal_pointer_inventory_transfer"
                or row["replenishment"] != replenishment[row["component_type"]]
                or not row["receipt"].strip()
                or not row["assembly_sha256"]
                or not row["slot"]
            ):
                raise ValueError(f"Invalid native item access observation: {origin!r}")
            if len(builds) == 1 and row["assembly_sha256"] == builds[0]["assembly_sha256"]:
                observations[row["component_type"], row["slot"]] = origin
        for row in self.rows("ui_item_access_targets"):
            support[self.origin("ui_item_access_targets", row["stable_key"])] = "unused_native_ui_target"
        for row in self.rows("ui_item_access_activations"):
            support[self.origin("ui_item_access_activations", row["stable_key"])] = "unused_native_ui_activation"
        consumed: set[InputIdentity] = set()
        for row in self.rows("ui_item_sources"):
            source, slot, component = row["stable_key"], str(row["slot"]), row["component_type"]
            origin = self.origin("ui_item_sources", source)
            if component == "ReplenishTMOGHide":
                item, quantity, mechanic = row["replenish_item_stable_key"], 1, "cosmetic_panel"
                locations: tuple[dict[str, Any], ...] = (
                    asdict(ProvenanceLocation(_key("ui_unlocated", source), "unlocated")),
                )
            elif component == "PlanningTableUI":
                item, quantity, mechanic = (
                    row["serialized_item_stable_key"],
                    row["serialized_quantity"],
                    "planning_table",
                )
                possible: list[dict[str, Any]] = []
                for target in self.rows("ui_item_access_targets"):
                    if target["tag"] != "PlanningDesk":
                        continue
                    key = target["stable_key"]
                    location_conditions: list[dict[str, Any]] = []
                    if not target["active_in_hierarchy"]:
                        for activation in self.rows("ui_item_access_activations"):
                            if activation["target_stable_key"] != key:
                                continue
                            for column, predicate in (
                                ("quest_stable_key", "quest_done"),
                                ("alternative_quest_stable_key", "quest_done"),
                                ("item_stable_key", "item_held"),
                            ):
                                if activation[column]:
                                    location_conditions.append(
                                        self.condition(
                                            "ui_access",
                                            predicate,
                                            activation[column],
                                            group_index=len(location_conditions),
                                            scope=key,
                                        )
                                    )
                        if not location_conditions:
                            location_conditions.append(self.condition("ui_access", "never", scope=key))
                    possible.append(self.location(target, key, "interaction", key, tuple(location_conditions)))
                locations = tuple(possible) or (asdict(ProvenanceLocation(_key("ui_unlocated", source), "unlocated")),)
            else:
                raise ValueError(f"Unsupported native item UI component {component!r}")
            if not item:
                self.exclude(origin, "empty_native_ui_slot")
                continue
            origins = [origin]
            if component == "PlanningTableUI":
                for location in locations:
                    if location["relation"] != "interaction":
                        continue
                    key = location["location_key"]
                    origins.append(self.origin("ui_item_access_targets", key))
                    origins.extend(
                        self.origin("ui_item_access_activations", activation["stable_key"])
                        for activation in self.rows("ui_item_access_activations")
                        if activation["target_stable_key"] == key
                    )
            observation = observations.get((component, slot))
            if observation is not None:
                origins.append(observation)
            consumed.update(origins)
            source_conditions: tuple[dict[str, Any], ...] = (
                self.condition("transfer", "route", value="normal_pointer_inventory_transfer"),
            )
            if component == "ReplenishTMOGHide":
                source_conditions += (
                    self.condition("replenishment", "source_replenishment", value="while_source_active"),
                )
            self.fact(
                "acquisition",
                "ui_grant",
                item,
                source,
                (source, slot),
                tuple(origins),
                quantity=quantity,
                mechanic=mechanic,
                variant_key=slot,
                player_access_state="verified_player"
                if observation is not None and not row["display_only"]
                else "unconfirmed_player",
                probability_basis="not_applicable",
                guarantee_scope="successful_ui_transfer",
                conditions=source_conditions,
                locations=locations,
            )
        for origin, reason in support.items():
            if origin not in consumed:
                self.exclude(origin, reason)

    def enumerate_smithing(self) -> None:
        facts = {(r["fact_id"], r["key"]): r["value"] for r in self.rows("code_facts")}
        if (
            facts.get(("smithing.upgrade_ids", "strings")) != "31377423,2298018,2265228"
            or facts.get(("smithing.planar_fuel", "ok")) != "true"
        ):
            raise ValueError("Missing native smithing route evidence")
        by_id = {str(r["id"]): r["stable_key"] for r in self.rows("items")}
        try:
            upgrade, removal, combining, fuel = (
                by_id[value] for value in ("31377423", "2298018", "2265228", "46289586")
            )
        except KeyError as error:
            raise ValueError(f"Missing native smithing item ID: {error.args[0]}") from error
        origins: tuple[InputIdentity, ...] = (
            self.origin("code_facts", "smithing.upgrade_ids", "strings"),
            self.origin("code_facts", "smithing.planar_fuel", "ok"),
        )
        origins += self.required_facts(
            "smithing.planar_input_quality",
            "smithing.planar_single_input",
            "smithing.planar_output_quality",
            "smithing.blessing_input_quality",
            "smithing.blessing_single_input",
            "smithing.blessing_outputs",
            "smithing.ascension_input_quality",
            "smithing.ascension_two_inputs",
            "smithing.ascension_equal_inputs",
            "smithing.ascension_output_quality",
            "smithing.fuel_flag",
            "smithing.single_fuel_amount",
        )
        recipes = {
            row["recipe_item_stable_key"]
            for row in self.rows("crafting_rewards")
            if row["reward_slot"] == 1
            and self.items[row["recipe_item_stable_key"]]["template"]
            and str(self.items[row["recipe_item_stable_key"]]["id"]) not in ("31377423", "2298018", "2265228")
        }
        for row in self.rows("items"):
            if not row["fuel_source"]:
                continue
            item = row["stable_key"]
            for target, role in (
                *((recipe, "forge_fuel") for recipe in sorted(recipes)),
                (removal, "blessing_removal_fuel"),
                (combining, "combining_fuel"),
            ):
                self.fact(
                    "use",
                    "smithing",
                    item,
                    target,
                    (item, target, role),
                    (*origins, self.origin("items", item)),
                    quantity=1,
                    mechanic=role,
                    conditions=(
                        self.condition(
                            "fuel_level",
                            "formula_operand",
                            value="fuel_level",
                            minimum=row["fuel_level"],
                            maximum=row["fuel_level"],
                            phase="mechanic_parameter",
                        ),
                    ),
                )
        for item, target, mechanic, primary in (
            (fuel, upgrade, "upgrade_material", (fuel, upgrade, "upgrade_material")),
            (removal, removal, "blessing_removal_material", (removal, "blessing_removal_material")),
            (combining, combining, "combine_quality", (combining, "combine_quality")),
        ):
            self.fact("use", "smithing", item, target, primary, origins, quantity=1, mechanic=mechanic)
        for row in self.rows("items"):
            item, slot = row["stable_key"], row["required_slot"]
            if slot in ("General", "Aura"):
                continue
            item_origins = (*origins, self.origin("items", item))
            self.fact(
                "use",
                "smithing",
                item,
                upgrade,
                (item, upgrade, "quality_upgrade"),
                item_origins,
                quantity=1,
                mechanic="quality_upgrade",
                conditions=(
                    self.condition("input_quality", "quality", value="blessed", phase="operation_input"),
                    self.condition("output_quality", "quality", value="divine", phase="operation_outcome"),
                ),
            )
            self.fact(
                "use",
                "smithing",
                item,
                removal,
                (item, removal, "remove_blessing"),
                item_origins,
                quantity=1,
                mechanic="remove_blessing",
                conditions=(
                    self.condition("input_quality", "quality", minimum=2, maximum=3, phase="operation_input"),
                    self.condition("output_quality", "quality", value="normal", phase="operation_outcome"),
                ),
            )
            if slot != "Charm":
                self.fact(
                    "use",
                    "smithing",
                    item,
                    combining,
                    (item, combining, "combine_matching"),
                    item_origins,
                    quantity=2,
                    mechanic="combine_matching",
                    conditions=(
                        self.condition("input_quality", "quality", minimum=1, maximum=1, phase="operation_input"),
                        self.condition(
                            "input_quality", "quality", group_index=1, minimum=11, maximum=14, phase="operation_input"
                        ),
                        self.condition(
                            "equal_quality", "formula_operand", value="matching_input_quality", phase="operation_input"
                        ),
                        self.condition(
                            "improvement",
                            "formula_operand",
                            value="normal_to_11_else_plus_1",
                            maximum=15,
                            phase="operation_outcome",
                        ),
                    ),
                )

    def enumerate_authored_equipment(self) -> None:
        sims = {row["stable_key"]: row for row in self.rows("authored_sims")}
        references: dict[str, list[InputIdentity]] = defaultdict(list)
        for row in self.rows("authored_sim_references"):
            references[row["authored_sim_stable_key"]].append(
                self.origin("authored_sim_references", row["source_component_key"], row["reference_index"])
            )
        populated: set[str] = set()
        for row in self.rows("authored_sim_equipment"):
            source, position = row["authored_sim_stable_key"], row["position"]
            origin = self.origin("authored_sim_equipment", source, position)
            if row["item_stable_key"] is None:
                self.exclude(origin, "empty_authored_seed_slot")
                continue
            if source not in sims:
                raise ValueError(f"Missing native authored simulation seed: {source}")
            populated.add(source)
            sim = sims[source]
            self.fact(
                "acquisition",
                "internal_equipment",
                row["item_stable_key"],
                source,
                ("authored_seed", source, position),
                (origin, self.origin("authored_sims", source), *references[source]),
                quantity=1,
                player_access_state="internal_only",
                variant_key=str(position),
                mechanic="authored_sim_seed",
                probability_basis="not_applicable",
                conditions=(
                    self.condition(
                        "seed_level",
                        "actor_level",
                        actor="sim",
                        minimum=sim["seed_level"],
                        maximum=sim["seed_level"],
                        phase="source_initialization",
                    ),
                    self.condition(
                        "seed_class",
                        "actor_class",
                        "class:" + sim["seed_class_name"].lower(),
                        actor="sim",
                        phase="source_initialization",
                    ),
                ),
            )
        for source in sims:
            origin = self.origin("authored_sims", source)
            if source not in populated:
                self.exclude(origin, "empty_authored_seed_configuration")
                for reference in references[source]:
                    self.exclude(reference, "empty_authored_seed_configuration")

    def enumerate_smithing_byproducts(self, raw: sqlite3.Connection) -> None:
        try:
            cursor = raw.execute("SELECT BindingKey,ItemStableKey,SourceComponentKey FROM NativeItemBindings")
        except sqlite3.OperationalError as error:
            raise ValueError("Smithing requires refreshed native item bindings") from error
        rows = cursor.fetchall()
        if len(rows) != 1 or rows[0][0] != "GameManager.PlanarShard" or not rows[0][2]:
            raise ValueError("Smithing requires one supported native PlanarShard binding")
        key, item, _component = rows[0]
        origin = self.origin("raw.NativeItemBindings", key)
        if item is None:
            self.exclude(origin, "empty_smithing_output_binding")
            return
        if item not in self.items:
            raise ValueError(f"Native smithing output references absent item: {item}")
        removal = next(row["stable_key"] for row in self.rows("items") if str(row["id"]) == "2298018")
        proof = self.required_facts(
            "smithing.blessing_outputs", "smithing.blessing_input_quality", "smithing.blessing_single_input"
        )
        outcome = self.fact(
            "acquisition",
            "crafting",
            item,
            removal,
            (removal, "blessing_removal_byproduct", item),
            (origin, self.origin("items", removal), *proof),
            quantity=1,
            probability_basis="not_applicable",
            mechanic="remove_blessing",
            variant_key="blessing_removal_byproduct",
            conditions=(self.condition("equipment_input", "quality", minimum=2, maximum=3, phase="operation_input"),),
        )
        for owner, (family, data) in self.expected.items():
            if family == "use" and data["mechanic"] in (
                "remove_blessing",
                "blessing_removal_material",
                "blessing_removal_fuel",
            ):
                data["outcome_key"] = outcome
                self.evidence.update((owner, relation, primary) for relation, primary in (origin, *proof))

    def enumerate_internal_equipment(self) -> None:
        facts = {(r["fact_id"], r["key"]): r["value"] for r in self.rows("code_facts")}
        required = (
            "sim.aura_equipment_slot",
            "sim.aura_equipment_added",
            "sim.generated_equipment_slot_gate",
            "sim.generated_equipment_nonweapon_gate",
            "sim.generated_equipment_assignment",
        )
        if any(facts.get((fact, "ok")) != "true" for fact in required):
            raise ValueError("Missing native internal equipment evidence")
        try:
            cap = int(facts["auction.sim_level_cap", "value"])
        except (KeyError, ValueError) as error:
            raise ValueError("Missing native simulated actor level cap") from error
        classes: dict[str, set[str]] = defaultdict(set)
        for row in self.rows("item_classes"):
            classes[row["item_stable_key"]].add(row["class_name"])
        for row in self.rows("items"):
            if (
                row["required_slot"] != "Aura"
                or row["sim_players_cant_get"]
                or not row["item_level"]
                or row["item_level"] <= 0
            ):
                continue
            item, level = row["stable_key"], row["item_level"]
            for scenario in ("normal", "rival"):
                eligible = []
                for actor in range(1, cap + 1):
                    lower = max(1, actor - 3)
                    ceiling = (45 if actor >= 35 else 37) if scenario == "rival" else 39
                    allowance = 6 if scenario == "rival" else 2 if actor > 10 else 1
                    if lower <= level <= min(ceiling, actor + allowance):
                        eligible.append(actor)
                if not eligible:
                    continue
                for class_name in sorted(classes[item]):
                    origins: tuple[InputIdentity, ...] = (
                        self.origin("items", item),
                        self.origin("item_classes", item, class_name),
                    )
                    origins += tuple(self.origin("code_facts", fact, "ok") for fact in required)
                    origins += (self.origin("code_facts", "auction.sim_level_cap", "value"),)
                    self.fact(
                        "acquisition",
                        "internal_equipment",
                        item,
                        "mechanic:simulated_equipment_generation",
                        (item, class_name, scenario),
                        origins,
                        quantity=1,
                        player_access_state="internal_only",
                        variant_key=_key("internal_gear", class_name, scenario),
                        mechanic="simulated_equipment_generation",
                        probability_basis="per_use",
                        conditions=(
                            self.condition("actor_class", "actor_class", "class:" + class_name.lower(), actor="sim"),
                            self.condition(
                                "actor_level", "actor_level", actor="sim", minimum=min(eligible), maximum=max(eligible)
                            ),
                            self.condition("route", "route", value=scenario),
                            self.condition("upgrade", "quality", value="improves_existing_equipment"),
                            self.condition("actor_access", "route", value="not_gm_upgrades_enabled_not_demo"),
                        ),
                    )

    def enumerate_raw_loot(self, raw: sqlite3.Connection, reviewed_unreachable: frozenset[str]) -> None:
        try:
            cursor = raw.execute("SELECT * FROM LootDrops")
        except sqlite3.OperationalError as error:
            raise ValueError("Item provenance requires refreshed native loot outcomes") from error
        columns = [column[0] for column in cursor.description or ()]
        if not {"LootTableStableKey", "CharacterStableKey", "ItemStableKey"}.issubset(columns):
            raise ValueError("Native loot coverage requires source-table outcome identities")
        native = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        try:
            source_flags = dict(raw.execute("SELECT StableKey,ComponentIsEnabled FROM LootTableSources").fetchall())
        except sqlite3.OperationalError as error:
            raise ValueError("Native loot coverage requires captured component enablement") from error
        if any(value not in (0, 1) for value in source_flags.values()):
            raise ValueError("Native loot component enablement must be an explicit boolean")
        hosts = {
            row[0]: dict(zip(("DestroyOnDeath", "DoNotLeaveCorpse", "IsSimPlayer"), row[1:], strict=True))
            for row in raw.execute("SELECT StableKey, DestroyOnDeath, DoNotLeaveCorpse, IsSimPlayer FROM Characters")
        }
        items = {row["stable_key"] for row in self.rows("items")}
        clean = {(row["character_stable_key"], row["item_stable_key"]): row for row in self.rows("loot_drops")}
        owners: dict[str, set[str]] = defaultdict(set)
        for owner, relation, primary in self.evidence:
            if relation == "loot_drops":
                owners[primary].add(owner)
        seen: set[tuple[str, str]] = set()
        native_seen: set[tuple[str, str]] = set()
        for row in native:
            copy, item = row["CharacterStableKey"], row["ItemStableKey"]
            identity = copy, item
            native_identity = row["LootTableStableKey"], item
            if native_identity in native_seen:
                raise ValueError(f"Duplicate raw loot input: {native_identity!r}")
            native_seen.add(native_identity)
            seen.add(identity)
            origin = self.origin("raw.LootDrops", *native_identity)
            host = hosts.get(copy)
            if host is None:
                reason = "loot_host_missing"
            elif host["DestroyOnDeath"]:
                reason = "loot_host_destroy_on_death"
            elif host["DoNotLeaveCorpse"]:
                reason = "loot_host_do_not_leave_corpse"
            elif host["IsSimPlayer"]:
                reason = "non_player_host"
            elif copy in reviewed_unreachable:
                reason = "reviewed_unexecuted_loot"
            else:
                reason = None
            if identity in clean:
                if clean[identity]["loot_table_stable_key"] != row["LootTableStableKey"]:
                    raise ValueError(f"Native loot source binding changed: {identity!r}")
                if row["LootTableStableKey"] not in source_flags:
                    raise ValueError(f"Native loot outcome lacks its actual source binding: {identity!r}")
                if clean[identity]["source_component_is_enabled"] != source_flags[row["LootTableStableKey"]]:
                    raise ValueError(f"Native loot component enablement differs from clean source: {identity!r}")
                if reason is not None:
                    raise ValueError(f"Ineligible raw loot host retained as a player source: {identity!r} ({reason})")
                for native_column, clean_column in (
                    ("DropProbability", "drop_probability"),
                    ("ExpectedPerKill", "expected_per_kill"),
                    ("DropCountDistribution", "drop_count_distribution"),
                    ("IsActual", "is_actual"),
                    ("IsGuaranteed", "is_guaranteed"),
                    ("IsCommon", "is_common"),
                    ("IsCommonWorldItem", "is_common_world_item"),
                    ("IsUncommon", "is_uncommon"),
                    ("IsRare", "is_rare"),
                    ("IsLegendary", "is_legendary"),
                    ("IsUltraRare", "is_ultra_rare"),
                ):
                    if row[native_column] != clean[identity][clean_column]:
                        raise ValueError(f"Native loot dimension changed: {identity!r} {native_column}")
                clean_key = _json(identity)
                if clean_key in owners:
                    self.evidence.update((owner, *origin) for owner in owners[clean_key])
                else:
                    self.exclude(origin, self.excluded["loot_drops", clean_key])
            elif item not in items:
                raise ValueError(f"Raw loot references absent native item: {identity!r}")
            elif reason is None:
                raise ValueError(f"Unexplained serialized loot exclusion: {identity!r}")
            else:
                self.fact(
                    "acquisition",
                    "character_drop",
                    item,
                    self.groups.get(copy, copy),
                    ("raw_excluded", row["LootTableStableKey"], item),
                    (origin,),
                    chance=row["DropProbability"],
                    player_access_state="non_acquirable",
                    source_copy_stable_key=copy,
                    source_group_key=self.groups.get(copy),
                    probability_basis="per_kill",
                    expected_quantity=row.get("ExpectedPerKill"),
                    count_distribution=row.get("DropCountDistribution"),
                    conditions=(self.condition("loot_host", "never", value=reason),),
                )
        if clean.keys() - seen:
            raise ValueError(f"Clean loot has no native input: {sorted(clean.keys() - seen)!r}")

    def enumerate_native_inputs(self, raw: sqlite3.Connection) -> None:
        keys: dict[str, tuple[str, ...]] = {
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
        required = {
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
            "MiningNodeItems": ("DropChance",),
            "MiningNodePoolSlots": ("ItemStableKey",),
            "MiningFallbackItems": ("ItemStableKey",),
            "WaterFishables": ("ItemStableKey",),
            "ItemDrops": ("DropProbability",),
            "ItemDropPools": ("SourceComponentKey", "SlotCount"),
            "ItemDropPoolSlots": ("ItemStableKey",),
            "Characters": ("StableKey", "DestroyOnDeath", "DoNotLeaveCorpse", "IsSimPlayer"),
        }
        native: dict[str, list[dict[str, Any]]] = {}
        indexed: dict[str, dict[tuple[object, ...], dict[str, Any]]] = {}
        for table in (*keys, "Characters"):
            try:
                cursor = raw.execute(f'SELECT * FROM "{table}"')
            except sqlite3.OperationalError as error:
                raise ValueError(f"Native item coverage requires refreshed table {table}") from error
            columns = [column[0] for column in cursor.description or ()]
            if (set(keys.get(table, ())) | set(required.get(table, ()))) - set(columns):
                raise ValueError(f"Native item coverage lacks identity columns: {table}")
            native[table] = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
            indexed[table] = {}
            for row in native[table]:
                if table == "Characters":
                    continue
                primary = tuple(row[column] for column in keys[table])
                if primary in indexed[table]:
                    raise ValueError(f"Duplicate native item identity: {table}{primary!r}")
                indexed[table][primary] = row
                self.origin("raw." + table, *primary)

        def require(table: str, *primary: object) -> dict[str, Any]:
            if primary not in indexed[table]:
                raise ValueError(f"Missing native item identity: {table}{primary!r}")
            return indexed[table][primary]

        def selected(table: str, column: str, value: object) -> list[dict[str, Any]]:
            return [row for row in native[table] if row[column] == value]

        def positions(rows: list[dict[str, Any]], count: object, label: str) -> None:
            if not isinstance(count, int) or count < 0 or sorted(row["Position"] for row in rows) != list(range(count)):
                raise ValueError(f"Native pool positions do not match serialized count: {label}")

        def origin_for(table: str, row: Mapping[str, Any]) -> InputIdentity:
            return "raw." + table, _json(tuple(row[column] for column in keys[table]))

        hosts = {row["StableKey"]: row for row in native["Characters"]}
        sources_with_outcomes = {row["LootTableStableKey"] for row in native["LootDrops"]}
        host_reasons: dict[object, str] = {}
        for source in native["LootTableSources"]:
            if source["ComponentIsEnabled"] not in (0, 1):
                raise ValueError("Native loot component enablement must be an explicit boolean")
            host = hosts.get(source["CharacterStableKey"])
            if source["MiningNodeStableKey"] is not None:
                if source["CharacterStableKey"] is not None:
                    raise ValueError("Native loot source links both world and mining hosts")
                require("MiningNodes", source["MiningNodeStableKey"])
                if source["StableKey"] in sources_with_outcomes or any(
                    row["ItemStableKey"] is not None
                    for row in native["LootTablePoolSlots"]
                    if row["LootTableStableKey"] == source["StableKey"]
                ):
                    raise ValueError("Native mining loot source has world item grants")
                reason = "non_world_mining_host"
            elif host is None:
                reason = "loot_host_missing"
            elif host["DestroyOnDeath"]:
                reason = "loot_host_destroy_on_death"
            elif host["DoNotLeaveCorpse"]:
                reason = "loot_host_do_not_leave_corpse"
            elif host["IsSimPlayer"]:
                reason = "non_player_host"
            elif source["StableKey"] not in sources_with_outcomes:
                reason = "empty_native_loot_configuration"
            elif source["CharacterStableKey"] in self.encountered and not (
                self.characters[source["CharacterStableKey"]]["can_be_damaged"]
                or self.characters[source["CharacterStableKey"]]["treasure_chest"]
            ):
                reason = "loot_host_undamageable"
            else:
                reason = "unencountered_copy"
            host_reasons[source["StableKey"]] = reason
        flags = {row["Name"]: row["Value"] for row in native["SpecialWorldDropFlags"]}
        gated = {"Masks": "DropMasks", "MoloraiMask": "DropMasks", "Empty2": "DemoBuild"}
        maps_have_items = any(
            row["Pool"] == "Maps" and row["Position"] < 4 and row["ItemStableKey"] is not None
            for row in native["SpecialWorldDropItems"]
        )
        productive_waters = {
            row["WaterStableKey"]
            for row in native["WaterFishables"]
            if row["ItemStableKey"] is not None or maps_have_items
        }
        productive_pools = {
            row["PoolStableKey"] for row in native["ItemDropPoolSlots"] if row["ItemStableKey"] is not None
        }
        fallback_needed = any(
            row["Pool"] == "guarantee" and row["ItemStableKey"] is None for row in native["MiningNodePoolSlots"]
        )
        defaults: dict[InputIdentity, str] = {}
        all_origins: set[InputIdentity] = set()
        for table in keys:
            for row in native[table]:
                all_origins.add(origin_for(table, row))
                exclusion_reason: str | None = None
                if table in ("LootDrops", "LootTableSources", "LootTablePoolSlots"):
                    source = require(
                        "LootTableSources",
                        row["StableKey"] if table == "LootTableSources" else row["LootTableStableKey"],
                    )
                    exclusion_reason = host_reasons[source["StableKey"]]
                    if table == "LootDrops" and row["CharacterStableKey"] != source["CharacterStableKey"]:
                        raise ValueError("Native loot outcome and component host bindings differ")
                elif table == "CommonWorldItems":
                    exclusion_reason = "unused_common_world_pool"
                elif table == "SpecialWorldDropItems" and row["Pool"] in gated:
                    flag = gated[row["Pool"]]
                    require("SpecialWorldDropFlags", flag)
                    if not flags[flag]:
                        exclusion_reason = "native_world_drop_gate_disabled"
                elif table == "SpecialWorldDropFlags":
                    if not row["Value"]:
                        exclusion_reason = "native_world_drop_gate_disabled"
                    elif not any(
                        gated.get(slot["Pool"]) == row["Name"] and slot["ItemStableKey"] is not None
                        for slot in native["SpecialWorldDropItems"]
                    ):
                        exclusion_reason = "empty_native_world_drop_configuration"
                elif table == "MiningFallbackItems" and not fallback_needed:
                    exclusion_reason = "unused_mining_fallback"
                elif table == "Waters" and row["StableKey"] not in productive_waters:
                    exclusion_reason = "empty_native_fishing_configuration"
                elif table == "ItemDropPools" and row["PoolStableKey"] not in productive_pools:
                    exclusion_reason = "empty_native_item_drop_configuration"
                if exclusion_reason is None and "ItemStableKey" in row and row["ItemStableKey"] is None:
                    exclusion_reason = "empty_native_pool_slot"
                if exclusion_reason is not None:
                    defaults[origin_for(table, row)] = exclusion_reason

        def add(owner: str, table: str, rows: list[dict[str, Any]]) -> None:
            self.evidence.update((owner, *origin_for(table, row)) for row in rows)

        def maps() -> list[dict[str, Any]]:
            rows = [row for row in native["SpecialWorldDropItems"] if row["Pool"] == "Maps" and row["Position"] < 4]
            positions(rows, 4, "first four Maps slots")
            return rows

        loot_pools = {
            "UltraRareDrop": "UltraRareDropCount",
            "LegendaryDrop": "LegendaryDropCount",
            "RareDrop": "RareDropCount",
            "UncommonDrop": "UncommonDropCount",
            "CommonDrop": "CommonDropCount",
            "GuaranteeOneDrop": "GuaranteeOneDropCount",
            "ActualDrops": "ActualDropsCount",
        }
        clean_loot = {(row["character_stable_key"], row["item_stable_key"]): row for row in self.rows("loot_drops")}
        clean_mining = {
            (row["mining_node_stable_key"], row["item_stable_key"]): row for row in self.rows("mining_node_items")
        }
        clean_drops = {
            (row["source_item_stable_key"], row["dropped_item_stable_key"], row["pool_stable_key"]): row
            for row in self.rows("item_drops")
        }
        for owner, relation, encoded in tuple(self.evidence):
            primary = tuple(json.loads(encoded))
            if relation in ("loot_drops", "raw.LootDrops"):
                if relation == "loot_drops":
                    outcome = require("LootDrops", clean_loot[primary]["loot_table_stable_key"], primary[1])
                    if outcome["CharacterStableKey"] != primary[0]:
                        raise ValueError("Native selected loot host differs from clean identity")
                else:
                    outcome = require("LootDrops", *primary)
                source = require("LootTableSources", outcome["LootTableStableKey"])
                slots = selected("LootTablePoolSlots", "LootTableStableKey", source["StableKey"])
                if {row["Pool"] for row in slots} - loot_pools.keys():
                    raise ValueError("Unknown native loot pool")
                for pool, column in loot_pools.items():
                    positions([row for row in slots if row["Pool"] == pool], source[column], pool)
                add(owner, "LootDrops", [outcome])
                add(owner, "LootTableSources", [source])
                add(owner, "LootTablePoolSlots", slots)
                if source["CommonDropCount"] > 0:
                    common = native["CommonWorldItems"]
                    if not common:
                        raise ValueError("Missing native common substitution slots")
                    positions(common, len(common), "CommonWorldItems")
                    add(owner, "CommonWorldItems", common)
            elif relation == "mining_node_items":
                outcome = require("MiningNodeItems", *primary)
                if outcome["DropChance"] != clean_mining[primary]["drop_chance"]:
                    raise ValueError("Native mining probability differs from clean outcome")
                source = require("MiningNodes", primary[0])
                slots = selected("MiningNodePoolSlots", "MiningNodeStableKey", primary[0])
                if {row["Pool"] for row in slots} - {"guarantee", "Common", "Rare", "Legend"}:
                    raise ValueError("Unknown native mining pool")
                guarantee = [row for row in slots if row["Pool"] == "guarantee"]
                positions(guarantee, 1, "mining guarantee")
                for pool in ("Common", "Rare", "Legend"):
                    positions([row for row in slots if row["Pool"] == pool], source[pool + "Count"], pool)
                add(owner, "MiningNodeItems", [outcome])
                add(owner, "MiningNodes", [source])
                add(owner, "MiningNodePoolSlots", slots)
                if guarantee[0]["ItemStableKey"] is None:
                    fallback = require("MiningFallbackItems", "GameManager.GuaranteeMine")
                    if fallback["ItemStableKey"] is None:
                        raise ValueError("Missing effective native mining guarantee")
                    add(owner, "MiningFallbackItems", [fallback])
            elif relation == "water_fishables":
                water, period, item = primary
                source = require("Waters", water)
                slots = selected("WaterFishables", "WaterStableKey", water)
                if period not in ("DayFishable", "NightFishable"):
                    raise ValueError("Unknown native fishing period")
                period_slots = [row for row in slots if row["Type"] == period]
                if period == "NightFishable" and not period_slots:
                    period_slots = [row for row in slots if row["Type"] == "DayFishable"]
                if not period_slots:
                    raise ValueError("Native fishing has no effective local pool")
                positions(period_slots, len(period_slots), "local fishing")
                global_slots = maps()
                if not any(row["ItemStableKey"] == item for row in (*period_slots, *global_slots)):
                    raise ValueError("Native fishing item has no contributing slot")
                add(owner, "Waters", [source])
                add(owner, "WaterFishables", period_slots)
                add(owner, "SpecialWorldDropItems", global_slots)
            elif relation == "fishing_bonus_catches":
                slots = maps()
                if not any(row["ItemStableKey"] == primary[0] for row in slots):
                    raise ValueError("Native fishing bonus has no contributing slot")
                add(owner, "SpecialWorldDropItems", slots)
            elif relation == "special_world_drops":
                item, pool = primary
                slots = selected("SpecialWorldDropItems", "Pool", pool)
                if not any(row["ItemStableKey"] == item for row in slots):
                    raise ValueError("Native world drop has no contributing slot")
                positions(slots, len(slots), "special world drop")
                add(owner, "SpecialWorldDropItems", slots)
                if pool in gated:
                    flag_row = require("SpecialWorldDropFlags", gated[pool])
                    if not flag_row["Value"]:
                        raise ValueError("Native world drop gate is disabled")
                    add(owner, "SpecialWorldDropFlags", [flag_row])
            elif relation == "item_drops":
                outcome = require("ItemDrops", *primary)
                source = require("ItemDropPools", primary[2])
                if not source["SourceComponentKey"]:
                    raise ValueError("Missing native item-draw component binding")
                slots = selected("ItemDropPoolSlots", "PoolStableKey", primary[2])
                positions(slots, source["SlotCount"], "item draw")
                if not slots or not any(row["ItemStableKey"] == primary[1] for row in slots):
                    raise ValueError("Native item draw has no contributing slot")
                probability = sum(row["ItemStableKey"] == primary[1] for row in slots) / len(slots) * 100.0
                if probability != outcome["DropProbability"] or probability != clean_drops[primary]["drop_probability"]:
                    raise ValueError("Native item draw probability differs from slot weights")
                add(owner, "ItemDrops", [outcome])
                add(owner, "ItemDropPools", [source])
                add(owner, "ItemDropPoolSlots", slots)
        consumed = {(relation, primary) for _, relation, primary in self.evidence}
        for origin, reason in defaults.items():
            if origin not in consumed:
                self.exclude(origin, reason)
        missing = all_origins - consumed - defaults.keys()
        if missing:
            raise ValueError(f"Unconsumed mandatory native item inputs: {sorted(missing)!r}")

    def enumerate_direct_native_inputs(self, raw: sqlite3.Connection) -> None:
        specs: tuple[tuple[str, str, tuple[str, ...], dict[str, str], bool], ...] = (
            (
                "Items",
                "items",
                ("StableKey",),
                {
                    "StableKey": "stable_key",
                    "Id": "id",
                    "Unique": "is_unique",
                    "RequiredSlot": "required_slot",
                    "Template": "template",
                    "FuelSource": "fuel_source",
                    "FuelLevel": "fuel_level",
                    "ItemLevel": "item_level",
                    "SimPlayersCantGet": "sim_players_cant_get",
                    "ItemEffectOnClickStableKey": "item_effect_on_click_stable_key",
                },
                False,
            ),
            (
                "ItemClasses",
                "item_classes",
                ("ItemStableKey", "ClassName"),
                {"ItemStableKey": "item_stable_key", "ClassName": "class_name"},
                False,
            ),
            ("Spells", "spells", ("StableKey",), {"StableKey": "stable_key", "SpellName": "spell_name"}, False),
            (
                "CraftingRecipes",
                "crafting_recipes",
                ("RecipeItemStableKey", "MaterialSlot"),
                {
                    "RecipeItemStableKey": "recipe_item_stable_key",
                    "MaterialSlot": "material_slot",
                    "MaterialItemStableKey": "material_item_stable_key",
                    "MaterialQuantity": "material_quantity",
                },
                False,
            ),
            (
                "CraftingRewards",
                "crafting_rewards",
                ("RecipeItemStableKey", "RewardSlot"),
                {
                    "RecipeItemStableKey": "recipe_item_stable_key",
                    "RewardSlot": "reward_slot",
                    "RewardItemStableKey": "reward_item_stable_key",
                    "RewardQuantity": "reward_quantity",
                },
                False,
            ),
            (
                "ClassStartingItems",
                "class_starting_items",
                ("ClassName", "SortOrder"),
                {"ClassName": "class_name", "SortOrder": "sort_order", "ItemStableKey": "item_stable_key"},
                False,
            ),
            (
                "ItemBags",
                "item_bags",
                ("StableKey",),
                {
                    "StableKey": "stable_key",
                    "ItemStableKey": "item_stable_key",
                    "Scene": "scene",
                    "X": "x",
                    "Y": "y",
                    "Z": "z",
                    "Respawns": "respawns",
                    "RespawnTimer": "respawn_timer",
                },
                False,
            ),
            (
                "CharacterVendorItems",
                "character_vendor_items",
                ("CharacterStableKey", "ItemSlot"),
                {
                    "CharacterStableKey": "character_stable_key",
                    "ItemSlot": "item_slot",
                    "ItemStableKey": "item_stable_key",
                },
                True,
            ),
            (
                "CharacterVendorQuestUnlocks",
                "character_vendor_quest_unlocks",
                ("CharacterStableKey", "QuestSlot"),
                {
                    "CharacterStableKey": "character_stable_key",
                    "QuestSlot": "quest_slot",
                    "QuestStableKey": "quest_stable_key",
                    "QuestVariantResourceName": "quest_variant_resource_name",
                },
                True,
            ),
            (
                "CharacterDialogs",
                "character_dialogs",
                ("CharacterStableKey", "DialogIndex"),
                {
                    "CharacterStableKey": "character_stable_key",
                    "DialogIndex": "dialog_index",
                    "GiveItemStableKey": "give_item_stable_key",
                    "RequiredQuestStableKey": "required_quest_stable_key",
                    "AssignQuestStableKey": "assign_quest_stable_key",
                    "AssignQuestVariantResourceName": "assign_quest_variant_resource_name",
                    "CompleteQuestStableKey": "complete_quest_stable_key",
                },
                True,
            ),
            (
                "CharacterQuestManagerQuests",
                "character_quest_manager_quests",
                ("CharacterStableKey", "QuestSlot"),
                {
                    "CharacterStableKey": "character_stable_key",
                    "QuestSlot": "quest_slot",
                    "QuestStableKey": "quest_stable_key",
                    "QuestVariantResourceName": "quest_variant_resource_name",
                },
                True,
            ),
            (
                "QuestVariants",
                "quest_variants",
                ("ResourceName",),
                {
                    "ResourceName": "resource_name",
                    "QuestStableKey": "quest_stable_key",
                    "Repeatable": "repeatable",
                    "ItemOnCompleteStableKey": "item_on_complete_stable_key",
                    "UnlockItemForVendorStableKey": "unlock_item_for_vendor_stable_key",
                },
                False,
            ),
            (
                "QuestRequiredItems",
                "quest_required_items",
                ("QuestVariantResourceName", "RequiredSlot"),
                {
                    "QuestVariantResourceName": "quest_variant_resource_name",
                    "RequiredSlot": "required_slot",
                    "ItemStableKey": "item_stable_key",
                    "Quantity": "quantity",
                },
                False,
            ),
            (
                "AuthoredSims",
                "authored_sims",
                ("StableKey",),
                {
                    "StableKey": "stable_key",
                    "PrefabGuid": "prefab_guid",
                    "PrefabLocalId": "prefab_local_id",
                    "PrefabPath": "prefab_path",
                    "ObjectName": "object_name",
                    "RawCharacterStableKey": "raw_character_stable_key",
                    "NPCName": "npc_name",
                    "SeedClassName": "seed_class_name",
                    "SeedLevel": "seed_level",
                    "SeedSkillLevel": "seed_skill_level",
                    "SeedIsMale": "seed_is_male",
                    "SeedHairName": "seed_hair_name",
                    "SeedHairColor": "seed_hair_color",
                    "SeedSkinColor": "seed_skin_color",
                    "IsGMCharacter": "is_gm_character",
                    "Rival": "rival",
                },
                False,
            ),
            (
                "AuthoredSimReferences",
                "authored_sim_references",
                ("SourceComponentKey", "ReferenceIndex"),
                {
                    "SourceComponentKey": "source_component_key",
                    "ReferenceIndex": "reference_index",
                    "SourceScene": "source_scene",
                    "SourceScenePath": "source_scene_path",
                    "AuthoredSimStableKey": "authored_sim_stable_key",
                },
                False,
            ),
            (
                "AuthoredSimEquipment",
                "authored_sim_equipment",
                ("AuthoredSimStableKey", "Position"),
                {
                    "AuthoredSimStableKey": "authored_sim_stable_key",
                    "Position": "position",
                    "ItemStableKey": "item_stable_key",
                },
                False,
            ),
            (
                "TreasureLocations",
                "treasure_locations",
                ("StableKey",),
                {"StableKey": "stable_key", "Scene": "scene", "X": "x", "Y": "y", "Z": "z"},
                False,
            ),
            (
                "TreasureHunting",
                "treasure_hunting",
                ("ZoneName",),
                {
                    "ZoneName": "zone_name",
                    "ZoneDisplayName": "zone_display_name",
                    "IsPickableAlways": "is_pickable_always",
                    "IsPickableGreater20": "is_pickable_greater_20",
                    "IsPickableGreater30": "is_pickable_greater_30",
                },
                False,
            ),
        )
        present = {row[0] for row in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        hosts = {row[0]: row[1] for row in raw.execute("SELECT StableKey,IsSimPlayer FROM Characters")}
        quests = {row["stable_key"] for row in self.rows("quests")}
        variants = {row["resource_name"] for row in self.rows("quest_variants")}
        audited: set[str] = set()
        raw_records: dict[str, list[dict[str, Any]]] = {}
        for native_table, clean_table, primary_columns, columns, world_character in specs:
            if native_table not in present:
                self.unsupported_native_tables.append(native_table)
                continue
            cursor = raw.execute(f'SELECT * FROM "{native_table}"')
            native_columns = [column[0] for column in cursor.description or ()]
            missing_columns = set(columns) - set(native_columns)
            if missing_columns:
                self.unsupported_native_tables.append(f"{native_table} missing {','.join(sorted(missing_columns))}")
                continue
            rows = [dict(zip(native_columns, row, strict=True)) for row in cursor.fetchall()]
            clean = {tuple(row[columns[column]] for column in primary_columns): row for row in self.rows(clean_table)}
            eligible: set[tuple[object, ...]] = set()
            seen: set[tuple[object, ...]] = set()
            for row in rows:
                primary = tuple(row[column] for column in primary_columns)
                if primary in seen:
                    raise ValueError(f"Duplicate direct native input: {native_table}{primary!r}")
                seen.add(primary)
                for column in (
                    "RecipeItemStableKey",
                    "MaterialItemStableKey",
                    "RewardItemStableKey",
                    "ItemStableKey",
                    "GiveItemStableKey",
                    "ItemOnCompleteStableKey",
                    "UnlockItemForVendorStableKey",
                ):
                    if column in row and row[column] is not None and row[column] not in self.items:
                        raise ValueError(
                            f"Direct native input references an unmapped item: {native_table}{primary!r} {column}"
                        )
                for column in (
                    "QuestStableKey",
                    "RequiredQuestStableKey",
                    "AssignQuestStableKey",
                    "CompleteQuestStableKey",
                ):
                    if column in row and row[column] is not None and row[column] not in quests:
                        raise ValueError(
                            f"Direct native input references an unmapped quest: {native_table}{primary!r} {column}"
                        )
                for column in ("QuestVariantResourceName", "AssignQuestVariantResourceName"):
                    if column in row and row[column] is not None and row[column] not in variants:
                        raise ValueError(
                            f"Direct native input references an unmapped quest resource: {native_table}{primary!r}"
                        )
                if world_character:
                    source = row["CharacterStableKey"]
                    if source not in hosts:
                        raise ValueError(f"Direct native input has no native character: {native_table}{primary!r}")
                    if hosts[source] == 1:
                        if source in self.characters or primary in clean:
                            raise ValueError(
                                f"Non-world native character leaked into world inputs: {native_table}{primary!r}"
                            )
                        self.direct_exclusions.append(
                            {
                                "relation": "raw." + native_table,
                                "primary_key": _json(primary),
                                "reason": "non_world_character_input",
                            }
                        )
                        continue
                    if source not in self.characters:
                        raise ValueError(
                            f"Direct native input has no mapped world character: {native_table}{primary!r}"
                        )
                if native_table == "AuthoredSims" and hosts.get(row["RawCharacterStableKey"]) != 1:
                    raise ValueError(f"Authored seed has no native simulated-player character: {primary!r}")
                eligible.add(primary)
                if primary not in clean:
                    raise ValueError(f"Missing clean identity for direct native input: {native_table}{primary!r}")
                for source_column, target_column in columns.items():
                    if row[source_column] != clean[primary][target_column]:
                        raise ValueError(f"Direct native dimension differs: {native_table}{primary!r} {source_column}")
            if clean.keys() != eligible:
                raise ValueError(
                    f"Clean identities have no direct native inputs: {clean_table}{sorted(clean.keys() - eligible)!r}"
                )
            self.direct_counts["raw." + native_table] = len(rows)
            audited.add(native_table)
            raw_records[native_table] = rows
        if {"Items", "Spells"}.issubset(audited):
            facts = {(row["fact_id"], row["key"]): row["value"] for row in self.rows("code_facts")}
            spell_names = {row["StableKey"]: row["SpellName"] for row in raw_records["Spells"]}
            if any(
                row["ItemEffectOnClickStableKey"] is not None and row["ItemEffectOnClickStableKey"] not in spell_names
                for row in raw_records["Items"]
            ):
                raise ValueError("Native item click references an uncaptured spell")
            literal = {key: value for (fact, key), value in facts.items() if fact == "item.offering_stone_grant"}
            if (
                set(literal) != {"spell_name", "created_item_id", "quantity"}
                or not all(isinstance(value, str) and value for value in literal.values())
                or int(literal["quantity"]) <= 0
            ):
                raise ValueError("Native literal grant coverage requires extracted switch operands")
            targets = [row["StableKey"] for row in raw_records["Items"] if str(row["Id"]) == literal["created_item_id"]]
            if len(targets) != 1:
                raise ValueError("Native literal grant requires one actual created-item identity")
            literal_grants = {
                (row["StableKey"], targets[0]): {
                    "source_item_stable_key": row["StableKey"],
                    "spell_stable_key": row["ItemEffectOnClickStableKey"],
                    "created_item_stable_key": targets[0],
                    "grant_fact_id": "item.offering_stone_grant",
                    "quantity": int(literal["quantity"]),
                }
                for row in raw_records["Items"]
                if spell_names.get(row["ItemEffectOnClickStableKey"]) == literal["spell_name"]
            }
            actual_grants = {
                (row["source_item_stable_key"], row["created_item_stable_key"]): row
                for row in self.rows("spell_created_items")
            }
            if actual_grants != literal_grants:
                raise ValueError("Native literal click grants differ from clean spell-created items")
            self.direct_counts["derived.spell_created_items"] = len(literal_grants)
            pool_grant = {key: value for (fact, key), value in facts.items() if fact == "item.fossil_pool_grant"}
            if (
                set(pool_grant) != {"spell_name", "quantity", "pool", "rolls"}
                or not all(isinstance(value, str) and value for value in pool_grant.values())
                or pool_grant["quantity"] != "1"
                or pool_grant["rolls"] != "1"
                or not pool_grant["pool"].startswith("GameData.")
            ):
                raise ValueError("Native pool grant coverage requires extracted single-draw operands")
            pool_key = pool_grant["pool"].removeprefix("GameData.")
            pool_cursor = raw.execute("SELECT * FROM ItemDropPools WHERE PoolStableKey=?", (pool_key,))
            pool_columns = [column[0] for column in pool_cursor.description or ()]
            pools = [dict(zip(pool_columns, row, strict=True)) for row in pool_cursor.fetchall()]
            if len(pools) != 1:
                raise ValueError("Native pool click grant lacks its actual singleton pool binding")
            slots = raw.execute(
                "SELECT Position,ItemStableKey FROM ItemDropPoolSlots WHERE PoolStableKey=?", (pool_key,)
            ).fetchall()
            if sorted(row[0] for row in slots) != list(range(pools[0]["SlotCount"])) or not slots:
                raise ValueError("Native pool click grant lacks complete draw positions")
            weights = Counter(row[1] for row in slots if row[1] is not None)
            expected_drops = {
                (row["StableKey"], item, pool_key): {
                    "SourceItemStableKey": row["StableKey"],
                    "DroppedItemStableKey": item,
                    "PoolStableKey": pool_key,
                    "DropProbability": count / len(slots) * 100.0,
                    "IsGuaranteed": 1,
                }
                for row in raw_records["Items"]
                if spell_names.get(row["ItemEffectOnClickStableKey"]) == pool_grant["spell_name"]
                for item, count in weights.items()
            }
            drop_cursor = raw.execute("SELECT * FROM ItemDrops")
            drop_columns = [column[0] for column in drop_cursor.description or ()]
            native_drops = {
                (row["SourceItemStableKey"], row["DroppedItemStableKey"], row["PoolStableKey"]): row
                for row in (dict(zip(drop_columns, values, strict=True)) for values in drop_cursor.fetchall())
            }
            if native_drops != expected_drops:
                raise ValueError("Native click sources and slot weights differ from native item-drop outcomes")
            clean_drops = {
                (row["source_item_stable_key"], row["dropped_item_stable_key"], row["pool_stable_key"]): (
                    row["drop_probability"],
                    row["is_guaranteed"],
                )
                for row in self.rows("item_drops")
            }
            if clean_drops != {
                key: (row["DropProbability"], row["IsGuaranteed"]) for key, row in expected_drops.items()
            }:
                raise ValueError("Native pool click grants differ from clean item-drop outcomes")
            self.direct_counts["derived.item_drops"] = len(expected_drops)
        if {"TreasureLocations", "TreasureHunting"}.issubset(audited):
            facts = {(row["fact_id"], row["key"]): row["value"] for row in self.rows("code_facts")}
            if (
                facts.get(("treasure.zone_pool_by_level", "ok")) != "true"
                or facts.get(("treasure.chest_tier_by_level", "ok")) != "true"
                or facts.get(("player.level_cap", "ok")) != "true"
            ):
                raise ValueError("Treasure placement coverage requires shipped chest and zone rules")
            cap = 35
            hunting = {row["zone_name"]: row for row in self.rows("treasure_hunting")}
            expected: dict[tuple[str, str], dict[str, object]] = {}
            for site in self.rows("treasure_locations"):
                if site["scene"] not in hunting:
                    continue
                zone = hunting[site["scene"]]
                minimum = (
                    1
                    if zone["is_pickable_always"]
                    else 21
                    if zone["is_pickable_greater_20"]
                    else 31
                    if zone["is_pickable_greater_30"]
                    else None
                )
                if minimum != zone["min_reading_level"]:
                    raise ValueError("Native treasure reading level differs from clean zone")
                if minimum is None:
                    continue
                for chest, low, high in (
                    ("character:treasurechest 0-10 1", 0, 10),
                    ("character:treasurechest 10-20 1", 10, 20),
                    ("character:treasurechest 20-30 1", 20, 30),
                    ("character:treasurechest 30-35", 30, 999),
                ):
                    player_low, player_high = max(low, minimum), min(high - 1, cap)
                    if player_low > player_high:
                        continue
                    if chest not in self.characters or chest not in hosts or hosts[chest] == 1:
                        raise ValueError(f"Native treasure chest has no mapped character: {chest}")
                    expected[chest, site["stable_key"]] = {
                        "chest_character_stable_key": chest,
                        "treasure_location_stable_key": site["stable_key"],
                        "level_min": low,
                        "level_max": high,
                        "player_level_min": player_low,
                        "player_level_max": player_high,
                        "scene": site["scene"],
                        "x": site["x"],
                        "y": site["y"],
                        "z": site["z"],
                    }
            actual = {
                (row["chest_character_stable_key"], row["treasure_location_stable_key"]): row
                for row in self.rows("treasure_chest_possible_spawns")
            }
            if actual != expected:
                raise ValueError("Native treasure locations and tiers differ from clean possible chest placements")

    def enumerate_encounter_inputs(self) -> None:
        keys = {
            "encounter_placements": ("encounter_key", "member_spawn_stable_key"),
            "encounter_conditions": ("encounter_key", "state_scope", "state_key"),
            "encounter_completions": ("encounter_key", "event_kind", "state_scope", "state_key"),
            "encounter_event_conditions": ("encounter_key", "event_kind", "state_scope", "state_key"),
        }
        placements = self.rows("encounter_placements")
        spawned = {
            row["spawn_point_stable_key"] for row in self.rows("character_spawns") if row["spawn_point_stable_key"]
        }
        contexts: dict[str, list[InputIdentity]] = defaultdict(list)
        members: dict[str, set[str]] = defaultdict(set)
        for row in placements:
            if row["member_spawn_stable_key"] not in spawned or row["root_spawn_stable_key"] not in spawned:
                raise ValueError("Encounter context has no actual native placement")
            members[row["member_spawn_stable_key"]].add(row["encounter_key"])
        declared = {row["encounter_key"] for row in placements}
        for table, columns in keys.items():
            for row in self.rows(table):
                if row["encounter_key"] not in declared:
                    raise ValueError("Encounter state has no native placement context")
                contexts[row["encounter_key"]].append(self.origin(table, *(row[column] for column in columns)))
        consumed: set[str] = set()
        for owner, (_family, data) in self.expected.items():
            for location in data["locations"]:
                for encounter in members.get(location["coordinate_stable_key"], ()):
                    consumed.add(encounter)
                    self.evidence.update((owner, relation, primary) for relation, primary in contexts[encounter])
        for encounter, origins in contexts.items():
            if encounter not in consumed:
                for origin in origins:
                    self.exclude(origin, "no_located_item_action")

    def validate_contract(self) -> dict[str, int]:
        counts = {}
        for family, table, key_column in (
            ("acquisition", "item_acquisitions", "acquisition_key"),
            ("use", "item_uses", "use_key"),
        ):
            actual = {r[key_column]: r for r in self.rows(table)}
            expected = {key: data for key, (kind, data) in self.expected.items() if kind == family}
            if actual.keys() != expected.keys():
                raise ValueError(
                    f"Item provenance {family} identities differ: missing={sorted(expected.keys() - actual.keys())!r}, "
                    f"unexpected={sorted(actual.keys() - expected.keys())!r}"
                )
            conditions: dict[str, list[dict[str, Any]]] = defaultdict(list)
            locations: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for table_suffix, grouped in (("conditions", conditions), ("locations", locations)):
                for row in self.rows(f"item_{family}_{table_suffix}"):
                    values = dict(row)
                    owner = values.pop("owner_key")
                    if owner not in actual:
                        raise ValueError(f"Orphan item provenance {table_suffix}: {owner}")
                    if table_suffix == "locations":
                        values["conditions"] = json.loads(values["conditions"])
                        values["entry_zone_line_keys"] = json.loads(values["entry_zone_line_keys"])
                    grouped[owner].append(values)
            for owner, data in expected.items():
                for dimension, value in data.items():
                    if dimension in ("conditions", "locations", "evidence"):
                        continue
                    if actual[owner][dimension] != value:
                        raise ValueError(
                            f"Item provenance {owner}: {dimension} expected {value!r}, got {actual[owner][dimension]!r}"
                        )
                for dimension, grouped in (("conditions", conditions), ("locations", locations)):
                    # JSON normalizes tuple/list and SQLite integer booleans without losing values.
                    wanted = sorted((_normalized(v) for v in data[dimension]), key=_json)
                    found = sorted((_normalized(v) for v in grouped[owner]), key=_json)
                    if wanted != found:
                        raise ValueError(f"Item provenance {owner}: {dimension} differ")
            counts[family + "s"] = len(actual)
        actual_evidence = {
            (r["owner_key"], r["input_relation"], r["input_primary_key"]) for r in self.rows("item_provenance_evidence")
        }
        if actual_evidence != self.evidence:
            raise ValueError(
                f"Item provenance evidence differs: missing={sorted(self.evidence - actual_evidence)!r}, "
                f"unexpected={sorted(actual_evidence - self.evidence)!r}"
            )
        return counts

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


def _normalized(value: object) -> Any:
    if isinstance(value, Mapping):
        return {key: _normalized(int(item) if isinstance(item, bool) else item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_normalized(item) for item in value]
    return value


def validate_item_provenance(
    connection: sqlite3.Connection,
    exclusions: Mapping[tuple[str, str], str],
    *,
    require_all_native_tables: bool,
    raw: sqlite3.Connection | None = None,
    reviewed_unreachable: frozenset[str] = frozenset(),
    lifecycle_path: Path | None = None,
) -> dict[str, object]:
    """Reject missing origins, facts or typed dimensions using native table identities."""
    if require_all_native_tables and raw is None:
        raise ValueError("Full native item coverage requires a raw database")
    coverage = _Coverage(connection)
    coverage.enumerate_loot()
    coverage.enumerate_characters()
    coverage.enumerate_crafting()
    coverage.enumerate_quests()
    coverage.enumerate_gathering()
    coverage.enumerate_operations()
    coverage.enumerate_starting_and_auctions()
    coverage.enumerate_ui()
    coverage.enumerate_smithing()
    coverage.enumerate_authored_equipment()
    coverage.enumerate_internal_equipment()
    if raw is not None:
        coverage.enumerate_smithing_byproducts(raw)
        coverage.enumerate_raw_loot(raw, reviewed_unreachable)
        coverage.enumerate_native_inputs(raw)
        coverage.enumerate_direct_native_inputs(raw)
        if require_all_native_tables and coverage.unsupported_native_tables:
            raise ValueError(f"Unsupported native input tables: {sorted(coverage.unsupported_native_tables)!r}")
    coverage.enumerate_encounter_inputs()
    consumed = {(relation, primary) for _, relation, primary in coverage.evidence}
    missing = coverage.inputs - consumed - coverage.excluded.keys()
    if missing:
        raise ValueError(f"Unaccounted native item provenance inputs: {sorted(missing)!r}")
    if dict(exclusions) != coverage.excluded:
        raise ValueError(f"Item provenance exclusions differ: expected={coverage.excluded!r}, got={dict(exclusions)!r}")
    counts = coverage.validate_contract()
    counts["dispositions"] = coverage.validate_dispositions(lifecycle_path)
    input_counts = Counter(relation for relation, _ in coverage.inputs)
    return {
        "input_counts": dict(sorted(input_counts.items())),
        "contract_counts": counts,
        "direct_native_counts": dict(sorted(coverage.direct_counts.items())),
        "unsupported_native_tables": sorted(coverage.unsupported_native_tables),
        "direct_native_exclusions": coverage.direct_exclusions,
        "exclusions": [
            {"relation": relation, "primary_key": primary, "reason": reason}
            for (relation, primary), reason in sorted(coverage.excluded.items())
        ],
    }
