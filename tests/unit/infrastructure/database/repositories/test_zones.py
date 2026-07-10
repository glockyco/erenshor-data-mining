"""Tests for ZoneRepository provenance queries."""

from __future__ import annotations

from pathlib import Path

from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.zones import ZoneRepository


def test_node_and_water_sources_preserve_smallest_identities(integration_db: Path) -> None:
    """Mining nodes and waters stay distinct while retaining connected zones."""
    repo = ZoneRepository(DatabaseConnection(integration_db, read_only=True))

    mining = repo.get_mining_nodes_for_item("item:ore - iron ore")
    assert len(mining) == 73
    assert len({source.source_key for source in mining}) == 73
    assert mining[0].source_key == "mining:azure:125.47:11.61:290.15"
    assert mining[0].probability == 21.0
    assert any(
        source.source_key.startswith("mining:stowaway:") and source.probability == 41.91666793823242
        for source in mining
    )

    fishing = repo.get_fishing_waters_for_item("item:fish - a burgundy skipper")
    brake = [source for source in fishing if source.source_key == "water:brake:287.10:7.50:247.80"]
    assert [(source.condition, source.probability) for source in brake] == [
        ("day", 5.9375),
        ("night", 19.0),
    ]
    plane = [source for source in fishing if source.source_key.startswith("water:planeoffernalla:")]
    assert len({source.source_key for source in plane}) == 2


def test_item_bag_sources_use_bag_stable_keys(integration_db: Path) -> None:
    """Item bags retain their identity while joining through the zone scene."""
    repo = ZoneRepository(DatabaseConnection(integration_db, read_only=True))

    sources = repo.get_item_bag_sources_for_item("item:cons - bread")

    assert [source.source_key for source in sources] == [
        "itembag:azure:44.61:14.12:246.98",
        "itembag:summerevent:174.32:12.11:147.70",
    ]
    assert all(source.source_type == "item_bag" for source in sources)
