"""Image processing commands for game icons."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from erenshor.application.services.image_processor import ImageProcessor
from erenshor.domain.entities.page import EntityRef
from erenshor.domain.value_objects.entity_type import EntityType
from erenshor.infrastructure.config.toml_loader import load_config

__all__ = ["app", "process"]

app = typer.Typer(help="Image processing operations")


@app.command("process")
def process(
    variant: str = typer.Option("main", help="Variant to process images for"),
    force: bool = typer.Option(False, "--force", help="Reprocess existing images"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without processing"),
) -> None:
    """Process game images: resize, pad, and add borders.

    Extracts icon names from the database, locates PNG files in Unity assets,
    and processes them into wiki-ready images (150x150px, with borders for spells/skills).

    Examples:
        # Process all images for main variant
        images process

        # Process for playtest variant
        images process --variant playtest

        # Reprocess all images (ignore existing)
        images process --force

        # Preview what would be processed
        images process --dry-run
    """
    console = Console()

    # Load configuration
    config = load_config()
    variant_config = config.get_variant_config(variant)

    if not variant_config:
        console.print(f"[red]Error: Variant '{variant}' not found in configuration[/red]")
        raise typer.Exit(1)

    # Setup paths
    db_path = Path(variant_config["database"])
    unity_project = Path(variant_config["unity_project"])
    texture_dir = unity_project / "Assets" / "Texture2D"
    output_dir = Path(variant_config.get("images_output", f"variants/{variant}/images/processed"))

    # Verify paths
    if not db_path.exists():
        console.print(f"[red]Error: Database not found: {db_path}[/red]")
        console.print("Run 'erenshor export' first to create the database")
        raise typer.Exit(1)

    if not texture_dir.exists():
        console.print(f"[red]Error: Texture directory not found: {texture_dir}[/red]")
        console.print("Run 'erenshor extract' first to extract Unity assets")
        raise typer.Exit(1)

    # Load registry for name overrides (uses get_registry for automatic rebuild)
    from erenshor.cli.wiki_group import get_registry
    from erenshor.infrastructure.database.repositories import get_engine

    registry = None
    try:
        engine = get_engine(str(db_path))
        registry = get_registry(engine)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load registry: {e}[/yellow]")

    # Initialize processor
    processor = ImageProcessor(
        db_path=db_path,
        texture_dir=texture_dir,
        output_dir=output_dir,
        registry=registry,
    )

    console.print(f"[bold]Processing images for variant: {variant}[/bold]")
    console.print(f"  Database: {db_path}")
    console.print(f"  Textures: {texture_dir}")
    console.print(f"  Output: {output_dir}")
    if dry_run:
        console.print("[yellow]  Mode: DRY-RUN (no files will be written)[/yellow]")
    if force:
        console.print("[yellow]  Force: Reprocessing all images[/yellow]")
    console.print()

    # Process images with progress bar
    stats = {"processed": 0, "skipped": 0, "failed": 0}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Processing images...", total=None
        )

        for result in processor.process_images(force=force):
            if result.action == "processed":
                stats["processed"] += 1
                if not dry_run and result.output_path:
                    # Actually write the file (processor already did this)
                    pass
            elif result.action == "skipped":
                stats["skipped"] += 1
            elif result.action == "failed":
                stats["failed"] += 1
                if result.message:
                    console.print(
                        f"[red]Failed: {result.entity_name} ({result.entity_type}): {result.message}[/red]"
                    )

            progress.update(task, advance=1)

        # Set total after we know it
        progress.update(task, total=sum(stats.values()))

    # Print summary
    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Processed: {stats['processed']}")
    console.print(f"  Skipped: {stats['skipped']}")
    console.print(f"  Failed: {stats['failed']}")
    console.print(f"  Total: {sum(stats.values())}")

    if stats["failed"] > 0:
        console.print("[yellow]Some images failed to process (see errors above)[/yellow]")
        raise typer.Exit(1)

    if dry_run:
        console.print("[yellow]DRY-RUN: No files were written[/yellow]")
    else:
        console.print(f"[green]Images written to: {output_dir}[/green]")


@app.command("upload")
def upload(
    variant: str = typer.Option("main", help="Variant to upload images for"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without uploading"),
    force: bool = typer.Option(False, "--force", help="Re-upload existing images"),
    filter: str = typer.Option(None, "--filter", help="Filter images by name"),
    batch_size: int = typer.Option(None, "--batch-size", help="Max images to upload"),
    delay: float = typer.Option(None, "--delay", help="Delay between uploads (seconds)"),
) -> None:
    """Upload processed images to MediaWiki.

    Uploads images to the wiki using the MediaWiki Upload API.
    Requires bot credentials to be configured.

    Examples:
        # Upload all images (dry-run first)
        images upload --dry-run

        # Upload for real
        images upload

        # Force re-upload existing images
        images upload --force

        # Upload specific image
        images upload --filter "Sword"

        # Upload with custom batch size and delay
        images upload --batch-size 50 --delay 2.0
    """
    from erenshor.infrastructure.wiki.auth import BotCredentials, MediaWikiAuth
    from erenshor.infrastructure.wiki.client import WikiAPIClient
    from erenshor.cli.wiki_group import get_registry
    from erenshor.infrastructure.database.repositories import get_engine
    from erenshor.domain.exceptions import WikiAPIError
    from erenshor.infrastructure.config.settings import load_settings

    console = Console()

    # Load configuration using the modern settings system (same as upload.py)
    settings = load_settings()

    # Check credentials (even in dry-run, warn if missing)
    if not settings.bot_username or not settings.bot_password:
        if dry_run:
            console.print(
                "[yellow]Warning: Bot credentials not configured "
                "(set ERENSHOR_BOT_USERNAME and ERENSHOR_BOT_PASSWORD)[/yellow]"
            )
        else:
            console.print("[red]Error: Bot credentials required for upload[/red]")
            console.print(
                "Set ERENSHOR_BOT_USERNAME and ERENSHOR_BOT_PASSWORD in .env or environment"
            )
            raise typer.Exit(1)

    # Load legacy config for variant-specific paths (until images are migrated)
    config = load_config()
    variant_config = config.get_variant_config(variant)

    if not variant_config:
        console.print(f"[red]Error: Variant '{variant}' not found in configuration[/red]")
        raise typer.Exit(1)

    # Setup paths
    images_dir = Path(variant_config.get("images_output", f"variants/{variant}/images/processed"))
    db_path = Path(variant_config["database"])

    if not images_dir.exists():
        console.print(f"[red]Error: Processed images directory not found: {images_dir}[/red]")
        console.print("Run 'images process' first")
        raise typer.Exit(1)

    # Load registry for name mapping
    engine = get_engine(str(db_path))
    registry = get_registry(engine)

    # Apply config defaults if not specified
    batch_size = batch_size if batch_size is not None else settings.upload_batch_size
    delay = delay if delay is not None else settings.upload_delay

    # Treat batch_size of 0 as unlimited
    if batch_size == 0:
        batch_size = None

    # Initialize wiki client
    client = WikiAPIClient(api_url=settings.api_url)

    # Authenticate (unless dry-run) - EXACT same pattern as upload.py
    if not dry_run:
        if not settings.bot_username or not settings.bot_password:
            console.print("[red]Error: Bot credentials not configured[/red]")
            raise typer.Exit(1)
        credentials = BotCredentials(
            username=settings.bot_username,
            password=settings.bot_password,
            api_url=settings.api_url,
        )
        auth = MediaWikiAuth(credentials)
        try:
            if not auth.login():
                console.print("[red]Error: Authentication failed (wrong credentials)[/red]")
                raise typer.Exit(1)
        except WikiAPIError as e:
            console.print(f"[red]Error: Authentication failed: {e}[/red]")
            raise typer.Exit(1)
        client.set_auth_session(auth.session)

    # Build upload list: resource name → display name mapping
    # Images are stored as resource names (e.g., "GEN - KGTI.png")
    # We need to map them to display names for wiki upload
    upload_items: list[tuple[Path, str]] = []  # (file_path, wiki_filename)
    skipped_excluded = 0

    all_image_files = sorted(images_dir.glob("*.png"))
    if filter:
        all_image_files = [f for f in all_image_files if filter.lower() in f.stem.lower()]

    # Map resource names to entities for quick lookup
    entity_map: dict[str, EntityRef] = {}
    for page in registry.list_pages():
        for entity in registry.list_entities_for_page(page.title):
            if entity.resource_name:
                # Key format: "entity_type:resource_name"
                key = entity.stable_key
                entity_map[key] = entity

    for image_file in all_image_files:
        # Extract entity type and resource name from filename
        # Format: "entitytype@RESOURCE_NAME.png" (e.g., "item@GEN - KGTI.png")
        # This matches the stable_key format but with @ instead of :
        if "@" not in image_file.stem:
            # Skip malformed filenames
            skipped_excluded += 1
            if dry_run:
                console.print(f"[dim]Skipping malformed filename: {image_file.name}[/dim]")
            continue

        # Convert filename back to stable key format (replace @ with :)
        stable_key = image_file.stem.replace("@", ":", 1)
        entity = entity_map.get(stable_key)

        if entity:
            # Get display name from registry for wiki upload
            display_name = registry.get_image_name(entity)
            # Sanitize display name for wiki filename (MediaWiki handles special chars)
            wiki_filename = f"{display_name}.png"
            upload_items.append((image_file, wiki_filename))
        else:
            # Not in registry = excluded entity
            skipped_excluded += 1
            if dry_run:
                console.print(f"[dim]Skipping excluded: {image_file.name}[/dim]")

    console.print(f"[bold]Found {len(upload_items)} images to upload[/bold]")
    if skipped_excluded > 0:
        console.print(f"[dim]Skipped {skipped_excluded} images for excluded entities[/dim]")
    if batch_size and len(upload_items) > batch_size:
        console.print(f"[yellow]Batch limit: {batch_size} images[/yellow]")
    if not dry_run and delay:
        console.print(f"[dim]Delay between uploads: {delay}s[/dim]")
    console.print()

    # Fetch existing files once (avoid rate limiting from individual checks)
    existing_files: set[str] = set()
    if not force and not dry_run:
        console.print("[dim]Fetching existing files from wiki...[/dim]")
        try:
            # List all files in File: namespace (namespace 6)
            file_titles = client.list_pages(namespace=6)
            existing_files = set(file_titles)
            console.print(f"[dim]Found {len(existing_files)} existing files on wiki[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not fetch file list: {e}[/yellow]")
            console.print("[yellow]Proceeding without existence checks[/yellow]")

    # Upload images with progress bar
    stats = {"uploaded": 0, "skipped": 0, "failed": 0}
    processed = 0  # Uploaded + failed (not skipped)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Uploading images...", total=len(upload_items))

        for image_file, wiki_filename in upload_items:
            # Check batch limit (skipped don't count)
            if batch_size and processed >= batch_size:
                break

            # Check if file already exists (unless force)
            if not force and not dry_run:
                file_title = f"File:{wiki_filename}"
                if file_title in existing_files:
                    stats["skipped"] += 1
                    progress.advance(task)
                    continue

            # Upload
            if dry_run:
                console.print(f"[dim]Would upload: {image_file.name} → {wiki_filename}[/dim]")
                stats["uploaded"] += 1
                processed += 1
            else:
                try:
                    client.upload_file(
                        file_path=str(image_file),
                        filename=wiki_filename,
                        comment="Automated icon upload",
                        text="",  # TODO: Add template with categories
                        ignore_warnings=True,  # Allow duplicate content (same icon for multiple items)
                    )
                    stats["uploaded"] += 1
                    processed += 1

                    # Add delay between uploads
                    if delay:
                        import time
                        time.sleep(delay)
                except Exception as e:
                    console.print(f"[red]Failed to upload {wiki_filename}: {e}[/red]")
                    stats["failed"] += 1
                    processed += 1

            progress.advance(task)

    # Print summary
    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Uploaded: {stats['uploaded']}")
    console.print(f"  Skipped: {stats['skipped']}")
    console.print(f"  Failed: {stats['failed']}")
    console.print(f"  Total: {len(upload_items)}")

    if dry_run:
        console.print("[yellow]DRY-RUN: No files were uploaded[/yellow]")
    else:
        console.print(f"[green]Upload complete[/green]")

    if stats["failed"] > 0:
        raise typer.Exit(1)
