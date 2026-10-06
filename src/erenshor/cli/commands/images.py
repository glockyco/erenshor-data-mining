"""Image processing commands for game icons with lifecycle management."""

from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import closing
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
from erenshor.application.services.image_registry import ImageComparisonError, ImageRegistry, ImageRegistryError
from erenshor.application.services.model_image_manifest import (
    build_manifest,
    load_character_sources,
    load_game_build,
    page_image_uses,
    unused_page_image_uses,
)
from erenshor.application.wiki.lifecycle import load_content_lifecycle
from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.cli.mediawiki import create_readonly_mediawiki_client
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, database_valid
from erenshor.cli.preconditions.checks.inputs import required_path, wiki_credentials
from erenshor.domain.value_objects.wiki_filename import needs_redirect, sanitize_wiki_filename

if TYPE_CHECKING:
    from erenshor.cli.context import CLIContext
    from erenshor.domain.entities.image import ImageMetadata

__all__ = ["app"]

app = typer.Typer(help="Image processing operations")


@app.command("process")
@require_preconditions(
    database_exists,
    database_valid,
    required_path("unity_project", "ExportedProject/Assets/Texture2D", kind="directory"),
)
def process(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Reprocess all images")] = False,
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
        erenshor --dry-run images process
    """
    console = Console()
    cli_ctx: CLIContext = ctx.obj
    dry_run = cli_ctx.dry_run
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

    db_path = variant_config.resolved_database(cli_ctx.repo_root)

    # Initialize registry
    registry = ImageRegistry(registry_db_path)

    # Initialize processor
    processor = ImageProcessor(
        texture_dir=texture_dir,
        output_dir=current_dir,
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
                registry.update_entity_names(image_info.stable_key, image_info)
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

                    # Register in registry with previous_dir for hash calculation
                    registry.register_processed_image(
                        stable_key=image_info.stable_key,
                        image_info=image_info,
                        processing_result=result,
                        previous_dir=previous_dir if previous_dir.exists() else None,
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
@require_preconditions(
    required_path("images_dir", "current", kind="directory"),
    required_path("images_dir", "registry.db"),
)
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

    # Initialize services
    registry = ImageRegistry(registry_db_path)
    comparator = ImageComparator(registry, current_dir, previous_dir)

    console.print("[bold]Comparing images...[/bold]")
    console.print(f"  Similarity threshold: {similarity * 100:.0f}%")
    console.print()

    # Run comparison
    try:
        report = comparator.compare_all(similarity_threshold=similarity)
    except ImageComparisonError as error:
        console.print(f"[red]{error}[/red]")
        console.print("No change classification was written. Re-run 'erenshor images process' for these images.")
        raise typer.Exit(1) from error

    # Display results
    console.print("[bold]Comparison Results:[/bold]")
    console.print(f"  Total images:    {report.total}")
    console.print(f"  [green]New:[/green]          {report.new}")
    console.print(f"  [yellow]Modified:[/yellow]     {report.modified}")
    console.print(f"  [cyan]Renamed:[/cyan]      {report.renamed}")
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
@require_preconditions(required_path("images_dir", "registry.db"))
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


def _model_capture_dir(cli_ctx: CLIContext) -> Path:
    """The untracked directory of the model capture manifest and its captures."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    return variant_config.resolved_unity_project(cli_ctx.repo_root).parent / "images" / "model-captures"


@app.command("manifest")
@require_preconditions(database_exists, database_valid)
def manifest(ctx: typer.Context) -> None:
    """List the character images that the wiki lacks, with the game object to capture for each.

    Reads the character infoboxes of the generated pages and the unused pages of
    content-lifecycle.json, asks the wiki which files have no upload, and writes
    the manifest to images/model-captures/manifest.json of the variant. Reads the
    wiki only. With the root --dry-run option, writes nothing.

    Examples:
        erenshor wiki generate
        erenshor images manifest
    """
    console = Console()
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]

    lifecycle = load_content_lifecycle(cli_ctx.repo_root / "content-lifecycle.json")
    unused = {
        title: page.stable_key
        for title, page in lifecycle.pages.items()
        if page.state == "unused" and page.thing == "character" and page.stable_key is not None
    }
    pages = WikiStorage(variant_config.resolved_wiki(cli_ctx.repo_root)).read_generated_pages()
    if not pages:
        console.print("[red]No generated pages. Run 'erenshor wiki generate' first.[/red]")
        raise typer.Exit(1)
    database = variant_config.resolved_database(cli_ctx.repo_root)
    with closing(sqlite3.connect(f"file:{database}?mode=ro", uri=True)) as clean:
        characters = load_character_sources(clean)
        game_build = load_game_build(clean)
    uses = [*page_image_uses(pages), *unused_page_image_uses(unused, characters)]
    client = create_readonly_mediawiki_client(cli_ctx)
    try:
        result = build_manifest(uses, characters, client.get_uploaded_files, game_build)
    finally:
        client.close()

    table = Table(title=f"Missing character images, game build {result.game_build}")
    table.add_column("File", style="cyan")
    table.add_column("Kind", style="magenta")
    table.add_column("Stable key")
    table.add_column("Source")
    table.add_column("Pages", style="dim")
    for entry in result.entries:
        source = entry.source
        where = source.resources_path or f"{source.scene}: {source.object_name}"
        table.add_row(entry.file, entry.kind, entry.stable_key, where, ", ".join(entry.pages))
    console.print(table)
    for heading, files in (
        ("No game object found", result.unsourced),
        ("Editors' zone images, not captured", result.editor_files),
    ):
        if files:
            console.print(f"[bold]{heading}:[/bold]")
            for file in files:
                console.print(f"  {file.file} ({', '.join(file.pages)})")

    if cli_ctx.dry_run:
        console.print("[yellow]Dry run: the manifest was not written.[/yellow]")
        return
    output = _model_capture_dir(cli_ctx) / "manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    console.print(f"[green]✓[/green] {len(result.entries)} captures in {output}")


