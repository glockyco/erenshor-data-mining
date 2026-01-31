"""Generator context for sharing dependencies across wiki generators.

This module defines GeneratorContext, which provides all generators with
access to repositories, resolvers, and storage without passing them
individually.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
    from erenshor.application.wiki.services.storage import WikiStorage
    from erenshor.infrastructure.database.repositories.characters import CharacterRepository
    from erenshor.infrastructure.database.repositories.factions import FactionRepository
    from erenshor.infrastructure.database.repositories.items import ItemRepository
    from erenshor.infrastructure.database.repositories.loot_tables import LootTableRepository
    from erenshor.infrastructure.database.repositories.quests import QuestRepository
    from erenshor.infrastructure.database.repositories.skills import SkillRepository
    from erenshor.infrastructure.database.repositories.spawn_points import SpawnPointRepository
    from erenshor.infrastructure.database.repositories.spells import SpellRepository
    from erenshor.infrastructure.database.repositories.stances import StanceRepository
    from erenshor.registry.resolver import RegistryResolver


@dataclass
class GeneratorContext:
    """Shared context for all wiki generators.

    Provides access to all repositories, registry resolver, and storage
    needed for wiki page generation.

    Attributes:
        item_repo: Repository for item entities
        character_repo: Repository for character entities
        spell_repo: Repository for spell entities
        skill_repo: Repository for skill entities
        stance_repo: Repository for stance entities
        faction_repo: Repository for faction data
        spawn_repo: Repository for spawn point data
        loot_repo: Repository for loot table data
        quest_repo: Repository for quest data
        resolver: Registry resolver for page titles and links
        storage: Wiki storage for reading fetched pages
        class_display: Service for mapping class names to display names
    """

    item_repo: ItemRepository
    character_repo: CharacterRepository
    spell_repo: SpellRepository
    skill_repo: SkillRepository
    stance_repo: StanceRepository
    faction_repo: FactionRepository
    spawn_repo: SpawnPointRepository
    loot_repo: LootTableRepository
    quest_repo: QuestRepository
    resolver: RegistryResolver
    storage: WikiStorage
    class_display: ClassDisplayNameService
