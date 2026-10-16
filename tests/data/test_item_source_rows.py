"""Every source kind that `Data/Items` holds for an item reaches a row of its page.

The item pages build their rows from link queries, and `Data/Items` from stable-keyed
queries over the same tables. An item whose data names a source kind that its page
leaves out tells readers that the item cannot be obtained that way.
"""

from __future__ import annotations

from pathlib import Path

from erenshor.application.wiki_lua.items import build_item_sources_by_item
from erenshor.infrastructure.database.connection import DatabaseConnection
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.quests import QuestRepository
from erenshor.infrastructure.database.repositories.zones import ZoneRepository


def test_every_item_source_kind_has_page_rows(main_clean_db: Path) -> None:
    with DatabaseConnection(main_clean_db, read_only=True) as db:
        items_repo = ItemRepository(db)
        characters = CharacterRepository(db)
        zones = ZoneRepository(db)
        items = [item for item in items_repo.get_items_for_wiki_generation() if item.wiki_page_name]
        sources = build_item_sources_by_item(items, items_repo, characters, QuestRepository(db), zones)

        row_checks = {
            "auction_house": lambda key: items_repo.get_auction_house_sources(key),
            "common_world_item": lambda key: characters.get_common_world_item_sources(key),
            "dialog": lambda key: characters.get_item_givers(key),
            "item_use": lambda key: items_repo.get_item_use_source_links(key),
            "item_conversion": lambda key: items_repo.get_item_use_source_links(key),
            "mining": lambda key: zones.get_mining_zones_for_item(key),
            "fishing": lambda key: zones.get_fishing_zones_for_item(key),
            "item_bag": lambda key: zones.get_item_bag_zones_for_item(key),
            "starting": lambda key: items_repo.get_starting_class_names(key),
        }
        missing = sorted(
            (item.stable_key, source.source_type)
            for item in items
            for source in sources[item.stable_key].obtained_from
            if source.source_type in row_checks and not row_checks[source.source_type](item.stable_key)
        )

    assert missing == []
