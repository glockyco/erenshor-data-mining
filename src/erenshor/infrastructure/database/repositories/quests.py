"""Quest repository for specialized quest queries."""

from typing import cast

from loguru import logger

from erenshor.domain.entities.quest import Quest
from erenshor.domain.value_objects.faction import FactionModifier
from erenshor.domain.value_objects.item_provenance import ItemAcquisition
from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository
from erenshor.infrastructure.database.repository import BaseRepository, RepositoryError


class QuestRepository(BaseRepository[Quest]):
    """Read quest entities and panels with canonical item acquisition and use facts."""

    def get_quests_for_wiki_generation(self) -> list[Quest]:
        """Get all quests for local Lua data module generation."""
        query = """
            SELECT *
            FROM quests
            ORDER BY display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, ())
            quests = [Quest.model_validate(dict(row)) for row in rows]
            logger.debug(f"Retrieved {len(quests)} quests for wiki generation")
            return quests
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve quests for wiki: {e}") from e

    def get_faction_changes_for_quests(self, stable_keys: list[str]) -> dict[str, list[FactionModifier]]:
        """Get display-ready faction changes for Lua quest data."""
        if not stable_keys:
            return {}

        placeholders = ",".join("?" for _ in stable_keys)
        query = f"""
            SELECT
                qv.quest_stable_key,
                qfa.faction_stable_key,
                qfa.modifier_value,
                f.display_name AS faction_display_name,
                f.wiki_page_name AS faction_wiki_page_name
            FROM quest_variants qv
            JOIN quest_faction_affects qfa ON qfa.quest_variant_resource_name = qv.resource_name
            JOIN factions f ON f.stable_key = qfa.faction_stable_key
            WHERE qv.quest_stable_key IN ({placeholders})
            ORDER BY qv.quest_stable_key, f.display_name COLLATE NOCASE
        """

        try:
            rows = self._execute_raw(query, tuple(stable_keys))
            changes: dict[str, list[FactionModifier]] = {stable_key: [] for stable_key in stable_keys}
            for row in rows:
                changes[str(row["quest_stable_key"])].append(
                    FactionModifier(
                        faction_stable_key=str(row["faction_stable_key"]),
                        modifier_value=int(row["modifier_value"]),
                        faction_display_name=str(row["faction_display_name"]),
                        faction_wiki_page_name=row["faction_wiki_page_name"],
                    )
                )
            return changes
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve quest faction changes: {e}") from e

    def get_quest_panel_rows(self) -> dict[str, list[dict[str, object]]]:
        """Project persisted item facts alongside configured quest execution metadata.

        Resource metadata describes TradeWindow effects only when a turn-in route
        exists. An item grant additionally needs its exact canonical native route.
        """
        try:
            quests = self._execute_raw(
                "SELECT stable_key FROM quests WHERE wiki_page_name IS NOT NULL ORDER BY stable_key", ()
            )
            panels: dict[str, list[dict[str, object]]] = {str(row["stable_key"]): [] for row in quests}
            provenance = ItemProvenanceRepository(self.db)
            acquisitions = [fact for fact in provenance.iter_acquisitions() if fact.kind in {"quest_reward", "dialog"}]
            uses = [fact for fact in provenance.iter_uses() if fact.kind == "quest_requirement"]
            rewards: dict[tuple[str, str], list[ItemAcquisition]] = {}
            for fact in acquisitions:
                if fact.kind == "quest_reward" and fact.source_stable_key and fact.variant_key:
                    rewards.setdefault((fact.source_stable_key, fact.variant_key), []).append(fact)
            variants = [
                dict(row)
                for row in self._execute_raw(
                    """
                    SELECT qv.*, COALESCE((
                        SELECT SUM(quantity) FROM quest_required_items r
                        WHERE r.quest_variant_resource_name = qv.resource_name
                    ), 0) AS required_count
                    FROM quest_variants qv ORDER BY resource_name
                    """,
                    (),
                )
            ]
            variant_quests = {str(row["resource_name"]): str(row["quest_stable_key"]) for row in variants}
            for variant in variants:
                quest_key = str(variant["quest_stable_key"])
                if quest_key not in panels:
                    continue
                row: dict[str, object] = {
                    "type": "variant",
                    "variant": variant["resource_name"],
                    "experience": variant["xp_on_complete"],
                    "gold": variant["gold_on_complete"],
                    "repeatable": bool(variant["repeatable"]),
                    "oncePerSpawn": bool(variant["once_per_spawn_instance"]),
                    "partialAssigns": bool(
                        variant["assign_this_quest_on_partial_complete"]
                        and variant["dialog_on_partial_success"]
                        and cast("int", variant["required_count"]) > 1
                    ),
                    "killsHolder": bool(variant["kill_turn_in_holder"]),
                    "dropsInvulnerability": bool(variant["drop_invuln_on_holder"]),
                }
                item_rewards = rewards.get((quest_key, str(variant["resource_name"])), [])
                if item_rewards:
                    outcomes = {(fact.item_stable_key, self._reward_quantity(fact)) for fact in item_rewards}
                    if len(outcomes) != 1:
                        raise RepositoryError(f"Conflicting canonical rewards for {variant['resource_name']}")
                    row["item"], row["quantity"] = next(iter(outcomes))
                for column, field in (
                    ("assign_new_quest_on_complete_stable_key", "nextQuest"),
                    ("unlock_item_for_vendor_stable_key", "unlocksItem"),
                ):
                    if variant[column]:
                        row[field] = variant[column]
                panels[quest_key].append(row)

            for query, row_type, fields in (
                (
                    "SELECT * FROM quest_faction_affects ORDER BY quest_variant_resource_name, faction_stable_key",
                    "faction",
                    {"faction_stable_key": "faction", "modifier_value": "amount"},
                ),
                (
                    "SELECT * FROM quest_complete_other_quests "
                    "ORDER BY quest_variant_resource_name, completed_quest_stable_key",
                    "completes",
                    {"completed_quest_stable_key": "quest"},
                ),
            ):
                for record in self._execute_raw(query, ()):
                    variant_key = str(record["quest_variant_resource_name"])
                    quest_key = variant_quests[variant_key]
                    if quest_key in panels:
                        panels[quest_key].append(
                            {"type": row_type, "variant": variant_key}
                            | {field: record[column] for column, field in fields.items()}
                        )
            for use in sorted(
                uses,
                key=lambda fact: (
                    fact.variant_key or "",
                    -1 if fact.material_slot is None else fact.material_slot,
                    fact.item_stable_key,
                    fact.use_key,
                ),
            ):
                if use.target_stable_key is None or use.target_stable_key not in panels:
                    continue
                if use.quantity_min != use.quantity_max or use.quantity_min is None:
                    raise RepositoryError(f"Quest requirement {use.use_key} has no exact quantity")
                panels[use.target_stable_key].append(
                    {
                        "type": "required",
                        "variant": use.variant_key,
                        "requiredSlot": use.material_slot,
                        "item": use.item_stable_key,
                        "quantity": int(use.quantity_min),
                    }
                )

            self._add_panel_sources(panels, variants, acquisitions)
            turnin_quests = {
                key
                for key, rows in panels.items()
                if any(row["type"] == "completion" and row["method"] == "item_turnin" for row in rows)
            }
            for key, rows in panels.items():
                for row in rows:
                    if row["type"] != "variant":
                        continue
                    if key in turnin_quests:
                        row["rewardMethod"] = "item_turnin"
                    else:
                        # FinishQuest does not execute the resource's TradeWindow effects.
                        row["experience"] = 0
                        row["gold"] = 0
                        row.pop("item", None)
                        row.pop("quantity", None)
                        for flag in ("oncePerSpawn", "partialAssigns", "killsHolder", "dropsInvulnerability"):
                            row[flag] = False
                panels[key] = [
                    row
                    for row in rows
                    if not (key not in turnin_quests and row["type"] in {"required", "completes"})
                    and not (
                        row["type"] == "completion" and row["method"] == "chain" and row["source"] not in turnin_quests
                    )
                ]
            return panels
        except Exception as e:
            raise RepositoryError(f"Failed to retrieve quest panels: {e}") from e

    @staticmethod
    def _reward_quantity(fact: ItemAcquisition) -> int:
        if fact.quantity_min is None or fact.quantity_min != fact.quantity_max:
            raise RepositoryError(f"Quest item grant {fact.acquisition_key} has no exact quantity")
        return int(fact.quantity_min)

    @staticmethod
    def _append_item_route(
        panels: dict[str, list[dict[str, object]]],
        quest_key: str,
        route: dict[str, object],
        fact: ItemAcquisition,
    ) -> None:
        """Furniture is a property of the canonical grant's alternative placements."""
        alternatives = [
            [atom for atom in (*fact.conditions, *location.conditions) if atom.predicate == "room_furnished"]
            for location in fact.locations
        ]
        if not alternatives or any(not atoms for atoms in alternatives):
            panels[quest_key].append(route)
            return
        seen: set[tuple[str | None, str | None]] = set()
        for atoms in alternatives:
            for atom in atoms:
                condition = (atom.reference_stable_key, atom.reference_slot)
                if condition not in seen:
                    seen.add(condition)
                    panels[quest_key].append(
                        route | {"furniture": atom.reference_stable_key, "room": atom.reference_slot}
                    )

    def _add_panel_sources(
        self,
        panels: dict[str, list[dict[str, object]]],
        variants: list[dict[str, object]],
        acquisitions: list[ItemAcquisition],
    ) -> None:
        """Keep dialog gates and item grants on their exact source route."""
        characters = self._execute_raw(
            """
            WITH representatives AS (
                SELECT group_key, MIN(member_stable_key) AS stable_key
                FROM character_deduplications WHERE is_wiki_generated = 1 GROUP BY group_key
            )
            SELECT s.member_stable_key, r.stable_key
            FROM character_fact_sources s
            JOIN representatives r ON r.group_key = s.group_key
            """,
            (),
        )
        source_characters = {str(row["member_stable_key"]): row["stable_key"] for row in characters}
        placements: dict[str, list[dict[str, object]]] = {}
        for placement in self._execute_raw(
            """
            SELECT DISTINCT character_stable_key, furniture_item_stable_key, furniture_slot
            FROM character_spawns
            WHERE character_stable_key IN (
                SELECT source_stable_key FROM quest_acquisition_sources WHERE source_type = 'character'
                UNION
                SELECT source_stable_key FROM quest_completion_sources WHERE source_type = 'character'
            )
            ORDER BY character_stable_key, furniture_item_stable_key, furniture_slot
            """,
            (),
        ):
            condition = (
                {"furniture": placement["furniture_item_stable_key"], "room": placement["furniture_slot"]}
                if placement["furniture_item_stable_key"]
                else {}
            )
            placements.setdefault(str(placement["character_stable_key"]), []).append(condition)

        def append_route(quest_key: str, route: dict[str, object]) -> None:
            conditions = placements.get(str(route.get("sourceCopy")), [{}])
            # An unconditional placement needs no furniture qualifier.
            if {} in conditions:
                panels[quest_key].append(route)
            else:
                panels[quest_key].extend(route | condition for condition in conditions)

        dialogs = [
            dict(row)
            for row in self._execute_raw(
                "SELECT * FROM character_dialogs ORDER BY character_stable_key, dialog_index", ()
            )
        ]
        dialog_rewards = {
            (fact.source_copy_stable_key, fact.variant_key): fact for fact in acquisitions if fact.kind == "dialog"
        }
        trade_rewards = [fact for fact in acquisitions if fact.kind == "quest_reward"]
        for table, row_type, dialog_column in (
            ("quest_acquisition_sources", "acquisition", "assign_quest_stable_key"),
            ("quest_completion_sources", "completion", "complete_quest_stable_key"),
        ):
            sources = self._execute_raw(
                f"SELECT DISTINCT * FROM {table} ORDER BY quest_stable_key, method, source_stable_key, note",
                (),
            )
            for source in sources:
                quest_key = str(source["quest_stable_key"])
                if quest_key not in panels:
                    continue
                source_key = source["source_stable_key"]
                source_kind = source["source_type"]
                method = source["method"]
                row: dict[str, object] = {"type": row_type, "method": method}
                if method == "item_turnin" and any(
                    fact.source_stable_key == quest_key and fact.source_copy_stable_key == source_key
                    for fact in trade_rewards
                ):
                    continue
                if source_kind == "character":
                    if source_key not in source_characters:
                        continue
                    row["sourceCopy"] = source_key
                    row["source"] = source_characters[source_key]
                    row["sourceKind"] = "character"
                elif source_key:
                    row["source"] = source_key
                    row["sourceKind"] = source_kind
                if source["note"]:
                    row["note"] = source["note"]
                if method in {"dialog", "talk"}:
                    matching = [
                        dialog
                        for dialog in dialogs
                        if dialog["character_stable_key"] == source_key and dialog[dialog_column] == quest_key
                    ]
                    for dialog in matching:
                        route = row | {"dialogIndex": dialog["dialog_index"]}
                        if dialog["give_item_stable_key"]:
                            route["notOwnedItem"] = dialog["give_item_stable_key"]
                        gift = dialog_rewards.get((str(source_key), str(dialog["dialog_index"])))
                        if row_type == "completion" and gift is not None:
                            route["item"] = gift.item_stable_key
                            route["quantity"] = self._reward_quantity(gift)
                            route["acquisitionKey"] = gift.acquisition_key
                        assigned_quest = dialog["assign_quest_stable_key"]
                        if assigned_quest:
                            repeat_flags = {
                                bool(variant["repeatable"])
                                for variant in variants
                                if variant["quest_stable_key"] == assigned_quest
                            }
                            if len(repeat_flags) != 1:
                                raise RepositoryError(
                                    f"Cannot resolve dialog {source_key}:{dialog['dialog_index']} "
                                    f"assignment gate for {assigned_quest}"
                                )
                            if False in repeat_flags:
                                route["blockedByQuest"] = assigned_quest
                        if dialog["keywords"]:
                            route["keywords"] = dialog["keywords"]
                        if dialog["required_quest_stable_key"]:
                            route["prerequisite"] = dialog["required_quest_stable_key"]
                        if row_type == "completion" and gift is not None:
                            self._append_item_route(panels, quest_key, route, gift)
                        else:
                            append_route(quest_key, route)
                    if matching:
                        continue
                if method == "quest_chain":
                    matching_variants = [
                        variant
                        for variant in variants
                        if variant["quest_stable_key"] == source_key
                        and variant["assign_new_quest_on_complete_stable_key"] == quest_key
                    ]
                    for variant in matching_variants:
                        append_route(quest_key, row | {"sourceVariant": variant["resource_name"]})
                    if matching_variants:
                        continue
                if method == "partial_turnin":
                    for variant in variants:
                        if (
                            variant["quest_stable_key"] == quest_key
                            and variant["assign_this_quest_on_partial_complete"]
                            and variant["dialog_on_partial_success"]
                            and cast("int", variant["required_count"]) > 1
                        ):
                            append_route(quest_key, row | {"variant": variant["resource_name"]})
                    continue
                append_route(quest_key, row)
        for fact in trade_rewards:
            if fact.source_stable_key is None or fact.source_stable_key not in panels:
                continue
            quest_key = fact.source_stable_key
            source = source_characters.get(str(fact.source_copy_stable_key), fact.source_group_key)
            if not source:
                raise RepositoryError(f"Quest item grant {fact.acquisition_key} has no character source")
            route = {
                "type": "completion",
                "method": "item_turnin",
                "variant": fact.variant_key,
                "source": source,
                "sourceKind": "character",
                "sourceCopy": fact.source_copy_stable_key,
                "mechanic": fact.mechanic,
                "acquisitionKey": fact.acquisition_key,
                "item": fact.item_stable_key,
                "quantity": self._reward_quantity(fact),
            }
            self._append_item_route(panels, quest_key, route, fact)
