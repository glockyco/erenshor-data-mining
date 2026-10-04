"""A stance takes its image and its wiki page from the skill that switches to it."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from erenshor.application.processor.entities import process_skills, process_stances
from erenshor.application.processor.writer import Writer


def _raw(
    tmp_path: Path, skills: list[tuple[str, str, str | None]], stances: list[tuple[str, str]]
) -> sqlite3.Connection:
    raw = sqlite3.connect(tmp_path / "raw.sqlite")
    raw.execute("CREATE TABLE Skills (StableKey TEXT, SkillName TEXT, StanceToUseStableKey TEXT)")
    raw.execute("CREATE TABLE Stances (StableKey TEXT, DisplayName TEXT)")
    raw.executemany("INSERT INTO Skills VALUES (?, ?, ?)", skills)
    raw.executemany("INSERT INTO Stances VALUES (?, ?)", stances)
    return raw


def _clean_stances(writer: Writer) -> dict[str, tuple[str, str | None]]:
    rows = writer._conn.execute("SELECT stable_key, image_name, wiki_page_name FROM stances").fetchall()
    return {key: (image, page) for key, image, page in rows}


def test_stance_takes_the_image_of_its_skill_and_a_stance_without_skill_gets_no_page(tmp_path: Path) -> None:
    raw = _raw(
        tmp_path,
        skills=[("skill:stance - expert", "Stance: Expert", "stance:expert"), ("skill:kick", "Kick", None)],
        stances=[("stance:expert", "Expert"), ("stance:reckless", "Reckless")],
    )
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()

    stance_images = process_skills(raw, writer, {})
    process_stances(raw, writer, {}, stance_images)

    assert _clean_stances(writer) == {
        "stance:expert": ("Stance: Expert", "Expert"),
        "stance:reckless": ("", None),
    }


def test_two_skills_with_different_images_for_one_stance_fail(tmp_path: Path) -> None:
    raw = _raw(
        tmp_path,
        skills=[
            ("skill:stance - expert", "Stance: Expert", "stance:expert"),
            ("skill:expert form", "Expert Form", "stance:expert"),
        ],
        stances=[("stance:expert", "Expert")],
    )
    writer = Writer(tmp_path / "clean.sqlite")
    writer.create_schema()

    with pytest.raises(ValueError, match="two skills switch to this stance"):
        process_skills(raw, writer, {})
