"""Unified update commands for wiki content generation.

Provides update commands for all content types with:

- Consistent interface across all content types
- Filtering capabilities (--filter, --unique-only, etc.)
- Integrated validation (--validate, --no-validate, --validate-only)
- Dry-run mode (--dry-run)
- Unified `update all` command

CLI structure:
  update <content-type> [OPTIONS]

Example commands:
  erenshor-wiki update items
  erenshor-wiki update items --filter "Time Stone"
  erenshor-wiki update characters --unique-only
  erenshor-wiki update all
  erenshor-wiki update items --validate-only
  erenshor-wiki update items --dry-run
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console

__all__ = [
    "update_abilities",
    "update_all",
    "update_characters",
    "update_fishing",
    "update_items",
    "update_overviews",
]


app = typer.Typer(
    name="update",
    help="Update wiki content from database",
    no_args_is_help=True,
)


FilterOption = typer.Option(
    None,
    "--filter",
    "-f",
    help="Filter entities by name or ID (e.g., 'Time Stone' or 'id:1234')",
)

ValidateOption = typer.Option(
    True,
    "--validate/--no-validate",
    help="Validate content before writing (default: enabled)",
)

ValidateOnlyOption = typer.Option(
    False,
    "--validate-only",
    help="Only validate, don't write files",
)

DryRunOption = typer.Option(
    False,
    "--dry-run",
    help="Show what would change without writing files",
)

BatchSizeOption = typer.Option(
    100,
    "--batch-size",
    help="Number of entities to process per batch",
)

DbOption = typer.Option(
    None,
    "--db",
    help="Path to erenshor.sqlite (uses config default if not specified)",
    exists=True,
    dir_okay=False,
)

CacheDirOption = typer.Option(
    None,
    "--cache-dir",
    help="Cache directory for fetched pages (uses config default if not specified)",
)

OutputDirOption = typer.Option(
    None,
    "--output-dir",
    help="Output directory for updated pages (uses config default if not specified)",
)


@app.command("items")
def update_items(
    filter: Optional[str] = FilterOption,
    validate: bool = ValidateOption,
    validate_only: bool = ValidateOnlyOption,
    dry_run: bool = DryRunOption,
    batch_size: int = BatchSizeOption,
    db: Optional[Path] = DbOption,
    cache_dir: Optional[Path] = CacheDirOption,
    output_dir: Optional[Path] = OutputDirOption,
) -> None:
    """Update item pages (all item types: weapons, armor, auras, consumables, etc.).

    Updates all item pages with content generated from the database. This includes:
    - Item infoboxes (all item types)
    - Fancy tables for weapons and armor (3 tiers)
    - Source information (vendors, drops, crafting, quests)

    Examples:
      # Update all items with validation
      erenshor-wiki update items

      # Update specific item
      erenshor-wiki update items --filter "Time Stone"

      # Update by ID
      erenshor-wiki update items --filter "id:1234"

      # Only validate without writing
      erenshor-wiki update items --validate-only

      # Show what would change
      erenshor-wiki update items --dry-run

      # Skip validation (faster)
      erenshor-wiki update items --no-validate
    """
    from erenshor.application.generators.items import ItemGenerator
    from erenshor.application.transformers.items import ItemTransformer
    from erenshor.domain.validation.items import ItemValidator
    from erenshor.cli.shared import (
        ContentTypeConfig,
        run_update_command,
    )

    run_update_command(
        config=ContentTypeConfig(
            name="items",
            generator_class=ItemGenerator,
            transformer_class=ItemTransformer,
            validator_class=ItemValidator,
            category="items",
            requires_parser_merger=True,
        ),
        filter_str=filter,
        validate=validate,
        validate_only=validate_only,
        dry_run=dry_run,
        db=db,
        cache_dir=cache_dir,
        output_dir=output_dir,
    )


@app.command("abilities")
def update_abilities(
    filter: Optional[str] = FilterOption,
    validate: bool = ValidateOption,
    validate_only: bool = ValidateOnlyOption,
    dry_run: bool = DryRunOption,
    batch_size: int = BatchSizeOption,
    db: Optional[Path] = DbOption,
    cache_dir: Optional[Path] = CacheDirOption,
    output_dir: Optional[Path] = OutputDirOption,
) -> None:
    """Update ability pages (spells and skills).

    Updates all ability pages with spell/skill information from the database.

    Examples:
      # Update all abilities
      erenshor-wiki update abilities

      # Update specific ability
      erenshor-wiki update abilities --filter "Fireball"

      # Only validate
      erenshor-wiki update abilities --validate-only
    """
    from erenshor.application.generators.abilities import AbilityGenerator
    from erenshor.application.transformers.abilities import AbilityTransformer
    from erenshor.domain.validation.abilities import AbilityValidator
    from erenshor.cli.shared import (
        ContentTypeConfig,
        run_update_command,
    )

    run_update_command(
        config=ContentTypeConfig(
            name="abilities",
            generator_class=AbilityGenerator,
            transformer_class=AbilityTransformer,
            validator_class=AbilityValidator,
            category="abilities",
            requires_parser_merger=False,
        ),
        filter_str=filter,
        validate=validate,
        validate_only=validate_only,
        dry_run=dry_run,
        db=db,
        cache_dir=cache_dir,
        output_dir=output_dir,
    )


@app.command("characters")
def update_characters(
    filter: Optional[str] = FilterOption,
    unique_only: bool = typer.Option(
        False,
        "--unique-only",
        help="Only update unique characters",
    ),
    hostile_only: bool = typer.Option(
        False,
        "--hostile-only",
        help="Only update hostile characters/enemies",
    ),
    friendly_only: bool = typer.Option(
        False,
        "--friendly-only",
        help="Only update friendly NPCs",
    ),
    validate: bool = ValidateOption,
    validate_only: bool = ValidateOnlyOption,
    dry_run: bool = DryRunOption,
    batch_size: int = BatchSizeOption,
    db: Optional[Path] = DbOption,
    cache_dir: Optional[Path] = CacheDirOption,
    output_dir: Optional[Path] = OutputDirOption,
) -> None:
    """Update character/enemy pages (NPCs and enemies).

    Updates all character and enemy pages with data from the database. This includes:
    - Enemy template (used for all characters regardless of friendly/hostile)
    - Stats, resists, drops
    - Coordinates (unique characters only)
    - Spawn information

    Examples:
      # Update all characters
      erenshor-wiki update characters

      # Update only unique characters
      erenshor-wiki update characters --unique-only

      # Update only hostile enemies
      erenshor-wiki update characters --hostile-only

      # Update specific character
      erenshor-wiki update characters --filter "Merchant"
    """
    from erenshor.application.generators.characters import CharacterGenerator
    from erenshor.application.transformers.characters import CharacterTransformer
    from erenshor.domain.validation.characters import CharacterValidator
    from erenshor.cli.shared import (
        ContentTypeConfig,
        run_update_command,
    )

    run_update_command(
        config=ContentTypeConfig(
            name="characters",
            generator_class=CharacterGenerator,
            transformer_class=CharacterTransformer,
            validator_class=CharacterValidator,
            category="characters",
            requires_parser_merger=False,
        ),
        filter_str=filter,
        validate=validate,
        validate_only=validate_only,
        dry_run=dry_run,
        db=db,
        cache_dir=cache_dir,
        output_dir=output_dir,
    )


@app.command("fishing")
def update_fishing(
    validate: bool = ValidateOption,
    validate_only: bool = ValidateOnlyOption,
    dry_run: bool = DryRunOption,
    db: Optional[Path] = DbOption,
    cache_dir: Optional[Path] = CacheDirOption,
    output_dir: Optional[Path] = OutputDirOption,
) -> None:
    """Update fishing zone tables.

    Updates the Fishing page with catch tables from the database.

    Examples:
      # Update fishing page
      erenshor-wiki update fishing

      # Only validate
      erenshor-wiki update fishing --validate-only
    """
    from erenshor.application.generators.fishing import FishingGenerator
    from erenshor.application.transformers.fishing import FishingTransformer
    from erenshor.domain.validation.fishing import FishingValidator
    from erenshor.cli.shared import (
        ContentTypeConfig,
        run_update_command,
    )

    run_update_command(
        config=ContentTypeConfig(
            name="fishing",
            generator_class=FishingGenerator,
            transformer_class=FishingTransformer,
            validator_class=FishingValidator,
            category="fishing",
            requires_parser_merger=False,
        ),
        filter_str=None,
        validate=validate,
        validate_only=validate_only,
        dry_run=dry_run,
        db=db,
        cache_dir=cache_dir,
        output_dir=output_dir,
    )


@app.command("overviews")
def update_overviews(
    validate: bool = ValidateOption,
    validate_only: bool = ValidateOnlyOption,
    dry_run: bool = DryRunOption,
    db: Optional[Path] = DbOption,
    cache_dir: Optional[Path] = CacheDirOption,
    output_dir: Optional[Path] = OutputDirOption,
) -> None:
    """Update overview pages (Weapons and Armor).

    Updates overview pages that aggregate weapon and armor stats from the database.

    Examples:
      # Update all overviews
      erenshor-wiki update overviews

      # Only validate
      erenshor-wiki update overviews --validate-only
    """
    from erenshor.application.generators.overviews import OverviewGenerator
    from erenshor.application.transformers.overviews import OverviewTransformer
    from erenshor.domain.validation.overviews import OverviewValidator
    from erenshor.cli.shared import (
        ContentTypeConfig,
        run_update_command,
    )

    run_update_command(
        config=ContentTypeConfig(
            name="overviews",
            generator_class=OverviewGenerator,
            transformer_class=OverviewTransformer,
            validator_class=OverviewValidator,
            category="items",
            requires_parser_merger=False,
        ),
        filter_str=None,
        validate=validate,
        validate_only=validate_only,
        dry_run=dry_run,
        db=db,
        cache_dir=cache_dir,
        output_dir=output_dir,
    )


@app.command("all")
def update_all(
    validate: bool = ValidateOption,
    validate_only: bool = ValidateOnlyOption,
    dry_run: bool = DryRunOption,
    batch_size: int = BatchSizeOption,
    db: Optional[Path] = DbOption,
    cache_dir: Optional[Path] = CacheDirOption,
    output_dir: Optional[Path] = OutputDirOption,
) -> None:
    """Update all content types in sequence.

    Runs all update commands in order:
    1. Items
    2. Abilities
    3. Characters
    4. Fishing
    5. Overviews

    This is the one-command workflow for updating everything.

    Examples:
      # Update everything with validation
      erenshor-wiki update all

      # Dry run to see what would change
      erenshor-wiki update all --dry-run

      # Only validate all content
      erenshor-wiki update all --validate-only

      # Update everything without validation (faster)
      erenshor-wiki update all --no-validate
    """
    from rich.panel import Panel

    console = Console()

    console.print(
        Panel(
            "Running all update commands in sequence...",
            title="Update All",
            border_style="blue",
        )
    )

    failed_commands: list[str] = []

    # Run each command in sequence
    # Each tuple contains (name, callable that invokes the command)
    commands: list[tuple[str, Any]] = [
        (
            "Items",
            lambda: update_items(
                None,
                validate,
                validate_only,
                dry_run,
                batch_size,
                db,
                cache_dir,
                output_dir,
            ),
        ),
        (
            "Abilities",
            lambda: update_abilities(
                None,
                validate,
                validate_only,
                dry_run,
                batch_size,
                db,
                cache_dir,
                output_dir,
            ),
        ),
        (
            "Characters",
            lambda: update_characters(
                None,
                False,
                False,
                False,
                validate,
                validate_only,
                dry_run,
                batch_size,
                db,
                cache_dir,
                output_dir,
            ),
        ),
        (
            "Fishing",
            lambda: update_fishing(
                validate, validate_only, dry_run, db, cache_dir, output_dir
            ),
        ),
        (
            "Overviews",
            lambda: update_overviews(
                validate, validate_only, dry_run, db, cache_dir, output_dir
            ),
        ),
    ]

    for idx, (name, cmd_func) in enumerate(commands, 1):
        console.print(f"\n[bold cyan]{idx}/5 - Running: {name}[/bold cyan]")
        console.print("─" * 80)

        try:
            cmd_func()
        except typer.Exit as e:
            if e.exit_code != 0:
                failed_commands.append(name)
                console.print(f"[bold red]✗ {name} failed[/bold red]")
            else:
                console.print(f"[bold green]✓ {name} completed[/bold green]")
        except Exception as e:
            failed_commands.append(name)
            console.print(f"[bold red]✗ {name} failed with error: {e}[/bold red]")

    # Print final summary
    console.print("\n" + "=" * 80)
    console.print("[bold]Final Summary[/bold]")
    console.print("=" * 80 + "\n")

    if failed_commands:
        console.print(
            f"[bold red]✗ {len(failed_commands)} command(s) failed:[/bold red]"
        )
        for cmd in failed_commands:
            console.print(f"  - {cmd}")
        console.print()
        raise typer.Exit(code=1)
    else:
        console.print(
            "[bold green]✓ All content types updated successfully![/bold green]\n"
        )

    console.print("Sequence completed:")
    console.print("  1. ✓ Items")
    console.print("  2. ✓ Abilities")
    console.print("  3. ✓ Characters")
    console.print("  4. ✓ Fishing")
    console.print("  5. ✓ Overviews")