@app.command("capture")
@require_preconditions(required_path("images_dir", "model-captures/manifest.json"))
def capture(
    ctx: typer.Context,
    files: Annotated[
        list[str] | None,
        typer.Option("--file", help="Capture only this file title of the manifest; repeat for more"),
    ] = None,
) -> None:
    """Capture the manifest's missing character images in the running game for review.

    Needs the game running with the MapTileCapture mod. Sends each manifest
    entry to the mod, reviews each portrait, and writes the PNGs, captures.json,
    and contact-sheet.png to images/model-captures/staging/ of the variant,
    replacing the previous staging set. At the end the mod returns the player to
    where the batch started. With the root --dry-run option, lists the captures
    and writes nothing.

    Examples:
        erenshor --dry-run images capture
        erenshor images capture --file "Faith.png"
    """
    import asyncio

    import websockets

    from erenshor.application.capture.portraits import (
        WS_PORT,
        PortraitRun,
        capture_portraits,
        portrait_requests,
        write_contact_sheet,
    )

    console = Console()
    cli_ctx: CLIContext = ctx.obj
    capture_dir = _model_capture_dir(cli_ctx)
    manifest_data = json.loads((capture_dir / "manifest.json").read_text(encoding="utf-8"))
    try:
        requests = portrait_requests(manifest_data, files or ())
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error

    by_scene: dict[str, int] = {}
    for request in requests:
        by_scene[request.scene or "no scene (Resources)"] = by_scene.get(request.scene or "no scene (Resources)", 0) + 1
    console.print(
        f"[bold]{len(requests)} portraits[/bold], game build {manifest_data['game_build']}, "
        f"preset {manifest_data['camera_preset']}"
    )
    for scene, count in by_scene.items():
        console.print(f"  {scene}: {count}")
    if cli_ctx.dry_run:
        console.print("[yellow]Dry run: nothing was captured or written.[/yellow]")
        return

    staging = capture_dir / "staging"
    png_dir = staging / "png"
    if staging.exists():
        shutil.rmtree(staging)
    png_dir.mkdir(parents=True)
    results_path = staging / "captures.json"
    run = PortraitRun(game_build=manifest_data["game_build"], preset=manifest_data["camera_preset"])

    printed = 0

    def record(progress: PortraitRun) -> None:
        nonlocal printed
        results_path.write_text(json.dumps(progress.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for result in progress.results[printed:]:
            console.print(f"  {result.status:8} {result.file} {'; '.join(result.reasons + result.warnings)}".rstrip())
        printed = len(progress.results)

    async def run_batch() -> PortraitRun:
        try:
            connection = await websockets.connect(f"ws://localhost:{WS_PORT}", max_size=None)
        except OSError as error:
            raise ConnectionError(
                f"Cannot connect to the MapTileCapture mod on port {WS_PORT}. Is the game running with the mod?"
            ) from error
        async with connection:
            return await capture_portraits(connection, requests, png_dir, run, record)

    try:
        asyncio.run(run_batch())
    except ConnectionError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    write_contact_sheet(run, png_dir, staging / "contact-sheet.png")

    counts = {status: sum(result.status == status for result in run.results) for status in ("accepted", "rejected")}
    failed = len(run.results) - counts["accepted"] - counts["rejected"]
    console.print(
        f"{counts['accepted']} accepted, {counts['rejected']} rejected, {failed} failed. "
        f"Review {staging / 'contact-sheet.png'}"
    )
    if not run.returned:
        console.print("[yellow]The mod did not confirm that the player is back where the batch started.[/yellow]")
    if run.interrupted:
        console.print(f"[red]Interrupted at {run.interrupted}; {len(run.not_captured)} files not captured.[/red]")
        raise typer.Exit(1)


@app.command("approve")
@require_preconditions(
    required_path("images_dir", "model-captures/manifest.json"),
    required_path("images_dir", "model-captures/staging/captures.json"),
)
def approve_captures(
    ctx: typer.Context,
    files: Annotated[
        list[str] | None,
        typer.Option("--file", help="Approve this captured file title; repeat for more"),
    ] = None,
    every_accepted: Annotated[
        bool, typer.Option("--all", help="Approve every capture that the review accepted")
    ] = False,
    excluded: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="With --all, leave this file title out; repeat for more"),
    ] = None,
) -> None:
    """Approve reviewed captures for upload.

    Copies each approved PNG out of the staging set to images/model-captures/approved/
    and records its file title and SHA-256 in approved.json. Only captures that the
    review accepted can be approved. With the root --dry-run option, lists the
    approvals and writes nothing.

    Examples:
        erenshor images approve --all --exclude "Planar Flame Energy.png"
        erenshor images approve --file "Faith.png"
    """
    from erenshor.application.services.model_image_upload import APPROVAL_FILE, Approval, approve

    console = Console()
    cli_ctx: CLIContext = ctx.obj
    capture_dir = _model_capture_dir(cli_ctx)
    captures = json.loads((capture_dir / "staging" / "captures.json").read_text(encoding="utf-8"))
    manifest_data = json.loads((capture_dir / "manifest.json").read_text(encoding="utf-8"))
    if every_accepted == bool(files):
        console.print("[red]Name files with --file, or approve every accepted capture with --all.[/red]")
        raise typer.Exit(1)
    selected = list(files or ())
    if every_accepted:
        skipped = set(excluded or ())
        selected = [
            result["file"]
            for result in captures["results"]
            if result["status"] == "accepted" and result["file"] not in skipped
        ]
    console.print(f"[bold]{len(selected)} captures to approve[/bold]")
    for file in selected:
        console.print(f"  {file}")
    if cli_ctx.dry_run:
        console.print("[yellow]Dry run: nothing was approved.[/yellow]")
        return

    approval_path = capture_dir / APPROVAL_FILE
    previous = (
        Approval.from_json(json.loads(approval_path.read_text(encoding="utf-8"))) if approval_path.exists() else None
    )
    try:
        approval = approve(
            captures, manifest_data, capture_dir / "staging" / "png", capture_dir / "approved", selected, previous
        )
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    approval_path.write_text(json.dumps(approval.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    console.print(f"[green]✓[/green] {len(approval.images)} approved captures in {approval_path}")


@app.command("upload-captures")
@require_preconditions(required_path("images_dir", "model-captures/approved.json"), wiki_credentials)
def upload_captures(ctx: typer.Context) -> None:
    """Upload the approved captures whose files the wiki lacks.

    Reads the live wiki for each approved file title. A title with an image,
    directly or through a redirect, is skipped and its uploader named. A title
    whose image the wiki holds under another name, or that another file of the
    batch uploads, becomes a redirect. Every other capture is uploaded, under a
    name without a colon when its title has one, with a redirect from the title.
    Each write checks its title again first and never replaces an image. With the
    root --dry-run option, shows the plan and writes nothing.

    Examples:
        erenshor --dry-run images upload-captures
        erenshor images upload-captures
    """
    from datetime import UTC, datetime

    from erenshor.application.services.model_image_upload import (
        APPROVAL_FILE,
        Approval,
        execute_uploads,
        plan_uploads,
        write_record,
    )
    from erenshor.infrastructure.wiki.client import MediaWikiClient

    console = Console()
    cli_ctx: CLIContext = ctx.obj
    capture_dir = _model_capture_dir(cli_ctx)
    approval = Approval.from_json(json.loads((capture_dir / APPROVAL_FILE).read_text(encoding="utf-8")))
    approved_dir = capture_dir / "approved"

    reader = create_readonly_mediawiki_client(cli_ctx)
    try:
        plan = plan_uploads(approval, approved_dir, reader)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    finally:
        reader.close()

    table = Table(title=f"Capture uploads, game build {approval.game_build}, preset {approval.preset}")
    table.add_column("File", style="cyan")
    table.add_column("Action", style="magenta")
    table.add_column("Target")
    table.add_column("Reason", style="dim")
    for item in plan:
        table.add_row(item.file, item.action, item.target or "", item.reason)
    console.print(table)
    counts = {action: sum(item.action == action for item in plan) for action in ("upload", "redirect", "skip")}
    console.print(f"{counts['upload']} uploads, {counts['redirect']} redirects, {counts['skip']} skipped")
    if cli_ctx.dry_run:
        console.print("[yellow]Dry run: nothing was written.[/yellow]")
        return

    wiki_config = cli_ctx.config.global_.mediawiki
    writer = MediaWikiClient(
        api_url=wiki_config.api_url,
        bot_username=wiki_config.bot_username,
        bot_password=wiki_config.bot_password,
        batch_size=50,
    )
    try:
        writer.login()
        results = execute_uploads(plan, writer, approved_dir, approval, "Upload a reviewed capture of the game's model")
    finally:
        writer.close()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    record_path = capture_dir / "uploads" / f"{stamp}.json"
    write_record(record_path, approval, results)
    for result in results:
        console.print(f"  {result['action']:8} {result['file']} {result.get('reason', '')}")
    console.print(f"[green]✓[/green] Record: {record_path}")


def _deployment_list_for_stable_keys(registry: ImageRegistry, stable_keys: list[str]) -> dict[str, ImageMetadata]:
    deployment_dict: dict[str, ImageMetadata] = {}
    missing_stable_keys = []
    for stable_key in stable_keys:
        metadata = registry.get_image_metadata(stable_key)
        if metadata is None:
            missing_stable_keys.append(stable_key)
            continue
        deployment_dict[metadata.image_name] = metadata
    if missing_stable_keys:
        raise ValueError("Unknown image stable key(s): " + ", ".join(missing_stable_keys))
    return deployment_dict


@app.command("upload")
@require_preconditions(
    required_path("images_dir", "current", kind="directory"),
    required_path("images_dir", "registry.db"),
    wiki_credentials,
)
def upload(
    ctx: typer.Context,
    changed_only: Annotated[bool, typer.Option("--changed-only", help="Upload only changed images")] = False,
    force: Annotated[bool, typer.Option("--force", help="Re-upload existing images")] = False,
    stable_keys: Annotated[
        list[str] | None,
        typer.Option("--stable-key", help="Upload only this registry stable key; repeat for multiple images"),
    ] = None,
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
        erenshor --dry-run images upload --changed-only
    """
    from erenshor.infrastructure.wiki.client import MediaWikiAPIError, MediaWikiClient, MediaWikiEditConflictError

    console = Console()
    cli_ctx: CLIContext = ctx.obj
    dry_run = cli_ctx.dry_run
    variant_config = cli_ctx.config.variants[cli_ctx.variant]

    # Check bot credentials
    wiki_config = cli_ctx.config.global_.mediawiki
    bot_username = wiki_config.bot_username
    bot_password = wiki_config.bot_password
    api_url = wiki_config.api_url

    # Setup paths
    unity_project = variant_config.resolved_unity_project(cli_ctx.repo_root)
    images_base_dir = unity_project.parent / "images"
    current_dir = images_base_dir / "current"
    registry_db_path = images_base_dir / "registry.db"

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
    if stable_keys:
        try:
            deployment_dict = _deployment_list_for_stable_keys(registry, stable_keys)
        except ValueError as error:
            console.print(f"[red]{error}[/red]")
            raise typer.Exit(1) from error
        console.print(f"[bold]Found {len(deployment_dict)} explicitly selected images to upload[/bold]")
    elif changed_only:
        # Get unique image_names that need deployment (deduplicated)
        try:
            deployment_dict = registry.get_deployment_list()
        except ImageRegistryError as error:
            console.print(f"[red]{error}[/red]")
            raise typer.Exit(1) from error
        console.print(f"[bold]Found {len(deployment_dict)} unique changed images to upload[/bold]")
    else:
        console.print("[yellow]Warning: Uploading ALL images (use --changed-only for efficiency)[/yellow]")
        deployment_dict = {}
        unregistered: list[str] = []
        for image_file in sorted(current_dir.glob("*.png")):
            # Processed files are named <entity_type>@<resource_name>.png.
            metadata = (
                registry.get_image_metadata(image_file.stem.replace("@", ":", 1)) if "@" in image_file.stem else None
            )
            if metadata is None:
                unregistered.append(image_file.name)
                continue
            # Use image_name as key to deduplicate
            deployment_dict[metadata.image_name] = metadata

        if unregistered:
            console.print(
                f"[red]{len(unregistered)} files in {current_dir} have no registry entry: "
                f"{', '.join(unregistered[:10])}{' ...' if len(unregistered) > 10 else ''}[/red]"
            )
            console.print("Run 'erenshor images process' so the registry matches the processed files.")
            raise typer.Exit(1)

        console.print(f"[bold]Found {len(deployment_dict)} unique images to upload[/bold]")

    console.print()

    # Upload images with progress bar
    stats = {"uploaded": 0, "skipped": 0, "failed": 0}
    redirects_to_create: list[tuple[str, str]] = []  # (original_name, sanitized_name)

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

            # Sanitize filename for MediaWiki (removes : | # < > [ ] { })
            sanitized_image_name = sanitize_wiki_filename(image_name)
            wiki_filename = f"{sanitized_image_name}.png"

            # Track redirect if sanitization changed the name
            if needs_redirect(image_name, sanitized_image_name):
                redirects_to_create.append((image_name, sanitized_image_name))

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
                if needs_redirect(image_name, sanitized_image_name):
                    console.print(
                        f"[dim]Would upload: {filename} → File:{wiki_filename} "
                        f"[yellow](redirect from {image_name})[/yellow][/dim]"
                    )
                else:
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

                    # Mark as uploaded in registry (store sanitized filename)
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

                    # Remove from redirect list if upload failed
                    if needs_redirect(image_name, sanitized_image_name):
                        redirects_to_create = [(orig, san) for orig, san in redirects_to_create if orig != image_name]

            progress.advance(task)

    # Create redirect pages for sanitized filenames
    redirect_stats = {"created": 0, "existing": 0, "failed": 0}
    redirect_errors: list[tuple[str, str]] = []  # (original_name, error_message)

    if redirects_to_create:
        if dry_run:
            console.print()
            console.print(f"[bold cyan]Would create {len(redirects_to_create)} redirect pages:[/bold cyan]")
            for original, sanitized in redirects_to_create[:10]:
                console.print(f"  [yellow]File:{original}.png[/yellow] → [green]File:{sanitized}.png[/green]")
            if len(redirects_to_create) > 10:
                console.print(f"  [dim]... and {len(redirects_to_create) - 10} more[/dim]")
        else:
            console.print()
            console.print(f"[bold cyan]Creating {len(redirects_to_create)} redirect pages...[/bold cyan]")

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
                    redirect_title = f"File:{original}.png"
                    redirect_target = f"File:{sanitized}.png"
                    redirect_content = f"#REDIRECT [[{redirect_target}]]"

                    try:
                        client.safe_create_page(
                            title=redirect_title,
                            content=redirect_content,
                            start_timestamp=client.get_edit_start_timestamp(assertion="bot"),
                            summary="Automated redirect for sanitized filename",
                            minor=True,
                            bot=True,
                            assertion="bot",
                        )
                        redirect_stats["created"] += 1
                    except MediaWikiEditConflictError:
                        # The page exists: an earlier run created it, or it holds other text.
                        redirect_stats["existing"] += 1
                    except MediaWikiAPIError as e:
                        redirect_stats["failed"] += 1
                        error_msg = str(e)
                        redirect_errors.append((original, error_msg))
                        # Continue with other redirects even if one fails

                    progress.advance(task)

            # Print redirect summary
            console.print()
            console.print(f"[green]✓ Redirects created: {redirect_stats['created']}[/green]")
            if redirect_stats["existing"] > 0:
                console.print(f"[dim]Redirect pages already present: {redirect_stats['existing']}[/dim]")
            if redirect_stats["failed"] > 0:
                console.print(f"[red]✗ Redirects failed: {redirect_stats['failed']}[/red]")
                console.print()
                console.print("[bold red]Redirect Errors:[/bold red]")
                for original, error_message in redirect_errors[:10]:  # Show first 10
                    console.print(f"  [red]File:{original}.png[/red]: {error_message}")
                if len(redirect_errors) > 10:
                    console.print(f"  [dim]... and {len(redirect_errors) - 10} more errors[/dim]")

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

    if stats["failed"] > 0 or redirect_stats.get("failed", 0) > 0:
        console.print()
        console.print("[red]Upload incomplete: some images or redirects failed, see above.[/red]")
        raise typer.Exit(1)

    if not dry_run:
        console.print()
        console.print("[green]✓ Upload complete[/green]")
