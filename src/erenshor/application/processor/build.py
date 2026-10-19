"""Top-level orchestrator for the Layer 2 clean database build.

Reads from the raw SQLite database (produced by ``extract export``) and
writes the clean SQLite database consumed by all downstream pipeline
components (wiki, sheets, map).

Processing order:
    1. Code facts             (no dependencies; gates on extract code-facts)
    2. World/placement tables (no dependencies)
    3. Zones                  (no dependencies)
    4. Factions               (no dependencies)
    5. Items                  (no dependencies)
    6. Spells                 (no dependencies)
    7. Skills                 (no dependencies)
    8. Stances                (no dependencies)
    9. Quests                 (depends on items, factions)
   10. Characters             (depends on all above)
   11. Pictures               (depends on the entity tables; reads the
                               export's textures and the approved captures)

Each step logs the entity counts so progress is visible.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

from .auction import process_auction_listings
from .authored_sims import process_authored_sims
from .characters import process_characters
from .code_facts import process_code_facts
from .combat_eligibility import process_combat_eligibility
from .encounters import process_encounters
from .entities import (
    process_class_starting_items,
    process_factions,
    process_items,
    process_quests,
    process_skills,
    process_spells,
    process_stances,
    process_world_tables,
    process_zones,
)
from .gates import process_gates
from .item_mechanics import process_item_mechanics
from .item_models import process_item_models
from .item_provenance import process_item_provenance
from .knowledge_base import process_knowledge_base
from .mapping import load_mapping, validate_character_name_overrides
from .navigation_contexts import process_zone_line_destinations
from .pictures import process_pictures
from .progression import process_progression
from .quest_routes import process_quest_routes
from .special_world_drops import process_common_world_items, process_special_world_drops
from .summons import process_summons
from .travel import process_travel
from .treasure import process_treasure
from .ui_items import process_ui_items
from .weather import process_weather
from .writer import Writer
from .zone_wide_spawns import process_zone_wide_spawns


def build(
    raw_db_path: Path,
    clean_db_path: Path,
    mapping_json_path: Path,
    barriers_path: Path,
    export_dir: Path,
    images_dir: Path,
) -> None:
    """Build the clean database from the raw export.

    Args:
        raw_db_path: Path to the raw SQLite database (``database_raw``).
        clean_db_path: Path where the clean database will be written
            (``database``).  Any existing file at this path is removed.
        mapping_json_path: Path to ``mapping.json``.
        barriers_path: Path to ``barriers.toml``, the reviewed list of what
            each keyed door guards.
        export_dir: The ripped Unity project (``ExportedProject``), whose
            textures hold the icons.
        images_dir: The variant's image directory, which holds the approved
            portrait captures and receives the picture catalog.

    Raises:
        FileNotFoundError: If ``raw_db_path``, ``mapping_json_path``, or
            ``barriers_path`` does not exist, or an icon texture or approved
            capture is missing.
        ValueError: If ``mapping.json`` or ``barriers.toml`` is malformed, a
            keyed door is not classified, an approved capture changed, or one
            wiki file title would name two pictures.
        sqlite3.Error: If the raw database cannot be opened.
    """
    if not raw_db_path.exists():
        raise FileNotFoundError(
            f"Raw database not found: {raw_db_path}\n"
            "Run 'erenshor extract export' to generate it, or copy the "
            "existing database to this path."
        )

    logger.info(f"Building clean DB from {raw_db_path}")
    logger.info(f"Output: {clean_db_path}")

    # Load mapping.json once; all processors share it.
    mapping, spawn_mapping = load_mapping(mapping_json_path)

    # Open raw DB (read-only).
    raw = sqlite3.connect(f"file:{raw_db_path}?mode=ro", uri=True)
    raw.row_factory = sqlite3.Row

    try:
        raw_npc_names = {
            str(row["StableKey"]): str(row["NPCName"] or "")
            for row in raw.execute("SELECT StableKey, NPCName FROM Characters")
        }
        validate_character_name_overrides(mapping, raw_npc_names)

        writer = Writer(clean_db_path)
        writer.create_schema()

        logger.info("Processing code facts...")
        process_code_facts(raw, writer)

        logger.info("Processing world/placement tables...")
        process_world_tables(raw, writer)

        logger.info("Processing zones...")
        process_zones(raw, writer, mapping)

        logger.info("Processing factions...")
        process_factions(raw, writer, mapping)

        logger.info("Processing items...")
        item_keys = process_items(raw, writer, mapping)

        logger.info("Processing class starting items...")
        process_class_starting_items(raw, writer, item_keys)

        logger.info("Processing authored SimPlayer defaults...")
        process_authored_sims(raw, writer)

        logger.info("Processing common world items...")
        process_common_world_items(raw, writer, item_keys)

        logger.info("Processing special world drops...")
        process_special_world_drops(raw, writer, item_keys)

        logger.info("Processing spells...")
        process_spells(raw, writer, mapping)

        logger.info("Processing scene weather and world state...")
        process_weather(raw, writer.conn)

        logger.info("Processing skills...")
        stance_images = process_skills(raw, writer, mapping)

        logger.info("Processing stances...")
        process_stances(raw, writer, mapping, stance_images)

        logger.info("Processing quests...")
        process_quests(raw, writer, mapping)

        logger.info("Processing characters...")
        process_characters(raw, writer, mapping, item_keys, spawn_mapping)

        logger.info("Processing combat eligibility...")
        process_combat_eligibility(raw, writer)

        logger.info("Processing encounter state and completion...")
        process_encounters(raw, writer)

        logger.info("Processing stored return destinations...")
        process_zone_line_destinations(raw, writer)

        logger.info("Processing native UI item sources...")
        process_ui_items(raw, writer.conn)

        logger.info("Processing gates...")
        process_gates(raw, writer, barriers_path)

        logger.info("Processing travel between zones...")
        route_total = process_travel(writer)
        logger.info(f"Travel routes: {route_total} rows")

        logger.info("Processing item mechanics...")
        process_item_mechanics(raw, writer)

        logger.info("Processing Auction House listings...")
        process_auction_listings(writer)

        logger.info("Processing treasure hunting...")
        process_treasure(raw, writer)

        # Summons need the placements of characters and the sites of dug-up chests.
        logger.info("Processing the characters that summon others...")
        summon_total = process_summons(raw, writer)
        logger.info(f"Character summons: {summon_total} rows")

        logger.info("Processing zone-wide spawn eligibility...")
        process_zone_wide_spawns(raw, writer)

        logger.info("Processing item models...")
        process_item_models(raw, writer)

        logger.info("Processing the chat knowledge base...")
        process_knowledge_base(raw, writer)

        logger.info("Processing pictures...")
        process_pictures(raw, writer, export_dir, images_dir)

        logger.info("Processing AE event mutations...")
        from erenshor.domain.constants.ae_event_mutations import AE_EVENT_MUTATIONS

        writer.insert_ae_event_mutations(AE_EVENT_MUTATIONS)
        logger.info(f"AE event mutations: {len(AE_EVENT_MUTATIONS)} rows")

        logger.info("Selecting canonical item provenance...")
        provenance_report = process_item_provenance(
            writer.conn,
            mapping_json_path.parent / "content-lifecycle.json",
            raw,
            reviewed_unreachable=frozenset(key for key, rule in mapping.items() if rule["loot_unreachable"]),
        )
        logger.info(f"Item provenance input coverage: {provenance_report}")

        logger.info("Selecting canonical quest routes...")
        route_count = process_quest_routes(writer.conn)
        logger.info(f"Quest routes: {route_count} rows")

        logger.info("Deriving progression requirements and playthrough tiers...")
        process_progression(writer.conn)

        logger.info("Finalising clean DB (VACUUM + ANALYZE)...")
        writer.finalize()

    finally:
        raw.close()

    logger.info("Clean DB build complete")
