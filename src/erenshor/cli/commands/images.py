"""Image processing commands for game icons with lifecycle management."""

from __future__ import annotations

import json
import shutil
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
from rich.table import Table

from erenshor.application.services.image_comparator import ImageComparator
from erenshor.application.services.image_processor import ImageProcessor
from erenshor.application.services.image_registry import ImageRegistry
from erenshor.registry.resolver import RegistryResolver

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext

__all__ = ["app"]

app = typer.Typer(help="Image processing operations")


@app.command("process")
def process(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Reprocess all images")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without processing")] = False,
) -> None:
    """Process game images with version tracking and registry integration.

    Backs up current/ to previous/, processes all icons from Unity assets,
    and registers metadata in the image registry for change detection.

    Examples:
        # Process new/changed images only
        erenshor images process

        # Reprocess all images (force mode)
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
    images_base_dir = unity_project.parent / "images"
    current_dir = images_base_dir / "current"
    previous_dir = images_base_dir / "previous"
    registry_db_path = images_base_dir / "registry.db"

    # Handle legacy processed/ directory migration
    legacy_dir = images_base_dir / "processed"
    if legacy_dir.exists() and not current_dir.exists():
        console.print("[yellow]Migrating legacy 'processed/' directory to 'current/'...[/yellow]")
        legacy_dir.rename(current_dir)
        console.print("[green]✓[/green] Migration complete")

    # Verify paths
    if not texture_dir.exists():
        console.print(f"[red]Error: Texture directory not found: {texture_dir}[/red]")
        console.print("Run 'erenshor extract rip' first to extract Unity assets")
        raise typer.Exit(1)

    # Load registry resolver
    console.print("[dim]Loading registry...[/dim]")
    wiki_dir = variant_config.resolved_wiki(cli_ctx.repo_root)
    wiki_registry_db_path = wiki_dir / "registry.db"
    db_path = variant_config.resolved_database(cli_ctx.repo_root)
    mapping_json_path = cli_ctx.repo_root / "mapping.json"
    resolver = RegistryResolver(wiki_registry_db_path, game_db_path=db_path, mapping_json_path=mapping_json_path)

    # Initialize registry
    registry = ImageRegistry(registry_db_path)

    # Initialize processor
    processor = ImageProcessor(
        texture_dir=texture_dir,
        output_dir=current_dir,
        resolver=resolver,
        game_db_path=db_path,
    )

    console.print(f"[bold]Processing images for variant: {cli_ctx.variant}[/bold]")
    console.print(f"  Textures: {texture_dir}")
    console.print(f"  Output: {current_dir}")
    if dry_run:
        console.print("[yellow]  Mode: DRY-RUN (no files will be written)[/yellow]")
    if force:
        console.print("[yellow]  Force: Reprocessing all images[/yellow]")
    console.print()

    # Step 1: Backup current/ → previous/ (if exists and not dry-run)
    if current_dir.exists() and not dry_run:
        console.print("[dim]Backing up current/ → previous/...[/dim]")
        if previous_dir.exists():
            shutil.rmtree(previous_dir)
        shutil.copytree(current_dir, previous_dir)
        file_count = len(list(current_dir.glob("*.png")))
        console.print(f"[green]✓[/green] Backed up {file_count} images")
        console.print()

    # Step 2: Process images with progress bar
    if not dry_run:
        current_dir.mkdir(parents=True, exist_ok=True)

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

        for image_info in processor.discover_images():
            # Get output filename
            filename = image_info.stable_key.replace(":", "@", 1).replace("/", "_").replace("\\", "_") + ".png"
            output_path = current_dir / filename

            # Check if should reprocess
            should_process = force or not registry.should_reprocess(
                image_info.stable_key, image_info.source_path or Path()
            )

            if not force and output_path.exists() and not should_process:
                stats["skipped"] += 1
                progress.update(task, advance=1)
                continue

            # Check if source exists
            if not image_info.source_path or not image_info.source_path.exists():
                stats["failed"] += 1
                console.print(f"[red]Failed: {image_info.entity_name} - Source not found: {image_info.icon_name}[/red]")
                progress.update(task, advance=1)
                continue

            # Process the image
            if dry_run:
                stats["processed"] += 1
            else:
                try:
                    result = processor.process_single_image(image_info, output_path)

                    # Register in registry
                    registry.register_processed_image(
                        stable_key=image_info.stable_key,
                        image_info=image_info,
                        processing_result=result,
                    )

                    stats["processed"] += 1
                except Exception as e:
                    stats["failed"] += 1
                    console.print(f"[red]Failed: {image_info.entity_name} - {e}[/red]")

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

    if dry_run:
        console.print()
        console.print("[yellow]DRY-RUN: No files were written[/yellow]")
    else:
        console.print()
        console.print(f"[green]✓ Images written to: {current_dir}[/green]")
        console.print("[dim]Run 'erenshor images compare' to detect changes[/dim]")

    if stats["failed"] > 0:
        raise typer.Exit(1)


@app.command("compare")
def compare(
    ctx: typer.Context,
    similarity: Annotated[float, typer.Option("--similarity", help="Similarity threshold (0.0-1.0)")] = 0.95,
) -> None:
    """Compare current vs previous images to detect changes.

    Uses perceptual hashing to detect visual differences between current
    and previous image versions. Similarity threshold determines what
    counts as "unchanged" (default 95% = visually similar).

    Examples:
        # Default threshold (95%)
        erenshor images compare

        # Stricter (99% similar required)
        erenshor images compare --similarity 0.99

        # More lenient (90% similar required)
        erenshor images compare --similarity 0.90
    """
    console = Console()
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]

    # Setup paths
    unity_project = variant_config.resolved_unity_project(cli_ctx.repo_root)
    images_base_dir = unity_project.parent / "images"
    current_dir = images_base_dir / "current"
    previous_dir = images_base_dir / "previous"
    registry_db_path = images_base_dir / "registry.db"

    # Verify paths
    if not current_dir.exists():
        console.print(f"[red]Error: Current images directory not found: {current_dir}[/red]")
        console.print("Run 'erenshor images process' first")
        raise typer.Exit(1)

    if not registry_db_path.exists():
        console.print(f"[red]Error: Image registry not found: {registry_db_path}[/red]")
        console.print("Run 'erenshor images process' first")
        raise typer.Exit(1)

    # Initialize services
    registry = ImageRegistry(registry_db_path)
    comparator = ImageComparator(registry, current_dir, previous_dir)

    console.print("[bold]Comparing images...[/bold]")
    console.print(f"  Similarity threshold: {similarity * 100:.0f}%")
    console.print()

    # Run comparison
    report = comparator.compare_all(similarity_threshold=similarity)

    # Display results
    console.print("[bold]Comparison Results:[/bold]")
    console.print(f"  Total images:    {report.total}")
    console.print(f"  [green]New:[/green]          {report.new}")
    console.print(f"  [yellow]Modified:[/yellow]     {report.modified}")
    console.print(f"  [dim]Unchanged:[/dim]    {report.unchanged}")
    console.print(f"  [red]Removed:[/red]      {report.removed}")

    if report.changed_count > 0:
        console.print()
        console.print(f"[green]✓ {report.changed_count} images changed[/green]")
        console.print("[dim]Run 'erenshor images report' for details[/dim]")
    else:
        console.print()
        console.print("[dim]No changes detected[/dim]")


@app.command("report")
def report(
    ctx: typer.Context,
    format: Annotated[str, typer.Option("--format", help="Output format (table or json)")] = "table",
    output: Annotated[Path | None, typer.Option("--output", help="Output file (default: stdout)")] = None,
) -> None:
    """Generate report of changed images.

    Examples:
        # Console table
        erenshor images report

        # JSON for scripting
        erenshor images report --format json

        # Save to file
        erenshor images report --format json --output changes.json
    """
    console = Console()
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]

    # Setup paths
    unity_project = variant_config.resolved_unity_project(cli_ctx.repo_root)
    images_base_dir = unity_project.parent / "images"
    registry_db_path = images_base_dir / "registry.db"

    # Verify registry exists
    if not registry_db_path.exists():
        console.print(f"[red]Error: Image registry not found: {registry_db_path}[/red]")
        console.print("Run 'erenshor images process' and 'erenshor images compare' first")
        raise typer.Exit(1)

    # Load changed images
    registry = ImageRegistry(registry_db_path)
    changed = registry.get_changed_images()

    if format == "table":
        # Rich table output
        table = Table(title="Changed Images")
        table.add_column("Entity", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Change", style="yellow")
        table.add_column("Similarity", style="dim")

        for img in changed:
            change_color = "green" if img.change_type == "new" else "yellow"
            table.add_row(
                img.entity_name,
                img.entity_type,
                f"[{change_color}]{img.change_type}[/{change_color}]",
                f"{img.similarity_score:.2%}" if img.similarity_score is not None else "N/A",
            )

        console.print(table)

    elif format == "json":
        # JSON output
        data = [img.to_dict() for img in changed]
        json_str = json.dumps(data, indent=2)

        if output:
            output.write_text(json_str)
            console.print(f"[green]✓[/green] Saved to {output}")
        else:
            console.print(json_str)
    else:
        console.print(f"[red]Error: Unknown format '{format}' (use 'table' or 'json')[/red]")
        raise typer.Exit(1)


@app.command("upload")
def upload(
    ctx: typer.Context,
    changed_only: Annotated[bool, typer.Option("--changed-only", help="Upload only changed images")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without uploading")] = False,
    force: Annotated[bool, typer.Option("--force", help="Re-upload existing images")] = False,
) -> None:
    """Upload processed images to MediaWiki.

    Uploads processed images to the wiki. Can upload all images or only
    those that changed (new or modified) based on registry tracking.

    Examples:
        # Upload all images
        erenshor images upload

        # Upload only changed images (recommended)
        erenshor images upload --changed-only

        # Dry-run to preview
        erenshor images upload --changed-only --dry-run
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
    images_base_dir = unity_project.parent / "images"
    current_dir = images_base_dir / "current"
    registry_db_path = images_base_dir / "registry.db"

    if not current_dir.exists():
        console.print(f"[red]Error: Current images directory not found: {current_dir}[/red]")
        console.print("Run 'erenshor images process' first")
        raise typer.Exit(1)

    if not registry_db_path.exists():
        console.print(f"[red]Error: Image registry not found: {registry_db_path}[/red]")
        console.print("Run 'erenshor images process' first")
        raise typer.Exit(1)

    # Initialize registry
    registry = ImageRegistry(registry_db_path)

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
    console.print(f"  Images: {current_dir}")
    console.print(f"  Wiki: {api_url}")
    if dry_run:
        console.print("[yellow]  Mode: DRY-RUN (no files will be uploaded)[/yellow]")
    if force:
        console.print("[yellow]  Force: Re-uploading all images[/yellow]")
    if changed_only:
        console.print("[yellow]  Uploading only changed images (new + modified)[/yellow]")
    console.print()

    # Get upload list
    if changed_only:
        # Get unique image_names that need deployment (deduplicated)
        deployment_dict = registry.get_deployment_list()
        console.print(f"[bold]Found {len(deployment_dict)} unique changed images to upload[/bold]")
    else:
        # Get all images from current directory
        console.print("[yellow]Warning: Uploading ALL images (use --changed-only for efficiency)[/yellow]")
        # Build list from filesystem for backward compatibility
        deployment_dict = {}
        all_image_files = sorted(current_dir.glob("*.png"))

        for image_file in all_image_files:
            # Extract stable_key from filename
            if "@" not in image_file.stem:
                continue

            stable_key = image_file.stem.replace("@", ":", 1)

            # Get metadata from registry
            metadata = registry.get_image_metadata(stable_key)
            if metadata:
                # Use image_name as key to deduplicate
                deployment_dict[metadata.image_name] = metadata

        console.print(f"[bold]Found {len(deployment_dict)} unique images to upload[/bold]")

    console.print()

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
        task = progress.add_task("[cyan]Uploading images...", total=len(deployment_dict))

        for image_name, metadata in deployment_dict.items():
            # Build paths
            filename = metadata.stable_key.replace(":", "@", 1).replace("/", "_").replace("\\", "_") + ".png"
            image_path = current_dir / filename
            wiki_filename = f"{image_name}.png"

            # Check if file exists
            if not image_path.exists():
                console.print(f"[red]Failed: {wiki_filename} - File not found: {image_path}[/red]")
                stats["failed"] += 1
                progress.advance(task)
                continue

            # Check if should upload
            should_upload, _reason = metadata.should_upload()

            if not force and not should_upload:
                stats["skipped"] += 1
                progress.advance(task)
                continue

            # Upload
            if dry_run:
                console.print(f"[dim]Would upload: {filename} → File:{wiki_filename}[/dim]")
                stats["uploaded"] += 1
            else:
                try:
                    client.upload_file(
                        file_path=str(image_path),
                        filename=wiki_filename,
                        comment="Automated icon upload",
                        text="",
                        ignore_warnings=True,
                        bot=True,
                    )

                    # Mark as uploaded in registry
                    if metadata.current_hash:
                        registry.mark_uploaded(
                            stable_key=metadata.stable_key,
                            uploaded_hash=metadata.current_hash,
                            wiki_filename=wiki_filename,
                        )

                    stats["uploaded"] += 1
                except MediaWikiAPIError as e:
                    error_msg = str(e)
                    # Check if this is a "no change" error
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
    console.print(f"  Total: {len(deployment_dict)}")

    if dry_run:
        console.print()
        console.print("[yellow]DRY-RUN: No files were uploaded[/yellow]")
    else:
        console.print()
        console.print("[green]✓ Upload complete[/green]")

    if stats["failed"] > 0:
        raise typer.Exit(1)
