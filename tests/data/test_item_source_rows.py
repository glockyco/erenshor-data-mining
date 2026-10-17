"""Shipping native inputs retain canonical identities, dimensions and explicit omissions."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from erenshor.application.processor.item_provenance_coverage import validate_item_provenance
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.item_provenance import ItemProvenanceRepository

_ROOT = Path(__file__).resolve().parents[2]


def _native_loot_omissions(connection: sqlite3.Connection) -> dict[tuple[str, str], str]:
    """Classify unused native origins without discarding recorded non-acquirable evidence."""
    reasons = dict(
        connection.execute(
            """
            SELECT source.StableKey,
                CASE
                    WHEN source.MiningNodeStableKey IS NOT NULL THEN 'non_world_mining_host'
                    WHEN host.StableKey IS NULL THEN 'loot_host_missing'
                    WHEN host.DestroyOnDeath THEN 'loot_host_destroy_on_death'
                    WHEN host.DoNotLeaveCorpse THEN 'loot_host_do_not_leave_corpse'
                    WHEN host.IsSimPlayer THEN 'non_player_host'
                    WHEN NOT EXISTS (
                        SELECT 1 FROM native.LootDrops outcome
                        WHERE outcome.LootTableStableKey = source.StableKey
                    ) THEN 'empty_native_loot_configuration'
                    WHEN NOT EXISTS (
                        SELECT 1 FROM character_fact_sources copy
                        WHERE copy.member_stable_key = source.CharacterStableKey
                    ) THEN 'unencountered_copy'
                END
            FROM native.LootTableSources source
            LEFT JOIN native.Characters host ON host.StableKey = source.CharacterStableKey
            """
        )
    )
    consumed = set(
        connection.execute(
            """
            SELECT input_relation, input_primary_key FROM item_provenance_evidence
            WHERE input_relation IN ('raw.LootDrops', 'raw.LootTableSources', 'raw.LootTablePoolSlots')
            """
        )
    )
    omissions: dict[tuple[str, str], str] = {}
    for relation, columns, source in (
        ("LootTableSources", "StableKey", "StableKey"),
        ("LootDrops", "LootTableStableKey, ItemStableKey", "LootTableStableKey"),
        ("LootTablePoolSlots", "LootTableStableKey, Pool, Position", "LootTableStableKey"),
    ):
        for row in connection.execute(f"SELECT {columns}, {source} FROM native.{relation}"):
            reason = reasons[row[-1]]
            if reason is not None:
                primary = json.dumps(tuple(row[:-1]), ensure_ascii=False, separators=(",", ":"))
                identity = "raw." + relation, primary
                if identity not in consumed:
                    omissions[identity] = reason
    return omissions


def _expected_omissions(connection: sqlite3.Connection) -> dict[tuple[str, str], str]:
    """Account for public native rows that do not execute an item acquisition."""
    omissions: dict[tuple[str, str], str] = {}
    queries = (
        (
            "loot_drops",
            "unencountered_copy",
            """
            SELECT character_stable_key, item_stable_key FROM loot_drops
            WHERE character_stable_key NOT IN (SELECT member_stable_key FROM character_fact_sources)
        """,
        ),
        (
            "character_dialogs",
            "unencountered_copy",
            """
            SELECT character_stable_key, dialog_index FROM character_dialogs
            WHERE give_item_stable_key IS NOT NULL
              AND character_stable_key NOT IN (SELECT member_stable_key FROM character_fact_sources)
        """,
        ),
        (
            "character_quest_manager_quests",
            "unencountered_copy",
            """
            SELECT character_stable_key, quest_slot FROM character_quest_manager_quests
            WHERE character_stable_key NOT IN (SELECT member_stable_key FROM character_fact_sources)
        """,
        ),
        (
            "character_quest_manager_quests",
            "no_executed_item_grant",
            """
            SELECT character_stable_key, quest_slot FROM character_quest_manager_quests q
            WHERE character_stable_key IN (SELECT member_stable_key FROM character_fact_sources)
              AND NOT EXISTS (SELECT 1 FROM quest_variants v
                  WHERE v.resource_name = q.quest_variant_resource_name AND v.item_on_complete_stable_key IS NOT NULL)
        """,
        ),
        (
            "quest_variants",
            "no_executed_item_grant",
            """
            SELECT resource_name FROM quest_variants v WHERE item_on_complete_stable_key IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM character_quest_manager_quests q
                  JOIN character_fact_sources s ON s.member_stable_key = q.character_stable_key
                  WHERE q.quest_variant_resource_name = v.resource_name)
        """,
        ),
        (
            "ui_item_sources",
            "empty_native_ui_slot",
            """
            SELECT stable_key FROM ui_item_sources WHERE
                CASE component_type WHEN 'ReplenishTMOGHide' THEN replenish_item_stable_key
                    WHEN 'PlanningTableUI' THEN serialized_item_stable_key END IS NULL
        """,
        ),
        (
            "authored_sims",
            "empty_authored_seed_configuration",
            """
            SELECT stable_key FROM authored_sims sim WHERE NOT EXISTS (
                SELECT 1 FROM authored_sim_equipment equipment
                WHERE equipment.authored_sim_stable_key = sim.stable_key AND equipment.item_stable_key IS NOT NULL
            )
        """,
        ),
        (
            "authored_sim_references",
            "empty_authored_seed_configuration",
            """
            SELECT source_component_key, reference_index FROM authored_sim_references reference WHERE NOT EXISTS (
                SELECT 1 FROM authored_sim_equipment equipment
                WHERE equipment.authored_sim_stable_key = reference.authored_sim_stable_key
                    AND equipment.item_stable_key IS NOT NULL
            )
        """,
        ),
        (
            "authored_sim_equipment",
            "empty_authored_seed_slot",
            "SELECT authored_sim_stable_key, position FROM authored_sim_equipment WHERE item_stable_key IS NULL",
        ),
        (
            "raw.MiningFallbackItems",
            "unused_mining_fallback",
            """
            SELECT SourceKey FROM native.MiningFallbackItems WHERE NOT EXISTS (
                SELECT 1 FROM native.MiningNodePoolSlots WHERE Pool = 'guarantee' AND ItemStableKey IS NULL
            )
        """,
        ),
        (
            "raw.SpecialWorldDropFlags",
            "native_world_drop_gate_disabled",
            "SELECT Name FROM native.SpecialWorldDropFlags WHERE Value = 0",
        ),
        (
            "raw.SpecialWorldDropItems",
            "native_world_drop_gate_disabled",
            """
            SELECT Pool, Position FROM native.SpecialWorldDropItems item WHERE EXISTS (
                SELECT 1 FROM native.SpecialWorldDropFlags flag WHERE flag.Value = 0
                    AND ((item.Pool IN ('Masks', 'MoloraiMask') AND flag.Name = 'DropMasks')
                        OR (item.Pool = 'Empty2' AND flag.Name = 'DemoBuild'))
            )
        """,
        ),
        (
            "raw.Waters",
            "empty_native_fishing_configuration",
            """
            SELECT StableKey FROM native.Waters water WHERE NOT EXISTS (
                SELECT 1 FROM native.WaterFishables fish WHERE fish.WaterStableKey = water.StableKey
                    AND (fish.ItemStableKey IS NOT NULL OR EXISTS (
                        SELECT 1 FROM native.SpecialWorldDropItems
                        WHERE Pool = 'Maps' AND Position < 4 AND ItemStableKey IS NOT NULL
                    ))
            )
        """,
        ),
    )
    for relation, reason, query in queries:
        for row in connection.execute(query):
            primary = json.dumps(tuple(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            omissions[relation, primary] = reason
    for relation, columns, reason in (
        ("ui_item_access_targets", "stable_key", "unused_native_ui_target"),
        ("ui_item_access_activations", "stable_key", "unused_native_ui_activation"),
        ("item_access_observations", "component_type, slot, assembly_sha256", "unused_access_observation"),
    ):
        for row in connection.execute(f"SELECT {columns} FROM {relation}"):
            primary = json.dumps(tuple(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            used = connection.execute(
                "SELECT COUNT(*) FROM item_provenance_evidence WHERE input_relation = ? AND input_primary_key = ?",
                (relation, primary),
            ).fetchone()[0]
            if not used:
                omissions[relation, primary] = reason
    omissions.update(_native_loot_omissions(connection))
    return omissions


def test_every_populated_native_family_has_canonical_coverage(main_clean_db: Path, main_raw_db: Path) -> None:
    mapping = json.loads((_ROOT / "mapping.json").read_text(encoding="utf-8"))
    reviewed = frozenset(key for key, rule in mapping["rules"].items() if rule.get("loot_unreachable"))
    with closing(sqlite3.connect(main_clean_db)) as clean, closing(sqlite3.connect(main_raw_db)) as raw:
        clean.execute("ATTACH DATABASE ? AS native", (str(main_raw_db),))
        audit = validate_item_provenance(
            clean,
            _expected_omissions(clean),
            raw=raw,
            require_all_native_tables=True,
            reviewed_unreachable=reviewed,
            lifecycle_path=_ROOT / "content-lifecycle.json",
        )
        families = {
            "loot_drops": "1",
            "special_world_drops": "1",
            "vendor_offers": "1",
            "character_dialogs": "give_item_stable_key IS NOT NULL",
            "crafting_rewards": "1",
            "crafting_recipes": "1",
            "character_quest_manager_quests": "1",
            "quest_variants": "item_on_complete_stable_key IS NOT NULL",
            "quest_required_items": "1",
            "mining_node_items": "1",
            "water_fishables": "1",
            "fishing_bonus_catches": "1",
            "item_bags": "item_stable_key IS NOT NULL",
            "item_drops": "1",
            "spell_created_items": "1",
            "item_conversions": "1",
            "item_zone_restrictions": "1",
            "quality_offerings": "1",
            "class_starting_items": "1",
            "auction_house_items": "1",
            "ui_item_sources": "1",
            "ui_item_access_targets": "1",
            "ui_item_access_activations": "1",
            "item_access_observations": "1",
            "items": "required_slot NOT IN ('General', 'Aura')",
            "item_classes": "1",
            "code_facts": "1",
        }
        populated = 0
        for relation, predicate in families.items():
            count = clean.execute(f"SELECT COUNT(*) FROM {relation} WHERE {predicate}").fetchone()[0]
            if count:
                assert audit["input_counts"].get(relation, 0) > 0, relation
                populated += 1
        assert populated > 0
        assert raw.execute("SELECT COUNT(*) FROM LootDrops").fetchone()[0] > 0
        assert audit["input_counts"]["raw.LootDrops"] > 0
        blocked_drops = clean.execute(
            """
            SELECT drop_row.LootTableStableKey, drop_row.ItemStableKey
            FROM native.LootDrops drop_row
            JOIN native.Characters host ON host.StableKey = drop_row.CharacterStableKey
            WHERE host.DestroyOnDeath OR host.DoNotLeaveCorpse OR host.IsSimPlayer
            """
        ).fetchall()
        assert blocked_drops
        for identity in blocked_drops:
            primary = json.dumps(tuple(identity), ensure_ascii=False, separators=(",", ":"))
            assert (
                clean.execute(
                    """
                SELECT COUNT(*) FROM item_provenance_evidence
                WHERE input_relation = 'raw.LootDrops' AND input_primary_key = ?
                """,
                    (primary,),
                ).fetchone()[0]
                > 0
            )

    with DatabaseConnection(main_clean_db, read_only=True) as db:
        provenance = ItemProvenanceRepository(db)
        acquisitions = list(provenance.iter_acquisitions())
        uses = list(provenance.iter_uses())
        assert len(acquisitions) == audit["contract_counts"]["acquisitions"] > 0
        assert len(uses) == audit["contract_counts"]["uses"] > 0
        acquisitions_by_item = {}
        uses_by_item = {}
        for acquisition in acquisitions:
            acquisitions_by_item.setdefault(acquisition.item_stable_key, []).append(acquisition)
        for use in uses:
            uses_by_item.setdefault(use.item_stable_key, []).append(use)
        for item_key in acquisitions_by_item.keys() | uses_by_item.keys():
            assert provenance.get_acquisitions(item_key) == acquisitions_by_item.get(item_key, [])
            assert provenance.get_uses(item_key) == uses_by_item.get(item_key, [])
            assert provenance.get_disposition(item_key) is not None
