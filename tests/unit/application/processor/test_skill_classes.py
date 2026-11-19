"""Skill class requirements follow the class assets in each game build."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from erenshor.application.processor.entities import process_skills
from erenshor.application.processor.writer import Writer
from erenshor.application.wiki.generators.sections.skill import SkillSectionGenerator
from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
from erenshor.application.wiki_lua.skills import generate_skills_module
from erenshor.domain.enriched_data.skill import EnrichedSkillData
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.skills import SkillRepository
from erenshor.infrastructure.database.repositories.spells import SpellRepository


@pytest.mark.parametrize("include_bard", [False, True])
def test_exported_classes_flow_from_raw_skills_to_repository_lua_and_wiki(tmp_path: Path, include_bard: bool) -> None:
    classes = ["Arcanist", "Druid", "Duelist", "Paladin", "Reaver", "Stormcaller"]
    if include_bard:
        classes.append("Bard")
    names = {name: "Windblade" if name == "Duelist" else name for name in classes}
    raw = sqlite3.connect(":memory:")
    raw.execute("CREATE TABLE Classes (ClassName TEXT)")
    raw.executemany("INSERT INTO Classes VALUES (?)", [(name,) for name in ["Default", *classes]])
    columns = ", ".join(f'"{name}RequiredLevel" INTEGER' for name in classes)
    raw.execute("CREATE TABLE Skills (StableKey TEXT, SkillName TEXT, StanceToUseStableKey TEXT, " + columns + ")")
    levels = {name: index + 1 for index, name in enumerate(classes)}
    raw.execute(
        "INSERT INTO Skills VALUES (" + ", ".join("?" for _ in range(3 + len(classes))) + ")",
        ("skill:chorus", "Chorus", None, *levels.values()),
    )
    raw.execute(
        "INSERT INTO Skills VALUES (" + ", ".join("?" for _ in range(3 + len(classes))) + ")",
        ("skill:npc", "NPC skill", None, *(0 for _ in classes)),
    )
    path = tmp_path / "clean.sqlite"
    writer = Writer(path)
    writer.create_schema()
    writer.conn.executemany("INSERT INTO classes (class_name, display_name) VALUES (?, ?)", names.items())
    process_skills(raw, writer, {})

    assert writer.conn.execute("SELECT count(*) FROM skill_classes").fetchone()[0] == len(classes)
    assert not any(row[1].endswith("_required_level") for row in writer.conn.execute("PRAGMA table_info(skills)"))
    writer.conn.execute(
        "INSERT INTO items (stable_key, display_name, wiki_page_name, image_name, teach_skill_stable_key) "
        "VALUES ('item:chorus', 'Chorus book', 'Chorus book', 'Chorus book', 'skill:chorus')"
    )
    writer.conn.commit()
    with DatabaseConnection(path) as db:
        repo = SkillRepository(db)
        skill = repo.get_skill_by_stable_key("skill:chorus")
        assert skill is not None
        assert skill.class_levels == levels
        assert {row.stable_key: row.class_levels for row in repo.get_skills_for_wiki_generation()} == {
            "skill:chorus": levels,
            "skill:npc": {},
        }
        module = generate_skills_module(repo)
        section = SkillSectionGenerator(ClassDisplayNameService(db)).generate_template(
            EnrichedSkillData(skill=skill, teaching_items=[], items_with_effect=[]), "Chorus"
        )
        for name, level in levels.items():
            assert f'"{names[name]}"' in module
            assert f"{{{{ClassLink|stablekey=class:{name.lower()}}}}} ({level})" in section
        assert ('"Bard"' in module) is include_bard
        assert SpellRepository(db).get_class_ability_teachers() == [
            {
                "class": f"class:{name.lower()}",
                "ability": "skill:chorus",
                "level": levels[name],
                "item": "item:chorus",
            }
            for name in sorted(classes, key=str.lower)
        ]
    writer.conn.close()
    raw.close()


@pytest.mark.parametrize(
    ("classes", "column", "message"),
    [
        (["Bard"], "DruidRequiredLevel", "missing required-level column for class Bard"),
        (["Druid"], "DruidRequiredLevel, BardRequiredLevel", "no playable class: Bard"),
    ],
)
def test_class_level_schema_mismatch_fails_before_writing(
    tmp_path: Path, classes: list[str], column: str, message: str
) -> None:
    raw = sqlite3.connect(":memory:")
    raw.execute("CREATE TABLE Classes (ClassName TEXT)")
    raw.executemany("INSERT INTO Classes VALUES (?)", [(name,) for name in classes])
    raw.execute(f"CREATE TABLE Skills (StableKey TEXT, {column})")
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()

    with pytest.raises(ValueError, match=message):
        process_skills(raw, writer, {})

    assert writer.conn.execute("SELECT count(*) FROM skills").fetchone()[0] == 0
    assert writer.conn.execute("SELECT count(*) FROM skill_classes").fetchone()[0] == 0
    writer.conn.close()
    raw.close()
