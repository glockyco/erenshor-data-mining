"""Image processing commands for game icons."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

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
from erenshor.registry.resolver import RegistryResolver

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

__all__ = ["app"]

app = typer.Typer(help="Image processing operations")


@app.command("process")
def process(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Reprocess existing images")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without processing")] = False,
) -> None:
    """Process game images: resize, pad, and add borders.

    Extracts icon names from the registry, locates PNG files in Unity assets,
    and processes them into wiki-ready images (150x150px, with borders for spells/skills).

    Examples:
        # Process all images for main variant
        erenshor images process

        # Process for playtest variant
        erenshor images process --variant playtest

        # Reprocess all images (ignore existing)
        erenshor images process --force

        # Preview what would be processed
        erenshor images process --dry-run
    """
    console = Console()
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]

    # Setup paths
    unity_project = variant_config.resolved_unity_project(cli_ctx.repo_root)
    texture_dir = unity_project / "ExportedProject" / "Assets" / "Texture2D"
    output_dir = unity_project.parent / "images" / "processed"

    # Verify paths
    if not texture_dir.exists():
        console.print(f"[red]Error: Texture directory not found: {texture_dir}[/red]")
        console.print("Run 'erenshor extract rip' first to extract Unity assets")
        raise typer.Exit(1)

    # Load registry resolver
    console.print("[dim]Loading registry...[/dim]")
    wiki_dir = variant_config.resolved_wiki(cli_ctx.repo_root)
    registry_db_path = wiki_dir / "registry.db"
    db_path = variant_config.resolved_database(cli_ctx.repo_root)
    mapping_json_path = cli_ctx.repo_root / "mapping.json"
    resolver = RegistryResolver(registry_db_path, game_db_path=db_path, mapping_json_path=mapping_json_path)

    # Initialize processor
    processor = ImageProcessor(
        texture_dir=texture_dir,
        output_dir=output_dir,
        resolver=resolver,
        game_db_path=db_path,
    )

    console.print(f"[bold]Processing images for variant: {cli_ctx.variant}[/bold]")
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
        task = progress.add_task("[cyan]Processing images...", total=None)

        for result in processor.process_images(force=force):
            if result.action == "processed":
                stats["processed"] += 1
                if not dry_run and result.output_path:
                    # Processor already wrote the file
                    pass
            elif result.action == "skipped":
                stats["skipped"] += 1
            elif result.action == "failed":
                stats["failed"] += 1
                if result.message:
                    console.print(f"[red]Failed: {result.entity_name} ({result.entity_type}): {result.message}[/red]")

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
    ctx: typer.Context,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without uploading")] = False,
    force: Annotated[bool, typer.Option("--force", help="Re-upload existing images")] = False,
    batch_size: Annotated[int | None, typer.Option("--batch-size", help="Max images to upload (0=unlimited)")] = None,
    stable_keys: Annotated[
        str | None, typer.Option("--stable-keys", help="File with stable keys to upload (one per line, or - for stdin)")
    ] = None,
) -> None:
    """Upload processed images to MediaWiki.

    Uploads processed images to the wiki using the MediaWiki Upload API.
    Requires bot credentials to be configured.

    Examples:
        # Upload all images (dry-run first)
        erenshor images upload --dry-run

        # Upload for real
        erenshor images upload

        # Force re-upload existing images
        erenshor images upload --force

        # Upload with batch limit
        erenshor images upload --batch-size 50

        # Upload only specific stable keys from file
        erenshor images upload --stable-keys new-entities.txt

        # Upload from stdin
        cat new-entities.txt | erenshor images upload --stable-keys -
    """
    from erenshor.infrastructure.wiki.client import MediaWikiAPIError, MediaWikiClient

    console = Console()
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]

    # Check bot credentials
    wiki_config = cli_ctx.config.global_.mediawiki
    bot_username = wiki_config.bot_username
    bot_password = wiki_config.bot_password
    api_url = wiki_config.api_url

    if not bot_username or not bot_password:
        if dry_run:
            console.print("[yellow]Warning: Bot credentials not configured[/yellow]")
        else:
            console.print("[red]Error: Bot credentials required for upload[/red]")
            console.print("Configure bot_username and bot_password in config.toml")
            raise typer.Exit(1)

    # Setup paths
    unity_project = variant_config.resolved_unity_project(cli_ctx.repo_root)
    images_dir = unity_project.parent / "images" / "processed"

    if not images_dir.exists():
        console.print(f"[red]Error: Processed images directory not found: {images_dir}[/red]")
        console.print("Run 'erenshor images process' first")
        raise typer.Exit(1)

    # Load registry resolver
    console.print("[dim]Loading registry...[/dim]")
    wiki_dir = variant_config.resolved_wiki(cli_ctx.repo_root)
    registry_db_path = wiki_dir / "registry.db"
    db_path = variant_config.resolved_database(cli_ctx.repo_root)
    mapping_json_path = cli_ctx.repo_root / "mapping.json"
    resolver = RegistryResolver(registry_db_path, game_db_path=db_path, mapping_json_path=mapping_json_path)

    # Initialize wiki client
    client = MediaWikiClient(
        api_url=api_url,
        bot_username=bot_username,
        bot_password=bot_password,
    )

    # Authenticate (unless dry-run)
    if not dry_run:
        try:
            console.print("[dim]Authenticating...[/dim]")
            client.login()
        except MediaWikiAPIError as e:
            console.print(f"[red]Authentication failed: {e}[/red]")
            raise typer.Exit(1) from e

    console.print(f"[bold]Uploading images for variant: {cli_ctx.variant}[/bold]")
    console.print(f"  Images: {images_dir}")
    console.print(f"  Wiki: {api_url}")
    if dry_run:
        console.print("[yellow]  Mode: DRY-RUN (no files will be uploaded)[/yellow]")
    if force:
        console.print("[yellow]  Force: Re-uploading all images[/yellow]")
    if batch_size:
        console.print(f"[yellow]  Batch limit: {batch_size} images[/yellow]")
    console.print()

    # Load stable keys filter if provided
    stable_keys_filter: set[str] | None = None
    if stable_keys:
        import sys

        try:
            if stable_keys == "-":
                # Read from stdin
                lines = sys.stdin.readlines()
            else:
                # Read from file
                with Path(stable_keys).open() as f:
                    lines = f.readlines()

            # Parse stable keys (strip whitespace, skip empty lines and comments)
            stable_keys_filter = {line.strip() for line in lines if line.strip() and not line.strip().startswith("#")}
            console.print(f"[dim]Filtering to {len(stable_keys_filter)} stable keys from {stable_keys}[/dim]")
        except Exception as e:
            console.print(f"[red]Error reading stable keys from {stable_keys}: {e}[/red]")
            raise typer.Exit(1) from e

    # Build upload list from processed images
    all_image_files = sorted(images_dir.glob("*.png"))
    upload_items: list[tuple[Path, str]] = []  # (file_path, wiki_filename)
    skipped_excluded = 0
    skipped_filtered = 0

    for image_file in all_image_files:
        # Extract stable_key from filename (format: "entitytype@resource_name.png")
        if "@" not in image_file.stem:
            skipped_excluded += 1
            continue

        # Convert filename back to stable key (replace @ with :)
        stable_key = image_file.stem.replace("@", ":", 1)

        # Apply stable keys filter if provided
        if stable_keys_filter and stable_key not in stable_keys_filter:
            skipped_filtered += 1
            continue

        # Check if entity is excluded
        try:
            image_name = resolver.resolve_image_name(stable_key)
        except ValueError:
            # Entity not in registry or excluded
            skipped_excluded += 1
            continue

        if image_name is None:
            # Entity is excluded
            skipped_excluded += 1
            continue

        # Wiki filename is image_name + .png
        wiki_filename = f"{image_name}.png"
        upload_items.append((image_file, wiki_filename))

    console.print(f"[bold]Found {len(upload_items)} images to upload[/bold]")
    if skipped_excluded > 0:
        console.print(f"[dim]Skipped {skipped_excluded} excluded entities[/dim]")
    if skipped_filtered > 0:
        console.print(f"[dim]Skipped {skipped_filtered} filtered out (not in stable keys list)[/dim]")
    console.print()

    # Apply batch limit
    if batch_size and batch_size > 0:
        upload_items = upload_items[:batch_size]
        console.print(f"[yellow]Processing first {len(upload_items)} images (batch limit)[/yellow]")

    # Upload images with progress bar
    stats = {"uploaded": 0, "skipped": 0, "failed": 0}

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
            # Check if file already exists (unless force or dry-run)
            if not force and not dry_run:
                try:
                    if client.page_exists(f"File:{wiki_filename}"):
                        stats["skipped"] += 1
                        progress.advance(task)
                        continue
                except MediaWikiAPIError:
                    # If check fails, proceed with upload attempt
                    pass

            # Upload
            if dry_run:
                console.print(f"[dim]Would upload: {image_file.name} → File:{wiki_filename}[/dim]")
                stats["uploaded"] += 1
            else:
                try:
                    client.upload_file(
                        file_path=str(image_file),
                        filename=wiki_filename,
                        comment="Automated icon upload",
                        text="",  # Could add image metadata template here
                        ignore_warnings=True,  # Allow duplicate content
                        bot=True,
                    )
                    stats["uploaded"] += 1
                except MediaWikiAPIError as e:
                    error_msg = str(e)
                    # Check if this is a "no change" error (file is identical)
                    if "fileexists-no-change" in error_msg or "duplicate" in error_msg:
                        stats["skipped"] += 1
                    else:
                        console.print(f"[red]Failed: {wiki_filename}: {e}[/red]")
                        stats["failed"] += 1

            progress.advance(task)

    # Close client
    client.close()

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
        console.print("[green]Upload complete[/green]")

    if stats["failed"] > 0:
        raise typer.Exit(1)
