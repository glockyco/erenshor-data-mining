"""Shared helper functions for wiki services.

This module contains common functionality used across WikiFetchService,
WikiGenerateService, and WikiDeployService to avoid duplication.
"""

from collections import defaultdict

from loguru import logger
from rich.console import Console

from erenshor.application.services.wiki_page import WikiPage
from erenshor.domain.entities import Character, Item, Skill, Spell
from erenshor.registry.resolver import RegistryResolver


def group_entities_by_page_title(
    entities: list[Item | Character | Spell | Skill],
    registry_resolver: RegistryResolver,
) -> list[WikiPage]:
    """Group entities by resolved page title.

    Args:
        entities: List of all entities to group.
        registry_resolver: Resolver for page titles from registry.

    Returns:
        List of WikiPage objects.
    """
    groups: dict[str, list[Item | Character | Spell | Skill]] = defaultdict(list)

    for entity in entities:
        # Get entity's display name based on type
        if isinstance(entity, Item):
            entity_name = entity.item_name
        elif isinstance(entity, Character):
            entity_name = entity.npc_name
        elif isinstance(entity, Spell):
            entity_name = entity.spell_name
        elif isinstance(entity, Skill):
            entity_name = entity.skill_name
        else:
            logger.warning(f"Unknown entity type: {type(entity)}")
            continue

        if not entity_name:
            raise ValueError(f"Entity {entity.stable_key} has no name")

        # Resolve page title via registry
        page_title = registry_resolver.resolve_page_title(entity.stable_key)

        # Skip excluded entities (None means excluded)
        if page_title is None:
            continue

        groups[page_title].append(entity)

    # Convert to WikiPage objects
    pages = [
        WikiPage(
            title=page_title,
            stable_keys=[e.stable_key for e in group_entities],
            entities=group_entities,
        )
        for page_title, group_entities in groups.items()
    ]

    logger.debug(f"Grouped {len(entities)} entities into {len(pages)} pages")
    return pages


def display_operation_summary(
    console: Console,
    operation: str,
    total: int,
    succeeded: int,
    failed: int,
    skipped: int,
    warnings: list[str],
    errors: list[str],
    dry_run: bool,
) -> None:
    """Display operation summary.

    Args:
        console: Rich console for output.
        operation: Name of the operation (e.g., "Fetch", "Generate", "Deploy").
        total: Total number of pages processed.
        succeeded: Number of successful operations.
        failed: Number of failed operations.
        skipped: Number of skipped operations.
        warnings: List of warning messages.
        errors: List of error messages.
        dry_run: Whether this was a dry run.
    """
    console.print()
    console.print(f"[bold]{operation} Summary:[/bold]")
    console.print(f"  Total pages:   {total}")
    console.print(f"  Succeeded:     {succeeded}")

    if failed > 0:
        console.print(f"  [red]Failed:        {failed}[/red]")

    if skipped > 0:
        console.print(f"  Skipped:       {skipped}")

    if warnings:
        console.print(f"  [yellow]Warnings:      {len(warnings)}[/yellow]")

    if dry_run:
        console.print("  [dim](Dry run - no changes made)[/dim]")

    console.print()
