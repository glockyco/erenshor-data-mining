"""Image processing commands for game icons."""

from __future__ import annotations

import hashlib
import json
import time
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
from rich.table import Table

from erenshor.application.services.image_processor import ImageProcessor
from erenshor.domain.entities.page import EntityRef
from erenshor.domain.value_objects.entity_type import EntityType
from erenshor.infrastructure.config.toml_loader import load_config

__all__ = ["app", "process", "fetch", "compare"]

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
    upload_items: list[tuple[Path, str, str]] = []  # (file_path, wiki_filename, original_name)
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

            # Sanitize filename for MediaWiki (remove problematic characters)
            # MediaWiki doesn't allow: : | # < > [ ] { }
            sanitized_name = display_name
            sanitized_name = sanitized_name.replace(":", "")  # Remove colons
            sanitized_name = sanitized_name.replace("|", "")  # Remove pipes
            sanitized_name = sanitized_name.replace("#", "")  # Remove hashes

            wiki_filename = f"{sanitized_name}.png"
            upload_items.append((image_file, wiki_filename, display_name))
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
    redirects_to_create: list[tuple[str, str]] = []  # (original_name, sanitized_name)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Uploading images...", total=len(upload_items))

        for image_file, wiki_filename, original_name in upload_items:
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

                # Track redirect for dry-run
                original_filename = f"{original_name}.png"
                if original_filename != wiki_filename:
                    redirects_to_create.append((original_filename, wiki_filename))
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

                    # Track redirect only after successful upload
                    original_filename = f"{original_name}.png"
                    if original_filename != wiki_filename:
                        redirects_to_create.append((original_filename, wiki_filename))

                    # Add delay between uploads
                    if delay:
                        import time
                        time.sleep(delay)
                except WikiAPIError as e:
                    error_msg = str(e)
                    # Check if this is a "no change" error (file is identical)
                    if "fileexists-no-change" in error_msg:
                        # File is identical, treat as skip
                        stats["skipped"] += 1
                        # Don't count as processed since we didn't actually upload
                    else:
                        # Real error
                        console.print(f"[red]Failed to upload {wiki_filename}: {e}[/red]")
                        stats["failed"] += 1
                        processed += 1
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

        # Show redirects that would be created
        if redirects_to_create:
            console.print()
            console.print(f"[bold cyan]Redirects that would be created: {len(redirects_to_create)}[/bold cyan]")
            for original, sanitized in redirects_to_create[:10]:  # Show first 10
                console.print(f"  [yellow]File:{original}[/yellow] → [green]File:{sanitized}[/green]")
            if len(redirects_to_create) > 10:
                console.print(f"  [dim]... and {len(redirects_to_create) - 10} more[/dim]")
    else:
        console.print(f"[green]Upload complete[/green]")

        # Create redirect pages automatically
        if redirects_to_create:
            console.print()
            console.print(f"[bold cyan]Creating {len(redirects_to_create)} redirect pages...[/bold cyan]")

            redirect_stats = {"created": 0, "failed": 0}

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]Creating redirects...", total=len(redirects_to_create))

                for original, sanitized in redirects_to_create:
                    redirect_title = f"File:{original}"
                    redirect_content = f"#REDIRECT [[File:{sanitized}]]"

                    try:
                        client.upload_page(
                            title=redirect_title,
                            content=redirect_content,
                            summary="Automated redirect for sanitized filename",
                            minor=True,
                            bot=True,
                        )
                        redirect_stats["created"] += 1

                        # Add delay between redirects
                        if delay:
                            import time
                            time.sleep(delay)
                    except Exception as e:
                        console.print(f"[red]Failed to create redirect {redirect_title}: {e}[/red]")
                        redirect_stats["failed"] += 1

                    progress.advance(task)

            console.print()
            console.print(f"[green]Redirects created: {redirect_stats['created']}[/green]")
            if redirect_stats["failed"] > 0:
                console.print(f"[red]Redirects failed: {redirect_stats['failed']}[/red]")

    if stats["failed"] > 0:
        raise typer.Exit(1)


