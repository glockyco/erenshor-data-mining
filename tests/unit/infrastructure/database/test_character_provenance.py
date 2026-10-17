"""Character loot and vendor stock project persisted canonical item facts."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from erenshor.application.processor.item_provenance import ProvenanceBuilder
from erenshor.application.processor.writer import Writer
from erenshor.domain.value_objects.item_provenance import (
    PROVENANCE_SCHEMA_VERSION,
    ItemAcquisition,
    ProvenanceCondition,
    ProvenanceLocation,
)
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repository import RepositoryError


@pytest.fixture
def database(tmp_path: Path) -> Iterator[tuple[Writer, DatabaseConnection]]:
    path = tmp_path / "clean.sqlite"
    writer = Writer(path)
    writer.create_schema()
    writer.conn.execute(
        "INSERT INTO item_provenance_meta VALUES (?, 'fixture-build', '{}')", (PROVENANCE_SCHEMA_VERSION,)
    )
    writer.conn.executemany(
        "INSERT INTO characters "
        "(stable_key, display_name, image_name, encounter_tier, is_wiki_generated, level_scales_with_player) "
        "VALUES (?, ?, '', 'enemy', 0, 0)",
        [("character:group", "Hidden character"), ("character:copy-a", "Copy A"), ("character:copy-b", "Copy B")],
    )
    writer.conn.executemany(
        "INSERT INTO items (stable_key, display_name, image_name, is_wiki_generated) VALUES (?, ?, '', 0)",
        [("item:reward", "Reward"), ("item:raw-only", "Raw only")],
    )
    writer.conn.commit()
    db = DatabaseConnection(path, read_only=True)
    try:
        yield writer, db
    finally:
        db.close()
        writer.conn.close()


def _persist(writer: Writer, *facts: ItemAcquisition) -> None:
    builder = ProvenanceBuilder(writer.conn)
    builder.acquisitions.extend(facts)
    builder.persist()
    writer.conn.commit()


def _drop(key: str, copy: str, chance: float, *, guaranteed: bool = False) -> ItemAcquisition:
    return ItemAcquisition(
        key,
        "item:reward",
        "character_drop",
        "character:group",
        source_group_key="character:group",
        source_copy_stable_key=copy,
        probability_kind="exact",
        probability_min=chance,
        probability_max=chance,
        guarantee_scope="pool" if guaranteed else None,
    )


def test_character_loot_keeps_differing_copy_outcomes(database: tuple[Writer, DatabaseConnection]) -> None:
    writer, db = database
    _persist(
        writer,
        _drop("drop:a", "character:copy-a", 12.5),
        _drop("drop:b", "character:copy-b", 87.5, guaranteed=True),
    )
    repo = CharacterRepository(db)

    first = repo.get_character_loot_drops("character:copy-a")
    second = repo.get_character_loot_drops("character:copy-b")
    assert [(drop.drop_probability, drop.is_guaranteed) for drop in first] == [(12.5, False)]
    assert [(drop.drop_probability, drop.is_guaranteed) for drop in second] == [(87.5, True)]


def test_character_loot_uses_canonical_chance_and_only_raw_visibility(
    database: tuple[Writer, DatabaseConnection],
) -> None:
    writer, db = database
    writer.conn.executemany(
        "INSERT INTO loot_drops"
        " (character_stable_key,item_stable_key,loot_table_stable_key,source_component_is_enabled,"
        " drop_probability,is_visible,is_guaranteed)"
        " VALUES ('character:copy-a',?,'character:copy-a:script:LootTable:0',1,99,1,0)",
        [("item:reward",), ("item:raw-only",)],
    )
    _persist(writer, _drop("drop:a", "character:copy-a", 12.5, guaranteed=True))
    repo = CharacterRepository(db)

    drops = repo.get_character_loot_drops("character:copy-a")
    assert [(drop.item_link.stable_key, drop.drop_probability) for drop in drops] == [("item:reward", 12.5)]
    assert drops[0].is_guaranteed
    assert drops[0].is_visible
    assert all(drop.item_link.stable_key != "item:raw-only" for drop in drops)


def test_character_loot_does_not_require_raw_drop_row(database: tuple[Writer, DatabaseConnection]) -> None:
    writer, db = database
    _persist(writer, _drop("drop:a", "character:copy-a", 25))

    drops = CharacterRepository(db).get_character_loot_drops("character:copy-a")
    assert len(drops) == 1
    assert drops[0].drop_probability == 25
    assert not drops[0].is_visible


def test_vendor_stock_uses_canonical_copy_and_location_gates(database: tuple[Writer, DatabaseConnection]) -> None:
    writer, db = database
    unlock = ProvenanceCondition("stock_unlock", 0, 0, "quest_done", "quest:unlock")
    furnished = ProvenanceCondition("furniture", 0, 0, "room_furnished", "item:furniture")
    _persist(
        writer,
        ItemAcquisition(
            "vendor:a",
            "item:reward",
            "vendor",
            "character:group",
            source_group_key="character:group",
            source_copy_stable_key="character:copy-a",
            locations=(ProvenanceLocation("furniture:a", "spawn", conditions=(furnished,)),),
        ),
        ItemAcquisition(
            "vendor:b",
            "item:reward",
            "vendor",
            "character:group",
            source_group_key="character:group",
            source_copy_stable_key="character:copy-b",
            variant_key="quest:unlock",
            conditions=(unlock,),
            locations=(
                ProvenanceLocation("furniture:b", "spawn", conditions=(furnished,)),
                ProvenanceLocation("outside:b", "spawn"),
            ),
        ),
    )
    repo = CharacterRepository(db)

    stock = repo.get_vendor_stock()
    assert [(entry.copy_key, entry.furniture_key, entry.quest_key) for entry in stock] == [
        ("character:copy-a", "item:furniture", None),
        ("character:copy-b", None, "quest:unlock"),
    ]
    assert {entry.vendor_key for entry in stock} == {"character:group"}


@pytest.mark.parametrize(
    ("method", "arguments"),
    [
        ("get_character_loot_drops", ("character:copy-a",)),
        ("get_vendor_stock", ()),
    ],
)
@pytest.mark.parametrize("versions", [[], [PROVENANCE_SCHEMA_VERSION + 1], [PROVENANCE_SCHEMA_VERSION] * 2])
def test_source_methods_require_supported_canonical_schema(
    database: tuple[Writer, DatabaseConnection],
    method: str,
    arguments: tuple[str, ...],
    versions: list[int],
) -> None:
    writer, db = database
    writer.conn.execute("DELETE FROM item_provenance_meta")
    writer.conn.executemany(
        "INSERT INTO item_provenance_meta VALUES (?, 'fixture-build', '{}')", [(v,) for v in versions]
    )
    writer.conn.commit()
    with pytest.raises(RepositoryError, match="Unsupported item provenance schema"):
        getattr(CharacterRepository(db), method)(*arguments)
