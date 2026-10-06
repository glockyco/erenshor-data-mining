"""An icon is named by the texture that its sprite draws, not by the sprite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from erenshor.application.processor.entities import process_skills, process_spells
from erenshor.application.processor.writer import Writer


def _writer(tmp_path: Path) -> Writer:
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()
    return writer


def test_a_spell_icon_is_named_by_its_texture_and_a_spell_without_icon_has_none(tmp_path: Path) -> None:
    raw = sqlite3.connect(tmp_path / "raw.sqlite")
    raw.execute("CREATE TABLE Spells (StableKey TEXT, SpellName TEXT, SpellIconTexture TEXT)")
    raw.execute("CREATE TABLE SpellClasses (SpellStableKey TEXT, ClassName TEXT)")
    # The export names this spell's sprite 4_6, and the sprite draws 4_7.png.
    raw.executemany(
        "INSERT INTO Spells VALUES (?, ?, ?)",
        [("spell:ice's memory", "Aura: Ice's Memory", "Assets/Texture2D/4_7.png"), ("spell:quiet", "Quiet", None)],
    )
    writer = _writer(tmp_path)

    process_spells(raw, writer, {})

    names = dict(writer._conn.execute("SELECT stable_key, spell_icon_name FROM spells"))
    assert names == {"spell:ice's memory": "4_7", "spell:quiet": None}


def test_an_icon_texture_outside_the_texture_folder_fails_and_names_the_skill(tmp_path: Path) -> None:
    raw = sqlite3.connect(tmp_path / "raw.sqlite")
    raw.execute(
        "CREATE TABLE Skills (StableKey TEXT, SkillName TEXT, StanceToUseStableKey TEXT, SkillIconTexture TEXT)"
    )
    raw.execute("INSERT INTO Skills VALUES ('skill:kick', 'Kick', NULL, 'Assets/Sprite/Kick.asset')")

    with pytest.raises(ValueError, match=r"skill:kick: icon texture Assets/Sprite/Kick\.asset is not a PNG file"):
        process_skills(raw, _writer(tmp_path), {})
