"""Tests for ZoneRepository provenance queries."""

from __future__ import annotations

from pathlib import Path

from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.zones import ZoneRepository


def test_zone_obtained_from_sources_preserve_conditions_and_aggregation(integration_db: Path) -> None:
    """Mining and fishing sources retain zone keys and day/night variants."""
    repo = ZoneRepository(DatabaseConnection(integration_db, read_only=True))

    mining = repo.get_mining_zones_for_item("item:ore - iron ore")
    assert [(source.source_key, source.probability) for source in mining] == [
        ("zone:azure", 21.0),
        ("zone:hidden", 21.0),
        ("zone:stowaway", 41.91666793823242),
        ("zone:vitheo", 21.0),
    ]

    fishing = repo.get_fishing_waters_for_item("item:fish - a burgundy skipper")
    brake = [source for source in fishing if source.source_key == "zone:brake"]
    assert [(source.condition, source.probability) for source in brake] == [
        ("day", 5.9375),
        ("night", 19.0),
    ]


def test_item_bag_sources_use_zone_stable_keys(integration_db: Path) -> None:
    """Item bags resolve their scene to a zone StableKey."""
    repo = ZoneRepository(DatabaseConnection(integration_db, read_only=True))

    sources = repo.get_item_bag_zones_for_item("item:cons - bread")

    assert [source.source_key for source in sources] == ["zone:azure", "zone:summerevent"]
    assert all(source.source_type == "item_bag" for source in sources)
