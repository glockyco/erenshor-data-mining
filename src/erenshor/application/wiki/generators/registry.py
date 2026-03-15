"""Wiki generator registry.

This module provides the central registry for all wiki page generators.
The registry is the single source of truth for available generators and
enables selective generation via CLI flags.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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

if TYPE_CHECKING:
    from erenshor.application.wiki.generators.base import GeneratedPage, PageGenerator
    from erenshor.application.wiki.generators.context import GeneratorContext


@dataclass
class GeneratorRegistration:
    """Registration entry for a wiki page generator.

    Attributes:
        name: Unique identifier for CLI selection (e.g., "items", "weapons_overview")
        generator_class: PageGenerator class to instantiate
        description: Human-readable description for CLI help text
        auto_deploy: If False, pages are excluded from the default `wiki deploy` run.
            Use for generators that write to a separate output_dir rather than
            the standard wiki storage.
        output_dir: If set, generated pages are written as plain .txt files to this
            directory instead of the standard WikiStorage. The generator is
            responsible for its own field preservation in this case.
    """

    name: str
    generator_class: type[PageGenerator]
    description: str
    auto_deploy: bool = True
    output_dir: Path | None = field(default=None)


# Global registry of all wiki page generators
WIKI_GENERATORS: list[GeneratorRegistration] = [
    GeneratorRegistration(
        name="entities",
        generator_class=EntityPageGenerator,
        description="Generate pages for all game entities (items, characters, spells, skills, stances)",
    ),
    GeneratorRegistration(
        name="weapons_overview",
        generator_class=WeaponsOverviewPageGenerator,
        description="Generate Weapons overview page with sortable stats table",
    ),
    GeneratorRegistration(
        name="armor_overview",
        generator_class=ArmorOverviewPageGenerator,
        description="Generate Armor overview page with sortable stats table",
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
        return [(reg, reg.generator_class(context)) for reg in WIKI_GENERATORS]

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

    return [(reg, reg.generator_class(context)) for reg in filtered_registrations]


def detect_conflicts(pages: list[GeneratedPage]) -> dict[str, list[GeneratedPage]]:
    """Detect page title conflicts (multiple generators producing same page).

    This is called after generation to identify cases where multiple generators
    attempt to create the same wiki page, which would be an error.

    Args:
        pages: List of all generated pages

    Returns:
        Dict mapping conflicting page titles to list of GeneratedPage objects
        that produced them. Empty dict if no conflicts.

    Example:
        ```python
        pages = list(chain.from_iterable(gen.generate_pages() for _, gen in pairs))
        conflicts = detect_conflicts(pages)

        if conflicts:
            for title, conflicting_pages in conflicts.items():
                logger.error(f"Multiple generators produced page '{title}'")
        ```
    """
    title_to_pages: dict[str, list[GeneratedPage]] = {}

    for page in pages:
        if page.title not in title_to_pages:
            title_to_pages[page.title] = []
        title_to_pages[page.title].append(page)

    # Return only pages with conflicts (>1 generator)
    conflicts = {title: pages for title, pages in title_to_pages.items() if len(pages) > 1}

    if conflicts:
        logger.warning(f"Detected {len(conflicts)} page title conflict(s)")
        for title, conflicting_pages in conflicts.items():
            logger.warning(f"  - '{title}': {len(conflicting_pages)} generators")

    return conflicts


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
