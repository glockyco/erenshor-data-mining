"""Generator context for sharing dependencies across wiki generators.

This module defines GeneratorContext, which provides all generators with
access to repositories and storage without passing them individually.
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


@dataclass
class GeneratorContext:
    """Shared context for all wiki generators.

    Provides access to all repositories and storage needed for wiki page generation.
    All link resolution is done at query time inside repositories — no registry resolver.

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
    storage: WikiStorage
    class_display: ClassDisplayNameService
