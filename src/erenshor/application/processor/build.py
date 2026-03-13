"""Top-level orchestrator for the Layer 2 clean database build.

Reads from the raw SQLite database (produced by ``extract export``) and
writes the clean SQLite database consumed by all downstream pipeline
components (wiki, sheets, map).

Processing order:
    1. World/placement tables  (no dependencies)
    2. Zones                   (no dependencies)
    3. Factions                (no dependencies)
    4. Items                   (no dependencies)
    5. Spells                  (no dependencies)
    6. Skills                  (no dependencies)
    7. Stances                 (no dependencies)
    8. Quests                  (depends on items, factions)
    9. Characters              (depends on all above)

Each step logs the entity counts so progress is visible.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

from .characters import process_characters
from .entities import (
    process_factions,
    process_items,
    process_quests,
    process_skills,
    process_spells,
    process_stances,
    process_world_tables,
    process_zones,
)
from .mapping import load_mapping
from .writer import Writer


def build(
    raw_db_path: Path,
    clean_db_path: Path,
    mapping_json_path: Path,
) -> None:
    """Build the clean database from the raw export.

    Args:
        raw_db_path: Path to the raw SQLite database (``database_raw``).
        clean_db_path: Path where the clean database will be written
            (``database``).  Any existing file at this path is removed.
        mapping_json_path: Path to ``mapping.json``.

    Raises:
        FileNotFoundError: If ``raw_db_path`` or ``mapping_json_path``
            does not exist.
        ValueError: If ``mapping.json`` is malformed.
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
        writer = Writer(clean_db_path)
        writer.create_schema()

        logger.info("Processing world/placement tables...")
        process_world_tables(raw, writer)

        logger.info("Processing zones...")
        process_zones(raw, writer, mapping)

        logger.info("Processing factions...")
        process_factions(raw, writer, mapping)

        logger.info("Processing items...")
        process_items(raw, writer, mapping)

        logger.info("Processing spells...")
        process_spells(raw, writer, mapping)

        logger.info("Processing skills...")
        process_skills(raw, writer, mapping)

        logger.info("Processing stances...")
        process_stances(raw, writer, mapping)

        logger.info("Processing quests...")
        process_quests(raw, writer, mapping)

        logger.info("Processing characters...")
        process_characters(raw, writer, mapping, spawn_mapping)

        logger.info("Finalising clean DB (VACUUM + ANALYZE)...")
        writer.finalize()

    finally:
        raw.close()

    logger.info("Clean DB build complete")
