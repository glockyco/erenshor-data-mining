"""Quest repository for specialized quest queries."""

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
        """Present canonical quest routes and their item grants as wiki panel rows."""
        try:
            quests = self._execute_raw(
                "SELECT stable_key FROM quests WHERE wiki_page_name IS NOT NULL ORDER BY stable_key", ()
            )
            panels: dict[str, list[dict[str, object]]] = {str(row["stable_key"]): [] for row in quests}
            routes = [
                dict(row)
                for row in self._execute_raw(
                    "SELECT * FROM quest_routes ORDER BY phase DESC, quest_stable_key, method, "
                    "source_stable_key, note, variant_resource_name, dialog_index",
                    (),
                )
            ]
            reward_routes = {
                (row["quest_stable_key"], row["variant_resource_name"], row["source_stable_key"])
                for row in routes
                if row["grants_resource_rewards"]
            }
            rewarded_variants = {(quest, variant) for quest, variant, _ in reward_routes}
            partial_variants = {
                (row["quest_stable_key"], row["variant_resource_name"])
                for row in routes
                if row["phase"] == "start" and row["method"] == "partial_turnin"
            }
            provenance = ItemProvenanceRepository(self.db)
            acquisitions = [fact for fact in provenance.iter_acquisitions() if fact.kind in {"quest_reward", "dialog"}]
            uses = [fact for fact in provenance.iter_uses() if fact.kind == "quest_requirement"]
            rewards: dict[tuple[str, str], list[ItemAcquisition]] = {}
            for fact in acquisitions:
                if (
                    fact.kind == "quest_reward"
                    and (fact.source_stable_key, fact.variant_key, fact.source_copy_stable_key) in reward_routes
                ):
                    rewards.setdefault((str(fact.source_stable_key), str(fact.variant_key)), []).append(fact)
            variants = [
                dict(row)
                for row in self._execute_raw(
                    "SELECT * FROM quest_variants ORDER BY resource_name",
                    (),
                )
            ]
            variant_quests = {str(row["resource_name"]): str(row["quest_stable_key"]) for row in variants}
            for variant in variants:
                quest_key = str(variant["quest_stable_key"])
                if quest_key not in panels:
                    continue
                grants_rewards = (quest_key, variant["resource_name"]) in rewarded_variants
                row: dict[str, object] = {
                    "type": "variant",
                    "variant": variant["resource_name"],
                    "experience": variant["xp_on_complete"] if grants_rewards else 0,
                    "gold": variant["gold_on_complete"] if grants_rewards else 0,
                    "repeatable": bool(variant["repeatable"]),
                    "oncePerSpawn": bool(grants_rewards and variant["once_per_spawn_instance"]),
                    "partialAssigns": bool(
                        grants_rewards and (quest_key, variant["resource_name"]) in partial_variants
                    ),
                    "killsHolder": bool(grants_rewards and variant["kill_turn_in_holder"]),
                    "dropsInvulnerability": bool(grants_rewards and variant["drop_invuln_on_holder"]),
                }
                if grants_rewards:
                    row["rewardMethod"] = "item_turnin"
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
                        if row_type == "completes" and (quest_key, variant_key) not in rewarded_variants:
                            continue
                        child: dict[str, object] = {"type": row_type, "variant": variant_key}
                        child.update({field: record[column] for column, field in fields.items()})
                        panels[quest_key].append(child)
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
                if (use.target_stable_key, use.variant_key) not in rewarded_variants:
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

            self._add_panel_sources(panels, routes, acquisitions)
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
        routes: list[dict[str, object]],
        acquisitions: list[ItemAcquisition],
    ) -> None:
        """Join route facts to wiki representatives and placement qualifiers."""
        representatives = {
            str(row["group_key"]): row["stable_key"]
            for row in self._execute_raw(
                "SELECT group_key, MIN(member_stable_key) AS stable_key "
                "FROM character_deduplications WHERE is_wiki_generated = 1 GROUP BY group_key",
                (),
            )
        }
        placements: dict[str, list[dict[str, object]]] = {}
        for placement in self._execute_raw(
            "SELECT DISTINCT character_stable_key, furniture_item_stable_key, furniture_slot "
            "FROM character_spawns WHERE character_stable_key IN ("
            "SELECT source_stable_key FROM quest_routes WHERE source_kind = 'character') "
            "ORDER BY character_stable_key, furniture_item_stable_key, furniture_slot",
            (),
        ):
            qualifier = (
                {"furniture": placement["furniture_item_stable_key"], "room": placement["furniture_slot"]}
                if placement["furniture_item_stable_key"]
                else {}
            )
            placements.setdefault(str(placement["character_stable_key"]), []).append(qualifier)
        conditions: dict[str, dict[str, object]] = {}
        fields = {"quest_done": "prerequisite", "quest_not_done": "blockedByQuest", "item_not_owned": "notOwnedItem"}
        for atom in self._execute_raw(
            "SELECT * FROM quest_route_conditions ORDER BY route_key, gate_key, group_index, atom_index", ()
        ):
            if atom["atom_kind"] not in fields or atom["group_index"] != 0:
                raise RepositoryError(f"Cannot present quest route condition {dict(atom)}")
            target = conditions.setdefault(str(atom["route_key"]), {})
            field = fields[atom["atom_kind"]]
            if field in target and target[field] != atom["atom_stable_key"]:
                raise RepositoryError(f"Cannot present multiple {field} conditions for route {atom['route_key']}")
            target[field] = atom["atom_stable_key"]
        trade_rewards: dict[tuple[str | None, str | None, str | None], list[ItemAcquisition]] = {}
        dialog_rewards: dict[tuple[str | None, str | None], ItemAcquisition] = {}
        for fact in acquisitions:
            if fact.kind == "quest_reward":
                trade_rewards.setdefault(
                    (fact.source_stable_key, fact.source_copy_stable_key, fact.variant_key), []
                ).append(fact)
            else:
                dialog_rewards[(fact.source_copy_stable_key, fact.variant_key)] = fact
        rewarded_sources = {
            (route["quest_stable_key"], route["source_stable_key"])
            for route in routes
            if route["grants_resource_rewards"]
            and (route["quest_stable_key"], route["source_stable_key"], route["variant_resource_name"]) in trade_rewards
        }
        generic_rows: set[tuple[object, ...]] = set()
        grants: list[tuple[str, dict[str, object], ItemAcquisition]] = []
        for route in routes:
            quest = str(route["quest_stable_key"])
            if quest not in panels:
                continue
            row: dict[str, object] = {
                "type": "acquisition" if route["phase"] == "start" else "completion",
                "method": route["method"],
            }
            source = str(route["source_stable_key"]) if route["source_stable_key"] is not None else None
            resource = str(route["variant_resource_name"]) if route["variant_resource_name"] is not None else None
            group = route["source_group_key"]
            rewards = trade_rewards.get((quest, source, resource), []) if route["grants_resource_rewards"] else []
            if route["source_kind"] == "character":
                representative = representatives.get(str(group))
                if not representative and not rewards:
                    continue
                row.update(sourceCopy=source, source=representative or group, sourceKind="character")
            elif source:
                row.update(source=source, sourceKind=route["source_kind"])
            for column, field in (("dialog_index", "dialogIndex"), ("keywords", "keywords"), ("note", "note")):
                if route[column] is not None:
                    row[field] = route[column]
            row.update(conditions.get(str(route["route_key"]), {}))
            if resource is not None and not route["grants_resource_rewards"]:
                row["sourceVariant" if route["method"] == "quest_chain" else "variant"] = resource
            if rewards:
                for fact in rewards:
                    grants.append(
                        (
                            quest,
                            {
                                "type": "completion",
                                "method": route["method"],
                                "variant": resource,
                                "source": row["source"],
                                "sourceKind": "character",
                                "sourceCopy": source,
                                "mechanic": fact.mechanic,
                                "acquisitionKey": fact.acquisition_key,
                                "item": fact.item_stable_key,
                                "quantity": self._reward_quantity(fact),
                            },
                            fact,
                        )
                    )
                continue
            if route["grants_resource_rewards"]:
                # The panel collapses resource variants without item grants to one source row.
                if (quest, source) in rewarded_sources:
                    continue
                identity = (quest, *tuple(sorted(row.items())))
                if identity in generic_rows:
                    continue
                generic_rows.add(identity)
            gift = dialog_rewards.get((source, str(route["dialog_index"])))
            if route["phase"] == "completion" and gift is not None:
                row.update(
                    item=gift.item_stable_key, quantity=self._reward_quantity(gift), acquisitionKey=gift.acquisition_key
                )
                self._append_item_route(panels, quest, row, gift)
                continue
            qualifiers = placements.get(str(source), [{}])
            if {} in qualifiers:
                panels[quest].append(row)
            else:
                panels[quest].extend(row | qualifier for qualifier in qualifiers)
        for quest, row, fact in sorted(grants, key=lambda grant: (grant[2].item_stable_key, grant[2].acquisition_key)):
            self._append_item_route(panels, quest, row, fact)
