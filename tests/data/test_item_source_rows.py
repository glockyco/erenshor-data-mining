"""Shipping inputs are accounted for and stored sources use the shared public view."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from erenshor.application.processor.item_provenance import ProvenanceBuilder, select_item_provenance
from erenshor.application.processor.item_provenance_coverage import validate_item_provenance
from erenshor.application.processor.item_public_view import derive_public_view
from erenshor.infrastructure.content_lifecycle import derive_item_dispositions, load_content_lifecycle

_ROOT = Path(__file__).resolve().parents[2]


def _selection(clean_path: Path, raw_path: Path, reviewed: frozenset[str]) -> ProvenanceBuilder:
    """Repeat the clean build's selection in memory, because the database does not store which rows facts use."""
    with (
        closing(sqlite3.connect(f"file:{clean_path}?mode=ro", uri=True)) as clean,
        closing(sqlite3.connect(f"file:{raw_path}?mode=ro", uri=True)) as raw,
    ):
        clean.row_factory = raw.row_factory = sqlite3.Row
        return select_item_provenance(clean, raw, reviewed_unreachable=reviewed)


def test_every_populated_native_family_has_canonical_coverage(main_clean_db: Path, main_raw_db: Path) -> None:
    mapping = json.loads((_ROOT / "mapping.json").read_text(encoding="utf-8"))
    reviewed = frozenset(key for key, rule in mapping["rules"].items() if rule.get("loot_unreachable"))
    builder = _selection(main_clean_db, main_raw_db, reviewed)
    with (
        closing(sqlite3.connect(f"file:{main_clean_db}?mode=ro", uri=True)) as clean,
        closing(sqlite3.connect(f"file:{main_raw_db}?mode=ro", uri=True)) as raw,
    ):
        audit = validate_item_provenance(
            clean,
            builder,
            raw=raw,
            require_all_native_tables=True,
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
            "item_access_observations": "1",
            "items": "required_slot NOT IN ('General', 'Aura')",
            "item_classes": "1",
            "code_facts": "1",
        }
        for relation, predicate in families.items():
            count = clean.execute(f"SELECT COUNT(*) FROM {relation} WHERE {predicate}").fetchone()[0]
            assert count > 0, relation
            assert audit["input_counts"].get(relation, 0) > 0, relation
        assert raw.execute("SELECT COUNT(*) FROM LootDrops").fetchone()[0] > 0
        assert audit["input_counts"]["raw.LootDrops"] > 0
        for relation, direct_count in audit["direct_native_counts"].items():
            if not relation.startswith("raw."):
                continue
            table = relation.removeprefix("raw.")
            count = raw.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            assert direct_count == count > 0, relation
            assert audit["input_counts"].get(relation, 0) > 0, relation
        assert audit["contract_counts"]["acquisitions"] == len(builder.acquisitions) > 0
        assert audit["contract_counts"]["uses"] == len(builder.uses) > 0

        lifecycle = load_content_lifecycle(_ROOT / "content-lifecycle.json")
        current = dict(clean.execute("SELECT stable_key, wiki_page_name FROM items"))
        dispositions = tuple(derive_item_dispositions(lifecycle, current))
        assert audit["contract_counts"]["dispositions"] == len(dispositions) > 0
        public = derive_public_view(
            builder.acquisitions,
            builder.uses,
            dispositions,
            builder.fact_evidence,
            builder.mechanic_conditions(),
        )
        stored_keys = {row[0] for row in clean.execute("SELECT source_key FROM item_sources")}
        assert stored_keys == {source.source_key for source in public.sources}


def test_mechanism_conditions_are_shared_by_selected_facts(main_clean_db: Path, main_raw_db: Path) -> None:
    mapping = json.loads((_ROOT / "mapping.json").read_text(encoding="utf-8"))
    reviewed = frozenset(key for key, rule in mapping["rules"].items() if rule.get("loot_unreachable"))
    builder = _selection(main_clean_db, main_raw_db, reviewed)
    shared = builder.mechanic_conditions()
    assert shared
    for mechanic, conditions in shared.items():
        members = [fact for fact in (*builder.acquisitions, *builder.uses) if fact.mechanic == mechanic]
        assert len(members) > 1, mechanic
        assert conditions, mechanic
        for fact in members:
            assert set(conditions).issubset(fact.conditions), fact