@app.command("fetch")
def fetch(
    variant: str = typer.Option("main", help="Variant to fetch images for"),
    force: bool = typer.Option(False, "--force", help="Re-download existing images"),
    delay: float = typer.Option(0.5, "--delay", help="Delay between downloads (seconds)"),
    batch_size: int = typer.Option(0, "--batch-size", help="Limit number of images to fetch (0 = all)"),
) -> None:
    """Fetch item and ability images from wiki for comparison.

    Downloads images from the wiki to a cache directory so you can compare
    them with locally processed images before uploading. Images are stored
    with the same naming convention as processed images (entitytype@RESOURCE_NAME.png).

    Examples:
        # Fetch first 10 images for testing
        images fetch --batch-size 10

        # Fetch all item and ability images
        images fetch

        # Force re-download
        images fetch --force

        # Custom delay between downloads
        images fetch --delay 1.0
    """
    from erenshor.infrastructure.wiki.client import WikiAPIClient
    from erenshor.cli.wiki_group import get_registry
    from erenshor.infrastructure.database.repositories import get_engine
    from erenshor.infrastructure.config.settings import load_settings
    import httpx

    console = Console()

    # Load configuration
    settings = load_settings()
    config = load_config()
    variant_config = config.get_variant_config(variant)

    if not variant_config:
        console.print(f"[red]Error: Variant '{variant}' not found in configuration[/red]")
        raise typer.Exit(1)

    # Setup paths
    db_path = Path(variant_config["database"])
    variant_root = Path(variant_config["database"]).parent
    cache_dir = variant_root / "image_cache"
    metadata_file = variant_root / "image_metadata.json"

    # Create cache directory
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Load existing metadata if present
    existing_metadata: dict[str, dict] = {}
    if metadata_file.exists() and not force:
        try:
            with open(metadata_file, "r") as f:
                existing_metadata = json.load(f)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load metadata: {e}[/yellow]")

    # Load registry to get items and spells
    if not db_path.exists():
        console.print(f"[red]Error: Database not found: {db_path}[/red]")
        console.print("Run 'erenshor export' first to create the database")
        raise typer.Exit(1)

    engine = get_engine(str(db_path))
    registry = get_registry(engine)

    console.print(f"[bold]Fetching images for variant: {variant}[/bold]")
    console.print(f"  Cache directory: {cache_dir}")
    console.print(f"  Metadata file: {metadata_file}")
    console.print()

    # Build list of images to fetch (items and spells only)
    images_to_fetch: list[tuple[EntityRef, str, str]] = []  # (entity, local_filename, wiki_filename)

    for page in registry.list_pages():
        for entity in registry.list_entities_for_page(page.title):
            # Only fetch items and spells
            if entity.entity_type in (EntityType.ITEM, EntityType.SPELL):
                # Local filename matches processed images: entitytype@RESOURCE_NAME.png
                local_filename = f"{entity.stable_key.replace(':', '@', 1)}.png"

                # Wiki filename is the sanitized display name
                display_name = registry.get_image_name(entity)
                sanitized_name = display_name.replace(":", "").replace("|", "").replace("#", "")
                wiki_filename = f"{sanitized_name}.png"

                images_to_fetch.append((entity, local_filename, wiki_filename))

    # Apply batch size limit
    total_available = len(images_to_fetch)
    if batch_size > 0:
        images_to_fetch = images_to_fetch[:batch_size]

    console.print(f"[bold]Found {total_available} images to fetch[/bold]")
    if batch_size > 0 and total_available > batch_size:
        console.print(f"[yellow]Batch limit: fetching {batch_size} images[/yellow]")
    console.print()

    # Initialize wiki client
    client = WikiAPIClient(api_url=settings.api_url)

    # Fetch images with progress bar
    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "missing": 0}
    metadata: dict[str, dict] = existing_metadata.copy()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Fetching images...", total=len(images_to_fetch))

        for entity, local_filename, wiki_filename in images_to_fetch:
            file_title = f"File:{wiki_filename}"
            cache_path = cache_dir / local_filename

            # Skip if already cached (unless force)
            if not force and local_filename in existing_metadata and cache_path.exists():
                stats["skipped"] += 1
                progress.advance(task)
                continue

            try:
                # Fetch imageinfo from wiki
                response = client._request({
                    "action": "query",
                    "format": "json",
                    "titles": file_title,
                    "prop": "imageinfo",
                    "iiprop": "url|sha1|size",
                    "formatversion": "2",
                })

                pages = response.get("query", {}).get("pages", [])
                if not pages or pages[0].get("missing"):
                    # Image doesn't exist on wiki yet
                    stats["missing"] += 1
                    progress.advance(task)
                    continue

                imageinfo_list = pages[0].get("imageinfo", [])
                if not imageinfo_list:
                    stats["missing"] += 1
                    progress.advance(task)
                    continue

                imageinfo = imageinfo_list[0]
                image_url = imageinfo.get("url")
                sha1 = imageinfo.get("sha1")
                size = imageinfo.get("size", 0)

                if not image_url or not sha1:
                    console.print(f"[yellow]Warning: Missing URL or SHA-1 for {local_filename}[/yellow]")
                    stats["failed"] += 1
                    progress.advance(task)
                    continue

                # Download the image
                img_response = httpx.get(image_url, timeout=30.0)
                img_response.raise_for_status()

                # Save to cache using local filename (matches processed images)
                with open(cache_path, "wb") as f:
                    f.write(img_response.content)

                # Store metadata using local filename as key
                metadata[local_filename] = {
                    "sha1": sha1,
                    "size": size,
                    "url": image_url,
                    "wiki_filename": wiki_filename,
                    "entity_type": entity.entity_type.value,
                    "resource_name": entity.resource_name,
                }

                stats["downloaded"] += 1

                # Add delay between downloads
                if delay > 0:
                    time.sleep(delay)

            except httpx.HTTPStatusError as e:
                console.print(f"[red]HTTP error fetching {local_filename}: {e}[/red]")
                stats["failed"] += 1
            except Exception as e:
                console.print(f"[red]Failed to fetch {local_filename}: {e}[/red]")
                stats["failed"] += 1

            progress.advance(task)

    # Save metadata
    try:
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
    except Exception as e:
        console.print(f"[red]Error saving metadata: {e}[/red]")

    # Print summary
    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Downloaded: {stats['downloaded']}")
    console.print(f"  Skipped (cached): {stats['skipped']}")
    console.print(f"  Missing on wiki: {stats['missing']}")
    console.print(f"  Failed: {stats['failed']}")
    console.print(f"  Total: {len(images_to_fetch)}")
    console.print()
    console.print(f"[green]Images cached to: {cache_dir}[/green]")
    console.print(f"[green]Metadata saved to: {metadata_file}[/green]")

    if stats["missing"] > 0:
        console.print()
        console.print(f"[yellow]{stats['missing']} images not yet on wiki (will be uploaded)[/yellow]")

    if stats["failed"] > 0:
        raise typer.Exit(1)


