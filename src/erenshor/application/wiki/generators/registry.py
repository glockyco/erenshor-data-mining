"""Wiki generator registry.

This module provides the central registry for all wiki page generators.
The registry is the single source of truth for available generators and
enables selective generation via CLI flags.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
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


@dataclass
class GeneratorRegistration:
    """Registration entry for a wiki page generator.

    Attributes:
        name: Unique identifier for CLI selection (e.g., "items", "weapons_overview")
        factory: Typed callable that constructs the page generator for a context
        description: Human-readable description for CLI help text
        auto_deploy: If False, pages are excluded from the default `wiki deploy` run.
            Use for generators that write to a separate output_dir rather than
            the standard wiki storage.
        output_dir: If set, generated pages are written as plain .txt files to this
            directory instead of the standard WikiStorage. The generator is
            responsible for its own field preservation in this case.
    """

    name: str
    factory: Callable[[GeneratorContext], PageGenerator]
    description: str
    auto_deploy: bool = True
    output_dir: Path | None = field(default=None)


# Zone paths are bound from GeneratorContext for each selected variant.


def _create_entity_generator(context: GeneratorContext) -> EntityPageGenerator:
    return EntityPageGenerator(context)


def _create_weapons_overview_generator(context: GeneratorContext) -> WeaponsOverviewPageGenerator:
    return WeaponsOverviewPageGenerator(context)


def _create_armor_overview_generator(context: GeneratorContext) -> ArmorOverviewPageGenerator:
    return ArmorOverviewPageGenerator(context)


def _create_zone_generator(context: GeneratorContext) -> ZonePageGenerator:
    return ZonePageGenerator(
        context,
        output_dir=context.zone_output_dir,
        zone_positions_path=context.zone_positions_path,
    )


def _bind_registration(registration: GeneratorRegistration, context: GeneratorContext) -> GeneratorRegistration:
    """Bind paths that are composed per wiki invocation."""
    if registration.name != "zones":
        return registration
    if context.zone_output_dir is None:
        raise ValueError("Zone generator requires an explicit output directory")
    return replace(registration, output_dir=context.zone_output_dir)


def _instantiate_registration(
    registration: GeneratorRegistration,
    context: GeneratorContext,
) -> tuple[GeneratorRegistration, PageGenerator]:
    """Bind invocation paths and construct one generator."""
    bound = _bind_registration(registration, context)
    return bound, bound.factory(context)


WIKI_GENERATORS: list[GeneratorRegistration] = [
    GeneratorRegistration(
        name="entities",
        factory=_create_entity_generator,
        description="Generate pages for all game entities (items, characters, spells, skills, stances)",
    ),
    GeneratorRegistration(
        name="weapons_overview",
        factory=_create_weapons_overview_generator,
        description="Generate Weapons overview page with sortable stats table",
    ),
    GeneratorRegistration(
        name="armor_overview",
        factory=_create_armor_overview_generator,
        description="Generate Armor overview page with sortable stats table",
    ),
    GeneratorRegistration(
        name="zones",
        factory=_create_zone_generator,
        description="Generate individual zone pages with connections and map links",
        auto_deploy=False,
        output_dir=None,
    ),
]


def get_generators_by_name(
    context: GeneratorContext,
    generator_names: list[str] | None = None,
) -> list[tuple[GeneratorRegistration, PageGenerator]]:
    """Get (registration, generator_instance) pairs filtered by name.

    Args:
        context: Shared context for all generators
        generator_names: Optional list of generator names to filter by.
                        If None, return all registered generators.

    Returns:
        List of (GeneratorRegistration, PageGenerator) pairs

    Raises:
        ValueError: If any requested generator name is not found in registry

    Example:
        ```python
        # Get all generators with their registrations
        pairs = get_generators_by_name(context)
        for reg, gen in pairs:
            pages = list(gen.generate_pages())
            if reg.output_dir:
                # Write to separate directory
                ...

        # Get specific generators
        pairs = get_generators_by_name(context, ["items", "weapons_overview"])
        ```
    """
    # If no filter, return all generators
    if generator_names is None:
        logger.debug(f"Instantiating all {len(WIKI_GENERATORS)} registered generators")
        return [_instantiate_registration(reg, context) for reg in WIKI_GENERATORS]

    # Validate all requested names exist
    available_names = {reg.name for reg in WIKI_GENERATORS}
    invalid_names = set(generator_names) - available_names

    if invalid_names:
        raise ValueError(
            f"Unknown generator(s): {', '.join(sorted(invalid_names))}. Available: {', '.join(sorted(available_names))}"
        )

    # Filter and instantiate requested generators
    filtered_registrations = [reg for reg in WIKI_GENERATORS if reg.name in generator_names]

    logger.debug(
        f"Instantiating {len(filtered_registrations)} filtered generators: "
        f"{', '.join(reg.name for reg in filtered_registrations)}"
    )

    return [_instantiate_registration(reg, context) for reg in filtered_registrations]


def list_generators() -> list[tuple[str, str, bool]]:
    """List all registered generators with descriptions and deploy status.

    Returns:
        List of (name, description, auto_deploy) tuples for CLI display

    Example:
        ```python
        for name, description, auto_deploy in list_generators():
            deploy_flag = "" if auto_deploy else " [manual deploy]"
            print(f"  {name:20s} - {description}{deploy_flag}")
        ```
    """
    return [(reg.name, reg.description, reg.auto_deploy) for reg in WIKI_GENERATORS]
