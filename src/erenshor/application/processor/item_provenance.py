"""Select item facts once, retaining producer identities before presentation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import Any

from erenshor.domain.value_objects.item_provenance import (
    PROVENANCE_SCHEMA_VERSION,
    ItemAcquisition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceEvidence,
    ProvenanceLocation,
    fact_from_dict,
)

# code-fact: treasure.chest_break_roll
# code-fact: treasure.strike_melee
# code-fact: treasure.strike_bolt
_CHEST_LOOT_FACTS = ("treasure.chest_break_roll", "treasure.strike_melee", "treasure.strike_bolt")


def identity(kind: str, *parts: object) -> str:
    """Encode identities injectively, without names or mutable numeric outcomes."""
    return kind + ":" + json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ProvenanceBuilder:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.acquisitions: list[ItemAcquisition] = []
        self.uses: list[ItemUse] = []
        self.input_exclusions: dict[tuple[str, str], str] = {}
        self._groups = {
            str(row["member_stable_key"]): str(row["group_key"]) for row in self.rows("character_deduplications")
        }
        self._encountered = {str(row["member_stable_key"]) for row in self.rows("character_fact_sources")}
        self._characters = {str(row["stable_key"]): row for row in self.rows("characters")}
        # TreasureChestEvent.SpawnGuardians breaks chests through direct HP assignment.
        # Character's player-hit chest branch runs before its invulnerability guard.
        self._loot_capable = {
            key for key, row in self._characters.items() if row["can_be_damaged"] or row["treasure_chest"]
        }
        self._zones = {str(row["scene_name"]): str(row["stable_key"]) for row in self.rows("zones")}
        self._items = {str(row["stable_key"]): row for row in self.rows("items")}
        self._facts = {(str(row["fact_id"]), str(row["key"])): str(row["value"]) for row in self.rows("code_facts")}
        self._character_locations: dict[str, tuple[ProvenanceLocation, ...]] = {}

    def rows(self, table: str) -> list[dict[str, Any]]:
        if table not in self.tables:
            self.tables[table] = [dict(row) for row in self.connection.execute(f"SELECT * FROM {table}")]
        return self.tables[table]

    def evidence(self, table: str, *primary_key: object) -> ProvenanceEvidence:
        key = _json(primary_key)
        return ProvenanceEvidence(table, key)

    def gate_conditions(
        self, kind: str, key: str, item_key: str | None = None, scope: str = "source"
    ) -> tuple[ProvenanceCondition, ...]:
        atoms = [
            row
            for row in self.rows("gate_conditions")
            if row["subject_kind"] == kind
            and row["subject_stable_key"] == key
            and (row["item_stable_key"] is None or row["item_stable_key"] == item_key)
        ]
        atoms.sort(key=lambda row: _json(row))
        counts: dict[tuple[str, int], int] = defaultdict(int)
        result = []
        for row in atoms:
            gate = identity("gate", kind, key, item_key, str(row["gate"]))
            group = int(row["group_index"])
            index = counts[gate, group]
            counts[gate, group] += 1
            result.append(
                ProvenanceCondition(
                    gate,
                    group,
                    index,
                    str(row["atom_kind"]),
                    str(row["atom_stable_key"]),
                    row["atom_slot"],
                    scope=scope,
                    minimum=row["atom_quantity"],
                )
            )
        return tuple(result)

    def _entries(self, kind: str, key: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                str(row["zone_line_stable_key"])
                for row in self.rows("target_entries")
                if row["target_kind"] == kind and row["target_stable_key"] == key
            )
        )

    def _location(
        self,
        row: dict[str, Any],
        key: str,
        relation: str,
        coordinate: str | None,
        conditions: tuple[ProvenanceCondition, ...] = (),
        entries: tuple[str, ...] = (),
    ) -> ProvenanceLocation:
        return ProvenanceLocation(
            key,
            relation,
            row.get("scene"),
            self._zones.get(str(row.get("scene"))),
            key,
            coordinate,
            row.get("x"),
            row.get("y"),
            row.get("z"),
            key if conditions else None,
            row.get("player_level_min"),
            row.get("player_level_max"),
            conditions,
            entries,
            row.get("character_stable_key") or row.get("chest_character_stable_key"),
        )

    def encounter_conditions(self, spawn: str, scope: str) -> tuple[ProvenanceCondition, ...]:
        result = []
        for placement in self.rows("encounter_placements"):
            if placement["member_spawn_stable_key"] != spawn:
                continue
            encounter = str(placement["encounter_key"])
            for row in self.rows("encounter_conditions"):
                if row["encounter_key"] != encounter:
                    continue
                if row["state_scope"] == "account":
                    predicate, actor, value = "account_state", "account", str(row["required_value"])
                else:
                    predicate = "quest_done" if row["required_value"] == "true" else "quest_not_done"
                    actor, value = None, None
                result.append(
                    ProvenanceCondition(
                        identity("encounter_availability", encounter, row["state_scope"], row["state_key"]),
                        0,
                        0,
                        predicate,
                        str(row["state_key"]),
                        actor=actor,
                        value=value,
                        scope=scope,
                    )
                )
        return tuple(result)

    def character_locations(self, copy: str) -> tuple[ProvenanceLocation, ...]:
        if copy in self._character_locations:
            return self._character_locations[copy]
        locations = []
        for row in self.rows("character_spawns"):
            if row["character_stable_key"] != copy:
                continue
            spawn_key = row["spawn_point_stable_key"]
            key = identity("placement", copy, spawn_key, row["is_directly_placed"])
            conditions = self.gate_conditions("character", copy, scope=key)
            if spawn_key:
                conditions += self.gate_conditions("spawn_point", str(spawn_key), scope=key)
                conditions += self.encounter_conditions(str(spawn_key), key)
            if row.get("furniture_item_stable_key") and not any(
                atom.predicate == "room_furnished" for atom in conditions
            ):
                conditions += (
                    ProvenanceCondition(
                        "furniture",
                        0,
                        0,
                        "room_furnished",
                        str(row["furniture_item_stable_key"]),
                        row["furniture_slot"],
                        scope=key,
                    ),
                )
            entries = self._entries("character", copy) + self._entries("spawn_point", str(spawn_key))
            locations.append(
                self._location(
                    row,
                    key,
                    "fixed" if row["is_directly_placed"] else "spawn",
                    str(spawn_key or copy),
                    conditions,
                    tuple(sorted(set(entries))),
                )
            )
        for row in self.rows("treasure_chest_possible_spawns"):
            if row["chest_character_stable_key"] == copy:
                key = str(row["treasure_location_stable_key"])
                locations.append(self._location(row, key, "possible_treasure", key))
        result = tuple(locations) or (
            ProvenanceLocation(identity("unlocated", copy), "unlocated", source_copy_stable_key=copy),
        )
        self._character_locations[copy] = result
        return result

    @staticmethod
    def conditional_quantity(distributions: tuple[str | None, ...]) -> tuple[int, int] | None:
        """Bound physical copies conditional on a nonzero native drop outcome."""
        counts: set[int] = set()
        for encoded in distributions:
            if encoded is None:
                return None
            distribution = json.loads(encoded)
            if not isinstance(distribution, list):
                raise ValueError("Native drop count distribution must be a numeric array")
            counts.update(index for index, probability in enumerate(distribution) if index > 0 and probability > 0)
        return (min(counts), max(counts)) if counts else None

    def acquisition(
        self,
        kind: str,
        item: str,
        source: str | None,
        *,
        primary: tuple[object, ...],
        evidence: tuple[ProvenanceEvidence, ...],
        chance: float | None = None,
        quantity: float | None = None,
        **kwargs: Any,
    ) -> ItemAcquisition:
        fact = ItemAcquisition(
            identity("acquisition", kind, *primary),
            item,
            kind,
            source,
            probability_kind="exact" if chance is not None else "unknown",
            probability_min=chance,
            probability_max=chance,
            quantity_min=quantity,
            quantity_max=quantity,
            quantity_kind="exact" if quantity is not None else "unknown",
            evidence=evidence,
            **kwargs,
        )
        if quantity is None and fact.count_distribution is not None:
            bounds = self.conditional_quantity((fact.count_distribution,))
            if bounds is not None:
                low, high = bounds
                fact = replace(
                    fact,
                    quantity_min=low,
                    quantity_max=high,
                    quantity_kind="exact" if low == high else "bounded",
                )
        if kwargs.get("probability_basis") == "not_applicable" and chance is None:
            fact = replace(fact, probability_kind="not_applicable")
        if chance is not None and chance <= 0:
            fact = replace(fact, player_access_state="non_acquirable")
        self.acquisitions.append(fact)
        return fact

    def use(
        self,
        kind: str,
        item: str,
        target: str | None,
        *,
        primary: tuple[object, ...],
        evidence: tuple[ProvenanceEvidence, ...],
        quantity: float | None = None,
        quantity_range: tuple[float | None, float | None] | None = None,
        **kwargs: Any,
    ) -> ItemUse:
        fact = ItemUse(
            identity("use", kind, *primary),
            item,
            target,
            kind,
            quantity_min=quantity_range[0] if quantity_range is not None else quantity,
            quantity_max=quantity_range[1] if quantity_range is not None else quantity,
            quantity_kind="bounded" if quantity_range is not None else "exact" if quantity is not None else "unknown",
            evidence=evidence,
            **kwargs,
        )
        self.uses.append(fact)
        return fact

    def require_facts(self, *fact_ids: str) -> tuple[ProvenanceEvidence, ...]:
        for fact_id in fact_ids:
            if self._facts.get((fact_id, "ok")) != "true":
                raise ValueError(f"Missing item mechanic evidence: {fact_id}")
        return tuple(self.evidence("code_facts", fact_id, "ok") for fact_id in fact_ids)

    @staticmethod
    def loot_probability_context() -> tuple[ProvenanceCondition, ...]:
        """The published rate is evaluated at this initialization-state parameter point."""
        return tuple(
            ProvenanceCondition(
                "probability_context",
                0,
                index,
                "formula_operand",
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

    def ownership_replacement(
        self, item: str
    ) -> tuple[tuple[ProvenanceCondition, ...], tuple[ProvenanceEvidence, ...]]:
        if not self._items[item]["is_unique"]:
            return (), ()
        # code-fact: loot.owned_unique_replacement
        if not any(
            row["fact_id"] == "loot.owned_unique_replacement" and row["key"] == "ok" and row["value"] == "true"
            for row in self.rows("code_facts")
        ):
            raise ValueError("Missing owned unique-item replacement evidence")
        return (
            (
                ProvenanceCondition(
                    "not_owned",
                    0,
                    0,
                    "item_not_owned",
                    item,
                    value="stored_slots_and_equipment_slots",
                    phase="source_initialization",
                ),
            ),
            (self.evidence("code_facts", "loot.owned_unique_replacement", "ok"),),
        )

    def loot(self) -> None:
        # code-fact: loot.start_initialization_sequence
        # code-fact: loot.character_component_binding
        # code-fact: loot.corpse_component_binding
        initialization_evidence = self.require_facts(
            "loot.start_initialization_sequence", "loot.character_component_binding", "loot.corpse_component_binding"
        )
        context = self.loot_probability_context()
        common: dict[str, list[tuple[dict[str, Any], ProvenanceEvidence]]] = defaultdict(list)
        own_flags = (
            "is_common",
            "is_uncommon",
            "is_rare",
            "is_legendary",
            "is_ultra_rare",
            "is_guaranteed",
            "is_actual",
        )
        for row in self.rows("loot_drops"):
            copy, item = str(row["character_stable_key"]), str(row["item_stable_key"])
            evidence = self.evidence("loot_drops", copy, item)
            if copy not in self._encountered:
                self.input_exclusions[(evidence.input_relation, evidence.input_primary_key)] = "unencountered_copy"
                continue
            initializes = bool(row["source_component_is_enabled"])
            if not initializes and not row["is_actual"]:
                raise ValueError("A disabled loot component cannot execute its configured initializer pools")
            if row["is_common_world_item"] and not any(row[flag] for flag in own_flags):
                if copy in self._loot_capable:
                    common[item].append((row, evidence))
                else:
                    self.input_exclusions[(evidence.input_relation, evidence.input_primary_key)] = (
                        "loot_host_undamageable"
                    )
                continue
            ownership_conditions, ownership_evidence = self.ownership_replacement(item) if initializes else ((), ())
            death_evidence = (
                self.require_facts(*_CHEST_LOOT_FACTS)
                if not self._characters[copy]["can_be_damaged"] and self._characters[copy]["treasure_chest"]
                else ()
            )
            self.acquisition(
                "character_drop",
                item,
                self._groups[copy],
                primary=(copy, item),
                evidence=(evidence, *ownership_evidence, *initialization_evidence, *death_evidence),
                chance=row["drop_probability"],
                probability_basis="per_kill",
                source_group_key=self._groups[copy],
                source_copy_stable_key=copy,
                expected_quantity=row["expected_per_kill"],
                count_distribution=row["drop_count_distribution"],
                guarantee_scope="pool" if initializes and row["is_guaranteed"] else None,
                player_access_state=(
                    "non_acquirable"
                    if copy not in self._loot_capable
                    else "verified_player"
                    if initializes
                    else "unconfirmed_player"
                ),
                mechanic=None if initializes else "preseeded_before_start",
                guaranteed_roll_count=(
                    self._characters[copy]["guaranteed_drop_rolls"] if initializes and row["is_guaranteed"] else None
                ),
                locations=self.character_locations(copy),
                conditions=(
                    *self.gate_conditions("character", copy),
                    *ownership_conditions,
                    *(context if initializes else ()),
                ),
            )
        for item, outcomes in common.items():
            probabilities = [row["drop_probability"] for row, _ in outcomes if row["drop_probability"] is not None]
            death_evidence = (
                self.require_facts(*_CHEST_LOOT_FACTS)
                if any(not self._characters[str(row["character_stable_key"])]["can_be_damaged"] for row, _ in outcomes)
                else ()
            )
            fact = self.acquisition(
                "common_world_item",
                item,
                None,
                primary=(item,),
                evidence=(*tuple(evidence for _, evidence in outcomes), *initialization_evidence, *death_evidence),
                probability_basis="per_kill",
                conditions=context,
            )
            bounds = self.conditional_quantity(tuple(row["drop_count_distribution"] for row, _ in outcomes))
            if bounds is not None:
                low, high = bounds
                fact = replace(
                    fact,
                    quantity_min=low,
                    quantity_max=high,
                    quantity_kind="exact" if low == high else "bounded",
                )
                self.acquisitions[-1] = fact
            if len(probabilities) == len(outcomes):
                low, high = min(probabilities), max(probabilities)
                self.acquisitions[-1] = replace(
                    fact,
                    probability_kind="exact" if low == high else "bounded",
                    probability_min=low,
                    probability_max=high,
                    player_access_state="non_acquirable" if high <= 0 else "verified_player",
                )
        for row in self.rows("special_world_drops"):
            item, pool = str(row["item_stable_key"]), str(row["pool"])
            ownership_conditions, ownership_evidence = self.ownership_replacement(item)
            self.acquisition(
                "special_world_drop",
                item,
                None,
                primary=(item, pool),
                evidence=(
                    self.evidence("special_world_drops", item, pool),
                    *ownership_evidence,
                    *initialization_evidence,
                ),
                chance=row["drop_probability"],
                probability_basis="per_kill",
                variant_key=pool,
                mechanic="default_loot_rate_without_bonuses",
                conditions=(
                    *(
                        (
                            ProvenanceCondition(
                                "enemy_level",
                                0,
                                0,
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

    def vendors_and_dialog(self) -> None:
        offers: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in self.rows("vendor_offers"):
            offers[(str(row["copy_stable_key"]), str(row["item_stable_key"]))].append(row)
        for (copy, item), rows in sorted(offers.items()):
            group = str(rows[0]["vendor_stable_key"])
            conditions = self.gate_conditions("character", copy) + self.gate_conditions("vendor_item", copy, item)
            offer_evidence = tuple(
                self.evidence("vendor_offers", copy, row["offer_kind"], row["offer_slot"]) for row in rows
            )
            self.acquisition(
                "vendor",
                item,
                group,
                primary=(copy, item),
                evidence=offer_evidence,
                source_group_key=group,
                source_copy_stable_key=copy,
                probability_basis="not_applicable",
                conditions=conditions,
                locations=self.character_locations(copy),
            )
        variants = {str(row["resource_name"]): row for row in self.rows("quest_variants")}
        for row in self.rows("character_dialogs"):
            if not row["give_item_stable_key"]:
                continue
            copy, slot, item = str(row["character_stable_key"]), row["dialog_index"], str(row["give_item_stable_key"])
            evidence = self.evidence("character_dialogs", copy, slot)
            if copy not in self._encountered:
                self.input_exclusions[(evidence.input_relation, evidence.input_primary_key)] = "unencountered_copy"
                continue
            conditions = self.gate_conditions("character", copy)
            conditions += (
                ProvenanceCondition(
                    "not_owned", 0, 0, "item_not_owned", item, value="stored_slots_and_equipment_slots"
                ),
            )
            if row["required_quest_stable_key"]:
                conditions += (
                    ProvenanceCondition(
                        "dialog_prerequisite", 0, 0, "quest_done", str(row["required_quest_stable_key"])
                    ),
                )
            assigned = row["assign_quest_variant_resource_name"]
            if assigned:
                if assigned not in variants:
                    raise ValueError(f"Dialog assignment references absent quest variant: {assigned}")
                variant = variants[assigned]
                if not variant["repeatable"]:
                    conditions += (
                        ProvenanceCondition(
                            "dialog_assignment", 0, 0, "quest_not_done", str(variant["quest_stable_key"])
                        ),
                    )
            self.acquisition(
                "dialog",
                item,
                self._groups[copy],
                primary=(copy, slot),
                evidence=(evidence,),
                quantity=1,
                source_group_key=self._groups[copy],
                source_copy_stable_key=copy,
                variant_key=str(slot),
                probability_basis="not_applicable",
                conditions=conditions,
                locations=self.character_locations(copy),
            )

    def crafting(self) -> None:
        # code-fact: smithing.template_flag
        # code-fact: smithing.fuel_flag
        # code-fact: smithing.single_template_amount
        # code-fact: smithing.single_fuel_amount
        # code-fact: smithing.fuel_quality
        forge_evidence = self.require_facts(
            "smithing.template_flag",
            "smithing.fuel_flag",
            "smithing.single_template_amount",
            "smithing.single_fuel_amount",
            "smithing.fuel_quality",
        )
        for row in self.rows("crafting_rewards"):
            recipe, slot, item = (
                str(row["recipe_item_stable_key"]),
                row["reward_slot"],
                str(row["reward_item_stable_key"]),
            )
            mechanic = identity("crafting", recipe)
            evidence = (self.evidence("crafting_rewards", recipe, slot), *forge_evidence)
            executable = (
                int(slot) == 1
                and bool(self._items[recipe]["template"])
                and str(self._items[recipe]["id"]) not in self._facts[("smithing.upgrade_ids", "strings")].split(",")
            )
            conditions: tuple[ProvenanceCondition, ...] = (
                () if executable else (ProvenanceCondition("unexecuted_reward_slot", 0, 0, "never"),)
            )
            if self._items[item]["required_slot"] not in ("General", "Aura", "Charm"):
                conditions += (
                    ProvenanceCondition(
                        "fuel_quality",
                        0,
                        0,
                        "formula_operand",
                        value="selected_fuel_level_plus_one",
                        phase="operation_outcome",
                    ),
                )
            fact = self.acquisition(
                "crafting",
                item,
                recipe,
                primary=(recipe, slot),
                evidence=evidence,
                quantity=row["reward_quantity"],
                variant_key=str(slot),
                mechanic=mechanic,
                probability_basis="per_use",
                player_access_state="verified_player" if executable else "non_acquirable",
                conditions=conditions,
            )
            self.use(
                "crafting_recipe",
                recipe,
                item,
                primary=(recipe, slot),
                evidence=evidence,
                quantity=1,
                variant_key=str(slot),
                mechanic=mechanic,
                outcome_key=fact.acquisition_key,
                conditions=conditions,
            )
        for row in self.rows("crafting_recipes"):
            recipe, slot = str(row["recipe_item_stable_key"]), row["material_slot"]
            material = self._items[str(row["material_item_stable_key"])]
            conditions = ()
            if not self._items[recipe]["template"] or str(self._items[recipe]["id"]) in self._facts[
                ("smithing.upgrade_ids", "strings")
            ].split(","):
                conditions = (ProvenanceCondition("unexecuted_material_slot", 0, 0, "never"),)
            if material["required_slot"] not in ("General", "Aura") and row["material_quantity"] == 1:
                conditions += (
                    ProvenanceCondition(
                        "material_quality",
                        0,
                        0,
                        "quality",
                        value="normal",
                        phase="operation_input",
                    ),
                )
            self.use(
                "crafting_material",
                str(row["material_item_stable_key"]),
                recipe,
                primary=(recipe, slot),
                evidence=(self.evidence("crafting_recipes", recipe, slot), *forge_evidence),
                quantity=row["material_quantity"],
                material_slot=slot,
                mechanic=identity("crafting", recipe),
                conditions=conditions,
            )

    def quests(self) -> None:
        routes: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self.rows("character_quest_manager_quests"):
            if row["character_stable_key"] in self._encountered:
                routes[str(row["quest_variant_resource_name"])].append(row)
        for row in self.rows("quest_variants"):
            if not row["item_on_complete_stable_key"]:
                continue
            variant, quest, item = (
                str(row["resource_name"]),
                str(row["quest_stable_key"]),
                str(row["item_on_complete_stable_key"]),
            )
            evidence = self.evidence("quest_variants", variant)
            if not routes[variant]:
                self.input_exclusions[(evidence.input_relation, evidence.input_primary_key)] = "no_executed_item_grant"
                continue
            for route in routes[variant]:
                copy = str(route["character_stable_key"])
                mechanic = identity("trade_reward", variant, copy, route["quest_slot"])
                conditions = self.gate_conditions("character", copy)
                if not row["repeatable"]:
                    conditions += (ProvenanceCondition("quest_available", 0, 0, "quest_not_done", quest),)
                required: dict[str, int] = defaultdict(int)
                for material in self.rows("quest_required_items"):
                    if material["quest_variant_resource_name"] == variant:
                        required[str(material["item_stable_key"])] += int(material["quantity"])
                conditions += tuple(
                    ProvenanceCondition("turnin_items", 0, index, "item_held", key, minimum=quantity)
                    for index, (key, quantity) in enumerate(sorted(required.items()))
                )
                self.acquisition(
                    "quest_reward",
                    item,
                    quest,
                    primary=(variant, mechanic),
                    evidence=(evidence, self.evidence("character_quest_manager_quests", copy, route["quest_slot"])),
                    quantity=1,
                    variant_key=variant,
                    mechanic=mechanic,
                    source_copy_stable_key=copy,
                    source_group_key=self._groups[copy],
                    probability_basis="not_applicable",
                    conditions=conditions,
                    locations=self.character_locations(copy),
                )
        variants = {str(row["resource_name"]): str(row["quest_stable_key"]) for row in self.rows("quest_variants")}
        for row in self.rows("quest_required_items"):
            variant, item, slot = (
                str(row["quest_variant_resource_name"]),
                str(row["item_stable_key"]),
                row["required_slot"],
            )
            self.use(
                "quest_requirement",
                item,
                variants[variant],
                primary=(variant, slot),
                evidence=(self.evidence("quest_required_items", variant, slot),),
                quantity=row["quantity"],
                variant_key=variant,
                material_slot=slot,
            )

    def gathering(self) -> None:
        for table, kind, source_column, location_table, basis in (
            ("mining_node_items", "mining", "mining_node_stable_key", "mining_nodes", "per_node"),
            ("water_fishables", "fishing", "water_stable_key", "waters", "per_successful_catch"),
        ):
            locations = {str(row["stable_key"]): row for row in self.rows(location_table)}
            for row in self.rows(table):
                source, item = str(row[source_column]), str(row["item_stable_key"])
                period = row.get("type")
                primary = (source, period, item) if period is not None else (source, item)
                time = {"DayFishable": "day", "NightFishable": "night"}[str(period)] if period is not None else None
                conditions = (
                    (ProvenanceCondition("time", 0, 0, "time_of_day", value=time, phase="operation_input"),)
                    if time is not None
                    else ()
                )
                self.acquisition(
                    kind,
                    item,
                    source,
                    primary=primary,
                    evidence=(self.evidence(table, *primary),),
                    chance=row["drop_chance"],
                    quantity=1,
                    probability_basis=basis,
                    variant_key=str(period) if period else None,
                    conditions=conditions,
                    locations=(self._location(locations[source], source, "fixed", source),),
                )
        for row in self.rows("fishing_bonus_catches"):
            item = str(row["item_stable_key"])
            self.acquisition(
                "fishing_bonus",
                item,
                None,
                primary=(item,),
                evidence=(self.evidence("fishing_bonus_catches", item),),
                chance=row["chance_per_catch"],
                quantity=1,
                probability_basis="per_successful_catch",
                probability_stage="native_pool",
                mechanic="fishing_global_replacement",
            )
        for row in self.rows("item_bags"):
            if row["item_stable_key"]:
                source, item = str(row["stable_key"]), str(row["item_stable_key"])
                # code-fact: item_bag.unique_initialization
                # code-fact: item_bag.single_pickup
                bag_evidence = self.require_facts("item_bag.unique_initialization", "item_bag.single_pickup")
                bag_conditions = self.gate_conditions("item_bag", source)
                if self._items[item]["is_unique"]:
                    bag_conditions += (
                        ProvenanceCondition(
                            "initial_ownership",
                            0,
                            0,
                            "item_not_owned",
                            item,
                            value="stored_slots_and_equipment_slots",
                            phase="source_initialization",
                        ),
                    )
                self.acquisition(
                    "item_bag",
                    item,
                    source,
                    primary=(source,),
                    evidence=(self.evidence("item_bags", source), *bag_evidence),
                    quantity=1,
                    probability_basis="not_applicable",
                    conditions=bag_conditions,
                    locations=(
                        self._location(row, source, "fixed", source, entries=self._entries("item_bag", source)),
                    ),
                )

    def item_operations(self) -> None:
        # code-fact: inventory.default_single_add
        # code-fact: inventory.default_single_force
        # code-fact: item.fossil_pool_grant
        pool_grant = "item.fossil_pool_grant"
        if int(self._facts[(pool_grant, "quantity")]) != 1 or int(self._facts[(pool_grant, "rolls")]) != 1:
            raise ValueError("Uniform item-pool grants require the shipped single-roll, single-item operation")
        for row in self.rows("item_drops"):
            source, item, pool = (
                str(row[key]) for key in ("source_item_stable_key", "dropped_item_stable_key", "pool_stable_key")
            )
            evidence = (
                self.evidence("item_drops", source, item, pool),
                *self.require_facts("inventory.default_single_add", "inventory.default_single_force"),
                *(self.evidence("code_facts", pool_grant, key) for key in ("spell_name", "quantity", "pool", "rolls")),
            )
            mechanic = identity("item_drop", source, pool)
            fact = self.acquisition(
                "item_drop",
                item,
                source,
                primary=(source, item, pool),
                evidence=evidence,
                chance=row["drop_probability"],
                quantity=1,
                expected_quantity=float(row["drop_probability"]) / 100.0,
                count_distribution=json.dumps(
                    [1.0 - float(row["drop_probability"]) / 100.0, float(row["drop_probability"]) / 100.0]
                ),
                probability_basis="per_use",
                mechanic=mechanic,
                guarantee_scope="pool",
                guaranteed_roll_count=1,
                variant_key=pool,
            )
            self.use(
                "item_drop",
                source,
                item,
                primary=(source, item, pool),
                evidence=evidence,
                quantity=1,
                mechanic=mechanic,
                variant_key=pool,
                outcome_key=fact.acquisition_key,
            )
        for row in self.rows("spell_created_items"):
            source, item, spell = (
                str(row["source_item_stable_key"]),
                str(row["created_item_stable_key"]),
                str(row["spell_stable_key"]),
            )
            evidence = (
                self.evidence("spell_created_items", source, item),
                *(
                    self.evidence("code_facts", str(row["grant_fact_id"]), key)
                    for key in ("spell_name", "created_item_id", "quantity")
                ),
                *self.require_facts("inventory.default_single_add", "inventory.default_single_force"),
            )
            mechanic = identity("spell_created", source, spell)
            fact = self.acquisition(
                "spell_created",
                item,
                source,
                primary=(source, spell, item),
                evidence=evidence,
                quantity=row["quantity"],
                probability_basis="per_use",
                mechanic=mechanic,
                variant_key=spell,
            )
            self.use(
                "spell_created",
                source,
                item,
                primary=(source, spell, item),
                evidence=evidence,
                quantity=1,
                mechanic=mechanic,
                variant_key=spell,
                outcome_key=fact.acquisition_key,
            )
        for row in self.rows("item_conversions"):
            source, item, mechanic, zone = (
                str(row[key])
                for key in ("input_item_stable_key", "output_item_stable_key", "mechanic", "zone_stable_key")
            )
            evidence = (self.evidence("item_conversions", source, item, mechanic),)
            conditions = (ProvenanceCondition("zone", 0, 0, "zone_use", zone),)
            locations = (
                ProvenanceLocation(identity("mechanic_zone", mechanic, zone), "mechanic_zone", zone_stable_key=zone),
            )
            fact = self.acquisition(
                "item_conversion",
                item,
                source,
                primary=(source, item, mechanic),
                evidence=evidence,
                quantity=1,
                probability_basis="per_use",
                mechanic=mechanic,
                conditions=conditions,
                locations=locations,
            )
            self.use(
                "item_conversion",
                source,
                item,
                primary=(source, item, mechanic),
                evidence=evidence,
                quantity=1,
                mechanic=mechanic,
                outcome_key=fact.acquisition_key,
                conditions=conditions,
                locations=locations,
            )
        for row in self.rows("item_zone_restrictions"):
            item, zone = str(row["item_stable_key"]), str(row["zone_stable_key"])
            self.use(
                "zone_restriction",
                item,
                zone,
                primary=(item, zone),
                evidence=(self.evidence("item_zone_restrictions", item, zone),),
                mechanic=str(row["outcome"]),
                conditions=(ProvenanceCondition("zone", 0, 0, "zone_use", zone),),
            )
        for row in self.rows("quality_offerings"):
            source = str(row["character_stable_key"])
            operation: tuple[ProvenanceCondition, ...] = (
                ProvenanceCondition(
                    "stone_counts",
                    0,
                    0,
                    "formula_operand",
                    value="equal_positive_stone_counts",
                    minimum=1,
                    phase="operation_input",
                ),
                ProvenanceCondition(
                    "offered_items",
                    0,
                    0,
                    "formula_operand",
                    value="all_offered_slots_consumed",
                    phase="mechanic_parameter",
                ),
                ProvenanceCondition(
                    "failure",
                    0,
                    0,
                    "formula_operand",
                    value="return_original_equipment_quality",
                    phase="operation_outcome",
                ),
            )
            operation += (
                ProvenanceCondition(
                    "result_quality", 0, 0, "quality", value=str(row["result_quality"]), phase="operation_outcome"
                ),
                ProvenanceCondition(
                    "enhanced_quality", 0, 0, "quality", value=str(row["enhanced_quality"]), phase="operation_outcome"
                ),
                *tuple(
                    ProvenanceCondition(
                        gate, 0, 0, "formula_operand", value=column, minimum=row[column], phase="mechanic_parameter"
                    )
                    for gate, column in (
                        ("chance_per_pair", "chance_per_stone_pair"),
                        ("chance_per_improvement", "chance_per_improvement_level"),
                        ("enhance_chance", "enhance_chance_per_stone_pair"),
                    )
                ),
            )
            for slot, column in enumerate(("first_item_stable_key", "second_item_stable_key")):
                self.use(
                    "quality_offering",
                    str(row[column]),
                    self._groups.get(source, source),
                    primary=(source, slot),
                    evidence=(self.evidence("quality_offerings", source),),
                    quantity_range=(1, None),
                    material_slot=slot,
                    mechanic=identity("quality_offering", source),
                    locations=self.character_locations(source),
                    conditions=operation,
                )
            for gear in self.rows("items"):
                if gear["required_slot"] in ("General", "Aura"):
                    continue
                item = str(gear["stable_key"])
                self.use(
                    "quality_offering",
                    item,
                    self._groups.get(source, source),
                    primary=(source, item, "equipment"),
                    evidence=(self.evidence("quality_offerings", source), self.evidence("items", item)),
                    quantity=1,
                    material_slot=2,
                    mechanic=identity("quality_offering", source),
                    locations=self.character_locations(source),
                    conditions=(
                        *operation,
                        ProvenanceCondition(
                            "eligible_quality", 0, 0, "quality", minimum=1, maximum=1, phase="operation_input"
                        ),
                        ProvenanceCondition("eligible_quality", 1, 0, "quality", minimum=11, phase="operation_input"),
                        ProvenanceCondition(
                            "improvement",
                            0,
                            0,
                            "formula_operand",
                            value="max_quality_minus_ten_or_zero",
                            phase="mechanic_parameter",
                        ),
                        ProvenanceCondition(
                            "success",
                            0,
                            0,
                            "formula_operand",
                            value="integer_roll_0_99_lt_pair_chance_plus_improvement_bonus",
                            phase="operation_outcome",
                        ),
                        ProvenanceCondition(
                            "enhancement",
                            0,
                            0,
                            "formula_operand",
                            value="improved_input_and_second_integer_roll_0_99_lt_bonus_plus_pair_enhancement",
                            phase="operation_outcome",
                        ),
                    ),
                )

    def starting_and_auctions(self) -> None:
        for row in self.rows("class_starting_items"):
            item, class_name, slot = str(row["item_stable_key"]), str(row["class_name"]), row["sort_order"]
            self.acquisition(
                "starting_class",
                item,
                "class:" + class_name.lower(),
                primary=(class_name, slot),
                evidence=(self.evidence("class_starting_items", class_name, slot),),
                quantity=1,
                variant_key=str(slot),
                probability_basis="not_applicable",
            )
        brokers = {str(row["character_stable_key"]) for row in self.rows("auction_house_brokers")}
        locations = tuple(
            replace(location, relation="interaction")
            for broker in sorted(brokers & self._encountered)
            for location in self.character_locations(broker)
        )
        for row in self.rows("auction_house_items"):
            item, route = str(row["item_stable_key"]), str(row["route"])
            conditions = []
            for actor in ("sim", "player"):
                minimum, maximum = row[f"min_{actor}_level"], row[f"max_{actor}_level"]
                if minimum is not None or maximum is not None:
                    conditions.append(
                        ProvenanceCondition(
                            "level_" + actor, 0, 0, "actor_level", actor=actor, minimum=minimum, maximum=maximum
                        )
                    )
            self.acquisition(
                "auction_house",
                item,
                "mechanic:auction_house",
                primary=(item, route),
                evidence=(self.evidence("auction_house_items", item, route),),
                variant_key=route,
                mechanic=identity("auction_house", route),
                probability_basis="per_listing_opportunity",
                conditions=tuple(conditions),
                locations=locations or (ProvenanceLocation("auction_house:unlocated", "unlocated"),),
            )

    def ui_grants(self) -> None:
        builds = self.rows("code_facts_meta")
        observations = {
            (row["component_type"], row["slot"]): row
            for row in self.rows("item_access_observations")
            if len(builds) == 1 and row["assembly_sha256"] == builds[0]["assembly_sha256"]
        }
        targets = self.rows("ui_item_access_targets")
        for row in self.rows("ui_item_sources"):
            source, component, slot = str(row["stable_key"]), str(row["component_type"]), str(row["slot"])
            if component == "ReplenishTMOGHide":
                item = row["replenish_item_stable_key"]
                mechanic = "cosmetic_panel"
                quantity = 1
                locations: tuple[ProvenanceLocation, ...] = (
                    ProvenanceLocation(identity("ui_unlocated", source), "unlocated"),
                )
            elif component == "PlanningTableUI":
                item = row["serialized_item_stable_key"]
                mechanic = "planning_table"
                quantity = row["serialized_quantity"]
                possible = []
                for target in targets:
                    if target["tag"] != "PlanningDesk":
                        continue
                    target_key = str(target["stable_key"])
                    location_conditions = self.gate_conditions("ui_item_access_target", target_key, scope=target_key)
                    possible.append(self._location(target, target_key, "interaction", target_key, location_conditions))
                locations = tuple(possible) or (ProvenanceLocation(identity("ui_unlocated", source), "unlocated"),)
            else:
                raise ValueError(f"Unsupported native item UI component {component!r}")
            evidence = self.evidence("ui_item_sources", source)
            native_evidence = [evidence]
            if component == "PlanningTableUI":
                for location in locations:
                    if location.relation == "interaction":
                        native_evidence.append(self.evidence("ui_item_access_targets", location.location_key))
            if not item:
                self.input_exclusions[(evidence.input_relation, evidence.input_primary_key)] = "empty_native_ui_slot"
                continue
            observation = observations.get((component, slot))
            if observation is not None:
                native_evidence.append(
                    self.evidence("item_access_observations", component, slot, observation["assembly_sha256"])
                )
            access = "verified_player" if observation is not None and not row["display_only"] else "unconfirmed_player"
            conditions: tuple[ProvenanceCondition, ...] = (
                ProvenanceCondition("transfer", 0, 0, "route", value="normal_pointer_inventory_transfer"),
            )
            if component == "ReplenishTMOGHide":
                conditions += (
                    ProvenanceCondition("replenishment", 0, 0, "source_replenishment", value="while_source_active"),
                )
            self.acquisition(
                "ui_grant",
                str(item),
                source,
                primary=(source, slot),
                evidence=tuple(native_evidence),
                quantity=quantity,
                mechanic=mechanic,
                variant_key=slot,
                player_access_state=access,
                probability_basis="not_applicable",
                guarantee_scope="successful_ui_transfer",
                conditions=conditions,
                locations=locations,
            )

    def smithing(self) -> None:
        # code-fact: smithing.planar_input_quality
        # code-fact: smithing.planar_single_input
        # code-fact: smithing.planar_output_quality
        # code-fact: smithing.blessing_input_quality
        # code-fact: smithing.blessing_single_input
        # code-fact: smithing.blessing_outputs
        # code-fact: smithing.ascension_input_quality
        # code-fact: smithing.ascension_two_inputs
        # code-fact: smithing.ascension_equal_inputs
        # code-fact: smithing.ascension_output_quality
        facts = {(str(row["fact_id"]), str(row["key"])): str(row["value"]) for row in self.rows("code_facts")}
        # code-fact: smithing.upgrade_ids
        # code-fact: smithing.planar_fuel
        if facts.get(("smithing.upgrade_ids", "strings")) != "31377423,2298018,2265228":
            raise ValueError("Re-derive the native special smithing routes")
        if facts.get(("smithing.planar_fuel", "ok")) != "true":
            raise ValueError("Missing special smithing fuel evidence")
        by_id = {str(row["id"]): str(row["stable_key"]) for row in self.rows("items")}
        for item_id in ("31377423", "2298018", "2265228", "46289586"):
            if item_id not in by_id:
                raise ValueError(f"Special smithing references absent native item ID {item_id}")
        upgrade, removal, combining = (by_id[value] for value in ("31377423", "2298018", "2265228"))
        fuel = by_id["46289586"]
        evidence: tuple[ProvenanceEvidence, ...] = (
            self.evidence("code_facts", "smithing.upgrade_ids", "strings"),
            self.evidence("code_facts", "smithing.planar_fuel", "ok"),
        )
        evidence += self.require_facts(
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
        normal_recipes = {
            str(row["recipe_item_stable_key"])
            for row in self.rows("crafting_rewards")
            if row["reward_slot"] == 1
            and self._items[str(row["recipe_item_stable_key"])]["template"]
            and str(self._items[str(row["recipe_item_stable_key"])]["id"])
            not in facts[("smithing.upgrade_ids", "strings")].split(",")
        }
        for fuel_row in self.rows("items"):
            if not fuel_row["fuel_source"]:
                continue
            fuel_item = str(fuel_row["stable_key"])
            for target, role in (
                *((recipe, "forge_fuel") for recipe in sorted(normal_recipes)),
                (removal, "blessing_removal_fuel"),
                (combining, "combining_fuel"),
            ):
                self.use(
                    "smithing",
                    fuel_item,
                    target,
                    primary=(fuel_item, target, role),
                    quantity=1,
                    evidence=(*evidence, self.evidence("items", fuel_item)),
                    mechanic=role,
                    conditions=(
                        ProvenanceCondition(
                            "fuel_level",
                            0,
                            0,
                            "formula_operand",
                            value="fuel_level",
                            minimum=fuel_row["fuel_level"],
                            maximum=fuel_row["fuel_level"],
                            phase="mechanic_parameter",
                        ),
                    ),
                )
        self.use(
            "smithing",
            fuel,
            upgrade,
            primary=(fuel, upgrade, "upgrade_material"),
            quantity=1,
            evidence=evidence,
            mechanic="upgrade_material",
        )
        self.use(
            "smithing",
            removal,
            removal,
            primary=(removal, "blessing_removal_material"),
            quantity=1,
            evidence=evidence,
            mechanic="blessing_removal_material",
        )
        self.use(
            "smithing",
            combining,
            combining,
            primary=(combining, "combine_quality"),
            quantity=1,
            evidence=evidence,
            mechanic="combine_quality",
        )
        for row in self.rows("items"):
            slot, item = row["required_slot"], str(row["stable_key"])
            if slot not in ("General", "Aura"):
                self.use(
                    "smithing",
                    item,
                    upgrade,
                    primary=(item, upgrade, "quality_upgrade"),
                    quantity=1,
                    evidence=(*evidence, self.evidence("items", item)),
                    mechanic="quality_upgrade",
                    conditions=(
                        ProvenanceCondition(
                            "input_quality",
                            0,
                            0,
                            "quality",
                            value="blessed",
                            phase="operation_input",
                        ),
                        ProvenanceCondition(
                            "output_quality",
                            0,
                            0,
                            "quality",
                            value="divine",
                            phase="operation_outcome",
                        ),
                    ),
                )
                self.use(
                    "smithing",
                    item,
                    removal,
                    primary=(item, removal, "remove_blessing"),
                    quantity=1,
                    evidence=(*evidence, self.evidence("items", item)),
                    mechanic="remove_blessing",
                    conditions=(
                        ProvenanceCondition(
                            "input_quality",
                            0,
                            0,
                            "quality",
                            minimum=2,
                            maximum=3,
                            phase="operation_input",
                        ),
                        ProvenanceCondition(
                            "output_quality",
                            0,
                            0,
                            "quality",
                            value="normal",
                            phase="operation_outcome",
                        ),
                    ),
                )
            if slot not in ("General", "Aura", "Charm"):
                self.use(
                    "smithing",
                    item,
                    combining,
                    primary=(item, combining, "combine_matching"),
                    quantity=2,
                    evidence=(*evidence, self.evidence("items", item)),
                    mechanic="combine_matching",
                    conditions=(
                        ProvenanceCondition(
                            "input_quality",
                            0,
                            0,
                            "quality",
                            minimum=1,
                            maximum=1,
                            phase="operation_input",
                        ),
                        ProvenanceCondition(
                            "input_quality",
                            1,
                            0,
                            "quality",
                            minimum=11,
                            maximum=14,
                            phase="operation_input",
                        ),
                        ProvenanceCondition(
                            "equal_quality",
                            0,
                            0,
                            "formula_operand",
                            value="matching_input_quality",
                            phase="operation_input",
                        ),
                        ProvenanceCondition(
                            "improvement",
                            0,
                            0,
                            "formula_operand",
                            value="normal_to_11_else_plus_1",
                            maximum=15,
                            phase="operation_outcome",
                        ),
                    ),
                )

    def authored_equipment(self) -> None:
        sims = {str(row["stable_key"]): row for row in self.rows("authored_sims")}
        populated: set[str] = set()
        references: dict[str, list[ProvenanceEvidence]] = defaultdict(list)
        for row in self.rows("authored_sim_references"):
            references[str(row["authored_sim_stable_key"])].append(
                self.evidence("authored_sim_references", row["source_component_key"], row["reference_index"])
            )
        for row in self.rows("authored_sim_equipment"):
            source, position = str(row["authored_sim_stable_key"]), row["position"]
            evidence = self.evidence("authored_sim_equipment", source, position)
            if not row["item_stable_key"]:
                self.input_exclusions[(evidence.input_relation, evidence.input_primary_key)] = (
                    "empty_authored_seed_slot"
                )
                continue
            sim = sims[source]
            populated.add(source)
            self.acquisition(
                "internal_equipment",
                str(row["item_stable_key"]),
                source,
                primary=("authored_seed", source, position),
                evidence=(evidence, self.evidence("authored_sims", source), *references[source]),
                quantity=1,
                player_access_state="internal_only",
                variant_key=str(position),
                mechanic="authored_sim_seed",
                probability_basis="not_applicable",
                conditions=(
                    ProvenanceCondition(
                        "seed_level",
                        0,
                        0,
                        "actor_level",
                        actor="sim",
                        minimum=sim["seed_level"],
                        maximum=sim["seed_level"],
                        phase="source_initialization",
                    ),
                    ProvenanceCondition(
                        "seed_class",
                        0,
                        0,
                        "actor_class",
                        "class:" + str(sim["seed_class_name"]).lower(),
                        actor="sim",
                        phase="source_initialization",
                    ),
                ),
            )
        for source in sims.keys() - populated:
            for evidence in (self.evidence("authored_sims", source), *references[source]):
                self.input_exclusions[(evidence.input_relation, evidence.input_primary_key)] = (
                    "empty_authored_seed_configuration"
                )

    def internal_aura_equipment(self) -> None:
        facts = {(str(row["fact_id"]), str(row["key"])): str(row["value"]) for row in self.rows("code_facts")}
        # code-fact: sim.aura_equipment_slot
        # code-fact: sim.aura_equipment_added
        # code-fact: sim.generated_equipment_slot_gate
        # code-fact: sim.generated_equipment_nonweapon_gate
        # code-fact: sim.generated_equipment_assignment
        required = (
            "sim.aura_equipment_slot",
            "sim.aura_equipment_added",
            "sim.generated_equipment_slot_gate",
            "sim.generated_equipment_nonweapon_gate",
            "sim.generated_equipment_assignment",
        )
        for fact_id in required:
            if facts.get((fact_id, "ok")) != "true":
                raise ValueError(f"Missing internal equipment evidence: {fact_id}")
        from .auction import ListingRules

        rules = ListingRules.from_facts(facts)
        classes: dict[str, set[str]] = defaultdict(set)
        for row in self.rows("item_classes"):
            classes[str(row["item_stable_key"])].add(str(row["class_name"]))
        for row in self.rows("items"):
            if (
                row["required_slot"] != "Aura"
                or row["sim_players_cant_get"]
                or not row["item_level"]
                or row["item_level"] <= 0
            ):
                continue
            item, level = str(row["stable_key"]), int(row["item_level"])
            for rival in (False, True):
                levels = [
                    actor
                    for actor in range(1, rules.sim_cap + 1)
                    if max(1, actor - 3)
                    <= level
                    <= min(
                        (45 if actor >= 35 else 37) if rival else 39,
                        actor + (6 if rival else 2 if actor > 10 else 1),
                    )
                ]
                if not levels:
                    continue
                for class_name in sorted(classes[item]):
                    scenario = "rival" if rival else "normal"
                    evidence: tuple[ProvenanceEvidence, ...] = (
                        self.evidence("items", item),
                        self.evidence("item_classes", item, class_name),
                    )
                    evidence += tuple(self.evidence("code_facts", fact_id, "ok") for fact_id in required)
                    evidence += (self.evidence("code_facts", "auction.sim_level_cap", "value"),)
                    self.acquisition(
                        "internal_equipment",
                        item,
                        "mechanic:simulated_equipment_generation",
                        primary=(item, class_name, scenario),
                        evidence=evidence,
                        quantity=1,
                        player_access_state="internal_only",
                        variant_key=identity("internal_gear", class_name, scenario),
                        mechanic="simulated_equipment_generation",
                        probability_basis="per_use",
                        conditions=(
                            ProvenanceCondition(
                                "actor_class", 0, 0, "actor_class", "class:" + class_name.lower(), actor="sim"
                            ),
                            ProvenanceCondition(
                                "actor_level",
                                0,
                                0,
                                "actor_level",
                                actor="sim",
                                minimum=min(levels),
                                maximum=max(levels),
                            ),
                            ProvenanceCondition("route", 0, 0, "route", value=scenario),
                            ProvenanceCondition("upgrade", 0, 0, "quality", value="improves_existing_equipment"),
                            ProvenanceCondition(
                                "actor_access", 0, 0, "route", value="not_gm_upgrades_enabled_not_demo"
                            ),
                        ),
                    )

    def raw_loot_evidence(self, raw: sqlite3.Connection, reviewed_unreachable: frozenset[str]) -> None:
        native = [dict(row) for row in raw.execute("SELECT * FROM LootDrops")]
        hosts = {
            str(row["StableKey"]): dict(row)
            for row in raw.execute("SELECT StableKey, DestroyOnDeath, DoNotLeaveCorpse, IsSimPlayer FROM Characters")
        }
        self.tables["raw.LootDrops"] = native
        self.tables["raw.Characters"] = list(hosts.values())
        items = {str(row["stable_key"]) for row in self.rows("items")}
        facts_by_input: dict[str, list[int]] = defaultdict(list)
        for index, fact in enumerate(self.acquisitions):
            for evidence in fact.evidence:
                if evidence.input_relation == "loot_drops":
                    facts_by_input[evidence.input_primary_key].append(index)
        clean_loot = {
            (str(row["character_stable_key"]), str(row["item_stable_key"])) for row in self.rows("loot_drops")
        }
        for row in native:
            copy, item = str(row["CharacterStableKey"]), str(row["ItemStableKey"])
            evidence = self.evidence("raw.LootDrops", row["LootTableStableKey"], item)
            clean_identity = _json((copy, item))
            for index in facts_by_input.get(clean_identity, ()):
                self.acquisitions[index] = replace(
                    self.acquisitions[index], evidence=(*self.acquisitions[index].evidence, evidence)
                )
            if clean_identity in facts_by_input:
                continue
            if (copy, item) in clean_loot:
                self.input_exclusions[(evidence.input_relation, evidence.input_primary_key)] = self.input_exclusions[
                    ("loot_drops", clean_identity)
                ]
                continue
            if item not in items:
                raise ValueError(f"Serialized loot references absent item: {copy!r}, {item!r}")
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
                raise ValueError(f"Unexplained serialized loot exclusion: {copy!r}, {item!r}")
            self.acquisition(
                "character_drop",
                item,
                self._groups.get(copy, copy),
                primary=("raw_excluded", row["LootTableStableKey"], item),
                evidence=(evidence,),
                chance=row["DropProbability"],
                player_access_state="non_acquirable",
                source_copy_stable_key=copy,
                source_group_key=self._groups.get(copy),
                probability_basis="per_kill",
                expected_quantity=row.get("ExpectedPerKill"),
                count_distribution=row.get("DropCountDistribution"),
                conditions=(ProvenanceCondition("loot_host", 0, 0, "never", value=reason),),
            )

    def smithing_byproducts(self, raw: sqlite3.Connection) -> None:
        cursor = raw.execute("SELECT * FROM NativeItemBindings")
        bindings = [dict(row) for row in cursor]
        self.tables["raw.NativeItemBindings"] = bindings
        selected = [row for row in bindings if row["BindingKey"] == "GameManager.PlanarShard"]
        if len(selected) != 1:
            raise ValueError("Smithing requires the refreshed native GameManager.PlanarShard binding")
        binding = selected[0]
        evidence = self.evidence("raw.NativeItemBindings", binding["BindingKey"])
        item = binding["ItemStableKey"]
        if item is None:
            self.input_exclusions[(evidence.input_relation, evidence.input_primary_key)] = (
                "empty_smithing_output_binding"
            )
            return
        if item not in self._items:
            raise ValueError(f"Native smithing output references absent item: {item}")
        removal = next(str(row["stable_key"]) for row in self.rows("items") if str(row["id"]) == "2298018")
        proof = self.require_facts(
            "smithing.blessing_outputs",
            "smithing.blessing_input_quality",
            "smithing.blessing_single_input",
        )
        outcome = self.acquisition(
            "crafting",
            str(item),
            removal,
            primary=(removal, "blessing_removal_byproduct", item),
            evidence=(evidence, self.evidence("items", removal), *proof),
            quantity=1,
            probability_basis="not_applicable",
            mechanic="remove_blessing",
            variant_key="blessing_removal_byproduct",
            conditions=(
                ProvenanceCondition(
                    "equipment_input",
                    0,
                    0,
                    "quality",
                    minimum=2,
                    maximum=3,
                    phase="operation_input",
                ),
            ),
        )
        for index, use in enumerate(self.uses):
            if use.mechanic in ("remove_blessing", "blessing_removal_material", "blessing_removal_fuel"):
                self.uses[index] = replace(
                    use,
                    outcome_key=outcome.acquisition_key,
                    evidence=tuple(dict.fromkeys((*use.evidence, evidence, *proof))),
                )

    def attach_native_inputs(self, raw: sqlite3.Connection) -> None:
        from .native_item_inputs import NativeItemInputs

        native = NativeItemInputs(raw, unavailable_loot_copies=frozenset(self._encountered - self._loot_capable))
        self.smithing_byproducts(raw)

        def attach[T: (ItemAcquisition, ItemUse)](family: list[T]) -> None:
            for index, fact in enumerate(family):
                evidence = list(fact.evidence)
                loot_pairs = {
                    tuple(json.loads(source.input_primary_key))
                    for source in fact.evidence
                    if source.input_relation == "loot_drops"
                }
                if isinstance(fact, ItemAcquisition) and fact.kind == "character_drop":
                    loot_pairs.add((fact.source_copy_stable_key, fact.item_stable_key))
                for primary in sorted(loot_pairs):
                    evidence.extend(native.evidence_for("character_drop", primary))
                if isinstance(fact, ItemAcquisition):
                    if fact.kind in ("mining", "fishing"):
                        primary = (
                            (fact.source_stable_key, fact.variant_key, fact.item_stable_key)
                            if fact.kind == "fishing"
                            else (fact.source_stable_key, fact.item_stable_key)
                        )
                    elif fact.kind == "fishing_bonus":
                        primary = (fact.item_stable_key,)
                    elif fact.kind == "special_world_drop":
                        primary = (fact.item_stable_key, fact.variant_key)
                    elif fact.kind == "item_drop":
                        primary = (fact.source_stable_key, fact.item_stable_key, fact.variant_key)
                    else:
                        primary = ()
                elif fact.kind == "item_drop":
                    primary = (fact.item_stable_key, fact.target_stable_key, fact.variant_key)
                else:
                    primary = ()
                if primary:
                    evidence.extend(native.evidence_for(fact.kind, primary))
                family[index] = replace(fact, evidence=tuple(dict.fromkeys(evidence)))

        attach(self.acquisitions)
        attach(self.uses)
        native.finalize()
        self.input_exclusions.update(native.input_exclusions)
        self.tables.update({f"raw.{table}": rows for table, rows in native.input_tables.items()})

    def attach_encounter_inputs(self) -> None:
        primaries = {
            "encounter_placements": ("encounter_key", "member_spawn_stable_key"),
            "encounter_conditions": ("encounter_key", "state_scope", "state_key"),
            "encounter_completions": ("encounter_key", "event_kind", "state_scope", "state_key"),
            "encounter_event_conditions": ("encounter_key", "event_kind", "state_scope", "state_key"),
        }
        by_encounter: dict[str, list[ProvenanceEvidence]] = defaultdict(list)
        by_spawn: dict[str, set[str]] = defaultdict(set)
        for row in self.rows("encounter_placements"):
            by_spawn[str(row["member_spawn_stable_key"])].add(str(row["encounter_key"]))
        encounters = set().union(*by_spawn.values()) if by_spawn else set()
        for table, columns in primaries.items():
            for row in self.rows(table):
                encounter = str(row["encounter_key"])
                if encounter not in encounters:
                    raise ValueError(f"Encounter configuration has no placement: {encounter}")
                by_encounter[encounter].append(self.evidence(table, *(row[column] for column in columns)))
        consumed: set[str] = set()

        def attach[T: (ItemAcquisition, ItemUse)](family: list[T]) -> None:
            for index, fact in enumerate(family):
                matching = {
                    encounter
                    for location in fact.locations
                    for encounter in by_spawn.get(str(location.coordinate_stable_key), ())
                }
                if not matching:
                    continue
                consumed.update(matching)
                evidence = list(fact.evidence)
                for encounter in sorted(matching):
                    evidence.extend(by_encounter[encounter])
                family[index] = replace(fact, evidence=tuple(dict.fromkeys(evidence)))

        attach(self.acquisitions)
        attach(self.uses)
        for encounter in encounters - consumed:
            for evidence in by_encounter[encounter]:
                self.input_exclusions[(evidence.input_relation, evidence.input_primary_key)] = "no_located_item_action"

    def account_support_inputs(self) -> None:
        self.attach_encounter_inputs()
        consumed = {
            (evidence.input_relation, evidence.input_primary_key)
            for fact in self.acquisitions
            for evidence in fact.evidence
        }
        consumed.update(
            (evidence.input_relation, evidence.input_primary_key) for use in self.uses for evidence in use.evidence
        )
        for row in self.rows("character_quest_manager_quests"):
            evidence = self.evidence("character_quest_manager_quests", row["character_stable_key"], row["quest_slot"])
            key = (evidence.input_relation, evidence.input_primary_key)
            if key not in consumed:
                self.input_exclusions[key] = (
                    "unencountered_copy"
                    if row["character_stable_key"] not in self._encountered
                    else "no_executed_item_grant"
                )
        for table, reason in (
            ("ui_item_access_targets", "unused_native_ui_target"),
            ("item_access_observations", "unused_access_observation"),
        ):
            for row in self.rows(table):
                primary = (
                    (row["component_type"], row["slot"], row["assembly_sha256"])
                    if table == "item_access_observations"
                    else (row["stable_key"],)
                )
                evidence = self.evidence(table, *primary)
                key = (evidence.input_relation, evidence.input_primary_key)
                if key not in consumed:
                    self.input_exclusions[key] = reason

    def select(self) -> None:
        self.loot()
        self.vendors_and_dialog()
        self.crafting()
        self.quests()
        self.gathering()
        self.item_operations()
        self.starting_and_auctions()
        self.ui_grants()
        self.smithing()
        self.internal_aura_equipment()
        self.authored_equipment()

    def persist(self) -> None:
        for family, facts, cls in (("acquisition", self.acquisitions, ItemAcquisition), ("use", self.uses, ItemUse)):
            table = "item_acquisitions" if family == "acquisition" else "item_uses"
            columns = [field.name for field in fields(cls) if field.name not in ("conditions", "locations", "evidence")]
            for fact in facts:
                owner = fact.acquisition_key if isinstance(fact, ItemAcquisition) else fact.use_key
                data = asdict(fact)
                fact_from_dict(data)
                self._insert(table, {column: data[column] for column in columns})
                for condition in data["conditions"]:
                    self._insert(f"item_{family}_conditions", {"owner_key": owner, **condition})
                for location_data in data["locations"]:
                    location_data["conditions"] = _json(location_data["conditions"])
                    location_data["entry_zone_line_keys"] = _json(location_data["entry_zone_line_keys"])
                    self._insert(f"item_{family}_locations", {"owner_key": owner, **location_data})
                for evidence in fact.evidence:
                    self.connection.execute(
                        "INSERT OR IGNORE INTO item_provenance_evidence VALUES (?,?,?)",
                        (owner, evidence.input_relation, evidence.input_primary_key),
                    )

    def _insert(self, table: str, data: dict[str, object]) -> None:
        self.connection.execute(
            f"INSERT INTO {table} ({','.join(data)}) VALUES ({','.join('?' for _ in data)})", tuple(data.values())
        )


def process_item_provenance(
    connection: sqlite3.Connection,
    lifecycle_path: Path,
    raw: sqlite3.Connection,
    *,
    reviewed_unreachable: frozenset[str],
) -> dict[str, object]:
    from erenshor.infrastructure.content_lifecycle import derive_item_dispositions, load_content_lifecycle

    from .item_provenance_coverage import validate_item_provenance

    evidence_path = lifecycle_path.parent / "item-access-evidence.json"
    access_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if access_evidence.get("schema_version") != 1:
        raise ValueError("Unsupported item access evidence schema")
    builder = ProvenanceBuilder(connection)
    for observation in access_evidence["observations"]:
        builder._insert(
            "item_access_observations", {"assembly_sha256": access_evidence["assembly_sha256"], **observation}
        )
    builder.select()
    builder.raw_loot_evidence(raw, reviewed_unreachable)
    builder.attach_native_inputs(raw)
    builder.account_support_inputs()
    builder.persist()
    lifecycle = load_content_lifecycle(lifecycle_path)
    current = {str(row["stable_key"]): row["wiki_page_name"] for row in builder.rows("items")}
    for disposition in derive_item_dispositions(lifecycle, current):
        data = asdict(disposition)
        data["current_pages"] = _json(data["current_pages"])
        data["former_pages"] = _json(data["former_pages"])
        builder._insert("item_dispositions", data)
    digests = {
        table: hashlib.sha256(_json(rows).encode()).hexdigest() for table, rows in sorted(builder.tables.items())
    }
    digests["content_lifecycle"] = hashlib.sha256(lifecycle_path.read_bytes()).hexdigest()
    digests["item_access_evidence"] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    digests["reviewed_loot_unreachable"] = hashlib.sha256(_json(sorted(reviewed_unreachable)).encode()).hexdigest()
    builds = connection.execute("SELECT game_build_id FROM code_facts_meta").fetchall()
    if len(builds) != 1 or not builds[0][0]:
        raise ValueError("Item provenance requires one source game build identity")
    connection.execute(
        "INSERT INTO item_provenance_meta VALUES (?,?,?)", (PROVENANCE_SCHEMA_VERSION, builds[0][0], _json(digests))
    )
    audit = validate_item_provenance(
        connection,
        builder.input_exclusions,
        raw=raw,
        reviewed_unreachable=reviewed_unreachable,
        lifecycle_path=lifecycle_path,
        require_all_native_tables=True,
    )
    # The writer vacuums after this post-insert expansion.
    connection.commit()
    return audit