@app.command("compare")
def compare(
    variant: str = typer.Option("main", help="Variant to compare images for"),
    show_all: bool = typer.Option(False, "--show-all", help="Show all files (not just differences)"),
    limit: int = typer.Option(0, "--limit", help="Limit output to N files (0 = all)"),
) -> None:
    """Compare SHA-1 hashes between cached wiki images and local processed images.

    Shows which images are identical, different, new, or missing.

    Examples:
        # Compare all images
        images compare

        # Show all files (not just differences)
        images compare --show-all

        # Show first 20 differences
        images compare --limit 20
    """
    console = Console()

    # Load configuration
    config = load_config()
    variant_config = config.get_variant_config(variant)

    if not variant_config:
        console.print(f"[red]Error: Variant '{variant}' not found in configuration[/red]")
        raise typer.Exit(1)

    # Setup paths
    variant_root = Path(variant_config["database"]).parent
    cache_dir = variant_root / "image_cache"
    processed_dir = Path(variant_config.get("images_output", f"variants/{variant}/images/processed"))
    metadata_file = variant_root / "image_metadata.json"

    # Check if cache exists
    if not metadata_file.exists():
        console.print("[red]Error: Image metadata not found[/red]")
        console.print("Run 'images fetch' first to download wiki images")
        raise typer.Exit(1)

    if not processed_dir.exists():
        console.print(f"[red]Error: Processed images directory not found: {processed_dir}[/red]")
        console.print("Run 'images process' first to process images")
        raise typer.Exit(1)

    # Load wiki metadata
    with open(metadata_file, "r") as f:
        wiki_metadata: dict[str, dict] = json.load(f)

    console.print(f"[bold]Comparing images for variant: {variant}[/bold]")
    console.print(f"  Wiki cache: {cache_dir}")
    console.print(f"  Processed: {processed_dir}")
    console.print()

    # Scan processed images and compute SHA-1
    console.print("[dim]Computing SHA-1 hashes for processed images...[/dim]")
    processed_files = list(processed_dir.glob("*.png"))
    local_hashes: dict[str, str] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Hashing...", total=len(processed_files))

        for img_file in processed_files:
            sha1 = hashlib.sha1()
            with open(img_file, "rb") as f:
                while chunk := f.read(8192):
                    sha1.update(chunk)
            local_hashes[img_file.name] = sha1.hexdigest()
            progress.advance(task)

    # Compare hashes
    identical: list[tuple[str, str]] = []  # (filename, sha1)
    different: list[tuple[str, str, str]] = []  # (filename, wiki_sha1, local_sha1)
    new_local: list[str] = []  # Only in processed (not on wiki)
    missing_local: list[str] = []  # Only in wiki (not processed locally)

    # Check all processed files
    for filename, local_sha1 in local_hashes.items():
        wiki_meta = wiki_metadata.get(filename)
        if wiki_meta:
            wiki_sha1 = wiki_meta["sha1"]
            if wiki_sha1 == local_sha1:
                identical.append((filename, local_sha1))
            else:
                different.append((filename, wiki_sha1, local_sha1))
        else:
            new_local.append(filename)

    # Check for wiki files not in processed
    for filename in wiki_metadata.keys():
        if filename not in local_hashes:
            missing_local.append(filename)

    # Print summary
    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Identical (no upload needed): {len(identical)}")
    console.print(f"  [yellow]Different (needs upload): {len(different)}[/yellow]")
    console.print(f"  [cyan]New (not on wiki): {len(new_local)}[/cyan]")
    console.print(f"  [dim]Missing locally: {len(missing_local)}[/dim]")
    console.print(f"  Total processed: {len(processed_files)}")
    console.print(f"  Total on wiki: {len(wiki_metadata)}")

    # Show differences in detail
    if different or new_local or (show_all and identical):
        console.print()

        # Prepare items to show
        items_to_show: list[tuple[str, str, str]] = []  # (filename, status, details)

        if show_all:
            for filename, sha1 in identical:
                items_to_show.append((filename, "[green]Identical[/green]", sha1[:8]))

        for filename, wiki_sha1, local_sha1 in different:
            items_to_show.append((
                filename,
                "[yellow]Different[/yellow]",
                f"Wiki: {wiki_sha1[:8]}, Local: {local_sha1[:8]}"
            ))

        for filename in new_local:
            local_sha1 = local_hashes[filename]
            items_to_show.append((filename, "[cyan]New[/cyan]", local_sha1[:8]))

        # Apply limit
        if limit > 0:
            items_to_show = items_to_show[:limit]

        # Show table
        table = Table(title="Image Comparison")
        table.add_column("Filename", style="white", overflow="fold")
        table.add_column("Status", justify="center")
        table.add_column("SHA-1", style="dim")

        for filename, status, details in items_to_show:
            table.add_row(filename, status, details)

        console.print(table)

        if limit > 0 and len(items_to_show) >= limit:
            total_remaining = len(different) + len(new_local) + (len(identical) if show_all else 0) - limit
            if total_remaining > 0:
                console.print(f"\n[dim]... and {total_remaining} more (use --limit to show more)[/dim]")

    # Show next steps
    if different or new_local:
        console.print()
        console.print("[yellow]Next steps:[/yellow]")
        console.print(f"  → Upload {len(different) + len(new_local)} images: images upload")
        console.print("  → Preview upload: images upload --dry-run")

    # Exit with error if there are differences (useful for CI/CD)
    if different or new_local:
        raise typer.Exit(1)
