"""Wiki generator registry.

This module provides the central registry for all wiki page generators.
The registry is the single source of truth for available generators and
enables selective generation via CLI flags.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.pages.entities import EntityPageGenerator

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
    """

    name: str
    generator_class: type[PageGenerator]
    description: str


# Global registry of all wiki page generators
WIKI_GENERATORS: list[GeneratorRegistration] = [
    GeneratorRegistration(
        name="entities",
        generator_class=EntityPageGenerator,
        description="Generate pages for all game entities (items, characters, spells, skills)",
    ),
]


def get_generators_by_name(
    context: GeneratorContext,
    generator_names: list[str] | None = None,
) -> list[PageGenerator]:
    """Get generator instances filtered by name.

    Args:
        context: Shared context for all generators
        generator_names: Optional list of generator names to filter by.
                        If None, return all registered generators.

    Returns:
        List of instantiated PageGenerator objects

    Raises:
        ValueError: If any requested generator name is not found in registry

    Example:
        ```python
        # Get all generators
        generators = get_generators_by_name(context)

        # Get specific generators
        generators = get_generators_by_name(context, ["items", "weapons_overview"])
        ```
    """
    # If no filter, return all generators
    if generator_names is None:
        logger.debug(f"Instantiating all {len(WIKI_GENERATORS)} registered generators")
        return [registration.generator_class(context) for registration in WIKI_GENERATORS]

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

    return [registration.generator_class(context) for registration in filtered_registrations]


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
        pages = list(chain.from_iterable(gen.generate_pages() for gen in generators))
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


def list_generators() -> list[tuple[str, str]]:
    """List all registered generators with descriptions.

    Returns:
        List of (name, description) tuples for CLI display

    Example:
        ```python
        for name, description in list_generators():
            print(f"  {name:20s} - {description}")
        ```
    """
    return [(reg.name, reg.description) for reg in WIKI_GENERATORS]
