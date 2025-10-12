"""Helper utilities for ability (spell/skill) generation.

Common functionality shared between spell and skill generators to avoid duplication.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, Optional, Sequence, TypeVar

from sqlalchemy import Engine

from erenshor.domain.entities.spell import DbSkill, DbSpell
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.game_constants import GAME_TICKS_PER_SECOND

__all__ = [
    "GAME_TICKS_PER_SECOND",
    "create_ability_cache",
    "parse_spell_reference",
    "build_sorted_classes_list",
]

T = TypeVar("T", DbSpell, DbSkill)


def create_ability_cache(
    engine: Engine, get_by_id_func: Callable[[Engine, str], Optional[T]]
) -> Callable[[str], Optional[T]]:
    """Create a cached lookup function for abilities.

    Args:
        engine: Database engine
        get_by_id_func: Function to fetch ability by ID from database

    Returns:
        Cached lookup function that reuses results within generation run
    """
    cache: Dict[str, Optional[T]] = {}

    def get_cached(ability_id: str) -> Optional[T]:
        if ability_id in cache:
            return cache[ability_id]
        result = get_by_id_func(engine, ability_id)
        cache[ability_id] = result
        return result

    return get_cached


def parse_spell_reference(
    text: str,
    link_resolver: RegistryLinkResolver,
    get_spell: Callable[[str], Optional[DbSpell]],
) -> str:
    """Parse 'Spell Name (ID)' format and return wiki link.

    IMPORTANT: Effects and procs in Erenshor ALWAYS reference spells, never skills.
    This is a game mechanics constraint - skills cannot be used as effects/procs.

    This function is used for:
    - Spells.AddProc: Spell that procs from this spell
    - Skills.EffectToApplyId: Spell effect applied by this skill
    - Skills.CastOnTargetId: Spell cast on target by this skill

    All of these reference spells only, never skills.

    Args:
        text: Reference text like "Spell Name (ID)"
        link_resolver: Link resolver for generating wiki links
        get_spell: Function to lookup spell by ID

    Returns:
        Wiki link like {{AbilityLink|Spell Name}}
    """
    from erenshor.domain.entities.page import EntityRef
    from erenshor.domain.value_objects.entity_type import EntityType

    # Parse "Name (ID)" format
    match = re.search(r"^(.+?)\s*\((\d+)\)$", text.strip())
    if not match:
        # No ID found, use name directly
        name = text.split("(")[0].strip()
        fallback_entity = EntityRef(
            entity_type=EntityType.SPELL,
            db_id=None,
            db_name=name,
            resource_name="",
        )
        return link_resolver.ability_link(fallback_entity)

    name = match.group(1).strip()
    spell_id = match.group(2)

    # Look up the spell (effects ONLY reference spells, not skills)
    cached_spell = get_spell(spell_id)
    if cached_spell:
        entity = EntityRef.from_spell(cached_spell)
        return link_resolver.ability_link(entity)

    # Spell not found, use parsed name
    fallback_entity = EntityRef(
        entity_type=EntityType.SPELL,
        db_id=spell_id,
        db_name=name,
        resource_name="",
    )
    return link_resolver.ability_link(fallback_entity)


def build_sorted_classes_list(
    class_level_pairs: Sequence[tuple[str, int | None]],
) -> list[str]:
    """Build alphabetically sorted classes list with required levels.

    Classes are sorted alphabetically by class name for consistent display.

    Args:
        class_level_pairs: Sequence of (class_name, required_level) tuples

    Returns:
        Sorted list of formatted class strings like "[[ClassName]] (level)"
    """
    # Filter to only classes with levels > 0, then sort alphabetically
    valid_classes = [
        (class_name, level)
        for class_name, level in class_level_pairs
        if level and level > 0
    ]
    valid_classes.sort(key=lambda x: x[0])

    # Format with level if present
    return [f"[[{class_name}]] ({level})" for class_name, level in valid_classes]
