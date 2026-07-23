"""All-page semantic validation against a staged main-variant corpus."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from erenshor.application.wiki.semantic_validation import (
    build_semantic_manifest,
    derive_corpus_expectations,
    validate_wiki_pages,
)
from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.application.wiki_lua.link_catalog import build_link_catalog_entries
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repositories.factions import FactionRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.quests import QuestRepository
from erenshor.infrastructure.database.repositories.skills import SkillRepository
from erenshor.infrastructure.database.repositories.spells import SpellRepository
from erenshor.infrastructure.database.repositories.stances import StanceRepository
from erenshor.infrastructure.database.repositories.zones import ZoneRepository

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "variants" / "main" / "erenshor-main.sqlite"
SOURCE_WIKI_DIR = REPO_ROOT / "variants" / "main" / "wiki"
GOLDEN_MANIFEST_PATH = REPO_ROOT / "tests" / "golden" / "wiki" / "manifest.json"


@pytest.fixture(scope="module")
def generated_semantic_corpus(tmp_path_factory: pytest.TempPathFactory):
    """Stage the exact generated article corpus without mutating variant state."""
    if not DB_PATH.is_file():
        pytest.skip(f"Main variant database not found: {DB_PATH}")
    fetched_dir = SOURCE_WIKI_DIR / "fetched"
    generated_dir = SOURCE_WIKI_DIR / "generated"
    metadata_file = SOURCE_WIKI_DIR / "metadata.json"
    if not fetched_dir.is_dir() or not generated_dir.is_dir() or not metadata_file.is_file():
        pytest.skip(f"Main fetched/generated wiki corpus not found: {SOURCE_WIKI_DIR}")

    wiki_dir = tmp_path_factory.mktemp("wiki-semantics")
    storage = WikiStorage(wiki_dir)
    shutil.copytree(fetched_dir, wiki_dir / "fetched", dirs_exist_ok=True)
    shutil.copytree(generated_dir, wiki_dir / "generated", dirs_exist_ok=True)
    shutil.copy2(metadata_file, wiki_dir / "metadata.json")

    connection = DatabaseConnection(DB_PATH, read_only=True)
    try:
        item_repo = ItemRepository(connection)
        character_repo = CharacterRepository(connection)
        spell_repo = SpellRepository(connection)
        skill_repo = SkillRepository(connection)
        stance_repo = StanceRepository(connection)
        faction_repo = FactionRepository(connection)
        quest_repo = QuestRepository(connection)
        zone_repo = ZoneRepository(connection)
        class_display = ClassDisplayNameService(connection)

        pages = storage.read_generated_pages()
        expectations = derive_corpus_expectations(storage, pages)

        catalog = build_link_catalog_entries(
            items=item_repo.get_items_for_link_catalog(),
            characters=character_repo.get_characters_for_wiki_generation(),
            quests=quest_repo.get_quests_for_wiki_generation(),
            zones=zone_repo.get_all_zones(),
            spells=spell_repo.get_spells_for_wiki_generation(),
            skills=skill_repo.get_skills_for_wiki_generation(),
            stances=stance_repo.get_all(),
            factions=faction_repo.get_factions_for_wiki_generation(),
            class_display=class_display,
        )
        yield pages, expectations, catalog
    finally:
        connection.close()


def test_semantic_manifest_matches_golden(generated_semantic_corpus) -> None:
    """The compact golden records every page identity and semantic output boundary."""
    pages, expectations, catalog = generated_semantic_corpus
    actual = build_semantic_manifest(pages, expectations=expectations, catalog_entries=catalog)

    assert GOLDEN_MANIFEST_PATH.is_file(), "Run 'uv run erenshor golden capture' to create the wiki manifest"
    assert actual == json.loads(GOLDEN_MANIFEST_PATH.read_text(encoding="utf-8"))


def test_all_generated_pages_satisfy_semantic_contracts(generated_semantic_corpus) -> None:
    """Every staged generated article satisfies every declared invariant."""
    pages, expectations, catalog = generated_semantic_corpus
    report = validate_wiki_pages(
        pages,
        expectations=expectations,
        catalog_entries=catalog,
        planned_titles=pages,
        known_generated_titles=pages,
        variant="main",
    )
    report.raise_for_errors()
