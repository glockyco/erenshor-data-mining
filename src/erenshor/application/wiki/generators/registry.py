"""Wiki generator registry.

This module provides the central registry for all wiki page generators.
The registry is the single source of truth for available generators and
enables selective generation via CLI flags.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.pages.armor_overview import (
    ArmorOverviewPageGenerator,
)
from erenshor.application.wiki.generators.pages.entities import EntityPageGenerator
from erenshor.application.wiki.generators.pages.weapons_overview import (
    WeaponsOverviewPageGenerator,
)
from erenshor.application.wiki.generators.pages.zones import ZonePageGenerator

if TYPE_CHECKING:
    from erenshor.application.wiki.generators.base import PageGenerator
    from erenshor.application.wiki.generators.context import GeneratorContext


@dataclass(frozen=True)
class GeneratorRegistration:
    """Registration entry for a wiki page generator.

    Attributes:
        name: Unique identifier for CLI selection (e.g., "entities", "zones")
        factory: Typed callable that constructs the page generator for a context
        description: Human-readable description of the generated pages
    """

    name: str
    factory: Callable[[GeneratorContext], PageGenerator]
    description: str


WIKI_GENERATORS: list[GeneratorRegistration] = [
    GeneratorRegistration(
        name="entities",
        factory=EntityPageGenerator,
        description="Generate pages for all game entities (items, characters, spells, skills, stances)",
    ),
    GeneratorRegistration(
        name="weapons_overview",
        factory=WeaponsOverviewPageGenerator,
        description="Generate Weapons overview page with sortable stats table",
    ),
    GeneratorRegistration(
        name="armor_overview",
        factory=ArmorOverviewPageGenerator,
        description="Generate Armor overview page with sortable stats table",
    ),
    GeneratorRegistration(
        name="zones",
        factory=ZonePageGenerator,
        description="Generate individual zone pages with connections and map links",
    ),
]


def get_generators_by_name(
    context: GeneratorContext,
    generator_names: list[str] | None = None,
) -> list[PageGenerator]:
    """Instantiate the registered generators, optionally filtered by name.

    Args:
        context: Shared context for all generators
        generator_names: Optional list of generator names to filter by.
                        If None, return all registered generators.

    Returns:
        Generators in registry order

    Raises:
        ValueError: If any requested generator name is not found in registry
    """
    if generator_names is None:
        logger.debug(f"Instantiating all {len(WIKI_GENERATORS)} registered generators")
        return [registration.factory(context) for registration in WIKI_GENERATORS]

    available_names = {registration.name for registration in WIKI_GENERATORS}
    invalid_names = set(generator_names) - available_names
    if invalid_names:
        raise ValueError(
            f"Unknown generator(s): {', '.join(sorted(invalid_names))}. Available: {', '.join(sorted(available_names))}"
        )

    selected = [registration for registration in WIKI_GENERATORS if registration.name in generator_names]
    logger.debug(f"Instantiating filtered generators: {', '.join(registration.name for registration in selected)}")
    return [registration.factory(context) for registration in selected]
