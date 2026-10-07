"""Wiki picture commands: character portrait captures and the publication of the picture catalog."""

from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console
from rich.table import Table

from erenshor.application.services.model_image_manifest import (
    build_manifest,
    load_character_sources,
    load_game_build,
)
from erenshor.application.wiki.lifecycle import load_content_lifecycle
from erenshor.cli.mediawiki import create_readonly_mediawiki_client
from erenshor.cli.preconditions import require_preconditions
from erenshor.cli.preconditions.checks.database import database_exists, database_valid
from erenshor.cli.preconditions.checks.inputs import required_path, wiki_credentials

if TYPE_CHECKING:
    from collections.abc import Iterator

    from erenshor.application.services.image_publication_run import RunRecord
    from erenshor.cli.context import CLIContext
    from erenshor.infrastructure.wiki.client import MediaWikiClient

__all__ = ["app"]

app = typer.Typer(help="Capture character portraits and publish the game's pictures to the wiki")


def _model_capture_dir(cli_ctx: CLIContext) -> Path:
    """The untracked directory of the model capture manifest and its captures."""
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    return variant_config.resolved_unity_project(cli_ctx.repo_root).parent / "images" / "model-captures"


@app.command("manifest")
@require_preconditions(database_exists, database_valid)
def manifest(ctx: typer.Context) -> None:
    """List every character model with the game object to capture for it.

    Characters that share a model share an image title and one capture. Lists
    each title of the clean database once, whether or not the wiki has a
    picture for it, with the pages of its characters, including the unused
    pages of content-lifecycle.json, and writes the manifest to
    images/model-captures/manifest.json of the variant. With the root
    --dry-run option, writes nothing.

    Examples:
        erenshor --dry-run images manifest
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
    database = variant_config.resolved_database(cli_ctx.repo_root)
    with closing(sqlite3.connect(f"file:{database}?mode=ro", uri=True)) as clean:
        characters = load_character_sources(clean)
        game_build = load_game_build(clean)
    try:
        result = build_manifest(characters, unused, game_build)
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error

    prefabs = sum(1 for entry in result.entries if entry.source.resources_path)
    scenes = {entry.source.scene for entry in result.entries if entry.source.scene}
    console.print(
        f"[bold]{len(result.entries)} models[/bold] of {len(characters)} characters, game build "
        f"{result.game_build}: {prefabs} prefabs, {len(result.entries) - prefabs} in {len(scenes)} scenes"
    )
    if result.unsourced:
        console.print(f"[bold]{len(result.unsourced)} models without a game object to capture:[/bold]")
        for model in result.unsourced:
            console.print(f"  {model.subject} ({', '.join(model.pages) or 'no page'})")

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
    subjects: Annotated[
        list[str] | None,
        typer.Option("--subject", help="Capture only this subject of the manifest; repeat for more"),
    ] = None,
) -> None:
    """Capture the manifest's character models in the running game for review.

    Needs the game running with the MapTileCapture mod. Sends each manifest
    entry to the mod, reviews each portrait, and writes the PNGs and
    captures.json to images/model-captures/staging/ of the variant, replacing
    the previous staging set. With --subject, recaptures only those subjects and
    keeps the rest of the staging set. At the end the mod returns the player to
    where the batch started. Draw the contact sheets with 'erenshor images
    review'. With the root --dry-run option, lists the captures and writes
    nothing.

    Examples:
        erenshor --dry-run images capture
        erenshor images capture --subject "Faith"
    """
    import asyncio

    import websockets

    from erenshor.application.capture.portraits import (
        WS_PORT,
        PortraitRun,
        capture_portraits,
        portrait_requests,
        recapture_run,
    )

    console = Console()
    cli_ctx: CLIContext = ctx.obj
    capture_dir = _model_capture_dir(cli_ctx)
    manifest_data = json.loads((capture_dir / "manifest.json").read_text(encoding="utf-8"))
    try:
        requests = portrait_requests(manifest_data, subjects or ())
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
    results_path = staging / "captures.json"
    game_build, preset = manifest_data["game_build"], manifest_data["camera_preset"]
    staged = json.loads(results_path.read_text(encoding="utf-8")) if subjects and results_path.exists() else None
    if staged is not None:
        if (staged["game_build"], staged["preset"]) != (game_build, preset):
            console.print("[red]The staging set is of another build or preset; capture every file again.[/red]")
            raise typer.Exit(1)
        run = recapture_run(staged, png_dir, set(subjects or ()))
    else:
        if staging.exists():
            shutil.rmtree(staging)
        png_dir.mkdir(parents=True)
        run = PortraitRun(game_build=game_build, preset=preset)

    printed = len(run.results)

    def record(progress: PortraitRun) -> None:
        nonlocal printed
        results_path.write_text(json.dumps(progress.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for result in progress.results[printed:]:
            console.print(
                f"  {result.status:8} {result.subject} {'; '.join(result.reasons + result.warnings)}".rstrip()
            )
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

    counts = {status: sum(result.status == status for result in run.results) for status in ("accepted", "rejected")}
    failed = len(run.results) - counts["accepted"] - counts["rejected"]
    console.print(
        f"{counts['accepted']} accepted, {counts['rejected']} rejected, {failed} failed. "
        "Draw the contact sheets with 'erenshor images review'."
    )
    if not run.returned:
        console.print("[yellow]The mod did not confirm that the player is back where the batch started.[/yellow]")
    if run.interrupted:
        console.print(f"[red]Interrupted at {run.interrupted}; {len(run.not_captured)} subjects not captured.[/red]")
        raise typer.Exit(1)


@app.command("review")
@require_preconditions(required_path("images_dir", "model-captures/staging/captures.json"))
def review(ctx: typer.Context) -> None:
    """Draw the staged captures beside the pictures that their titles show on the wiki now.

    Reads the wiki's file listing and downloads each shown picture once into
    the cache of live pictures of images/publish/live/, which publishing shares.
    Writes the contact sheets to images/model-captures/staging/contact-sheets/
    of the variant, failed and rejected captures first, and counts who uploaded
    the pictures that the renders would join or replace. Reads the wiki only.

    Examples:
        erenshor images review
    """
    from collections import Counter

    from erenshor.application.capture.portraits import PortraitRun, WikiPicture, write_contact_sheets
    from erenshor.application.services.image_publication import LivePictureCache, LiveWiki
    from erenshor.domain.value_objects.wiki_filename import picture_file_title

    console = Console()
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    staging = _model_capture_dir(cli_ctx) / "staging"
    run = PortraitRun.from_json(json.loads((staging / "captures.json").read_text(encoding="utf-8")))
    _, owners = _project_accounts(cli_ctx)

    with closing(create_readonly_mediawiki_client(cli_ctx)) as reader:
        file_pages = reader.list_file_pages()
        live = LiveWiki({file.title: file for file in reader.list_files()}, file_pages.redirects, file_pages.pages)
        pictures = LivePictureCache(
            reader.download, variant_config.resolved_images_output(cli_ctx.repo_root) / "publish" / "live"
        )
        shown = {
            picture_file_title("render", result.subject): file
            for result in run.results
            if (file := live.shown(f"File:{picture_file_title('render', result.subject)}")) is not None
        }
        for file in shown.values():
            pictures.content(file)
        console.print(f"{len(shown)} titles show a picture on the wiki; {pictures.downloads} downloaded")

    def wiki(title: str) -> WikiPicture | None:
        file = shown.get(title)
        return WikiPicture(file.user, pictures.content(file)) if file is not None else None

    sheets_dir = staging / "contact-sheets"
    if sheets_dir.exists():
        shutil.rmtree(sheets_dir)
    sheets = write_contact_sheets(run, staging / "png", wiki, sheets_dir)

    uploaders = Counter(file.user or "uploader hidden" for file in shown.values())
    project = sum(count for user, count in uploaders.items() if user in owners)
    editors = ", ".join(f"{user} {count}" for user, count in uploaders.most_common() if user not in owners)
    console.print(
        f"Wiki pictures: {len(run.results) - len(shown)} titles have none, {project} are the project's, "
        f"{len(shown) - project} are editors' ({editors or 'none'})"
    )
    console.print(f"[green]✓[/green] {len(sheets)} contact sheets in {sheets_dir}")


@app.command("approve")
@require_preconditions(
    required_path("images_dir", "model-captures/manifest.json"),
    required_path("images_dir", "model-captures/staging/captures.json"),
)
def approve_captures(
    ctx: typer.Context,
    subjects: Annotated[
        list[str] | None,
        typer.Argument(help="Captured subjects to approve"),
    ] = None,
    every_accepted: Annotated[
        bool, typer.Option("--all", help="Approve every capture that the review accepted")
    ] = False,
    excluded: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="With --all, leave this subject out; repeat for more"),
    ] = None,
) -> None:
    """Approve reviewed captures for upload.

    Copies each approved PNG out of the staging set to images/model-captures/approved/
    and records its subject and SHA-256 in approved.json. Only captures that the
    review accepted can be approved. With the root --dry-run option, lists the
    approvals and writes nothing.

    Examples:
        erenshor images approve --all --exclude "Planar Flame Energy"
        erenshor images approve "Faith"
    """
    from erenshor.application.services.model_image_approval import approve
    from erenshor.domain.value_objects.capture_approval import APPROVAL_FILE, Approval

    console = Console()
    cli_ctx: CLIContext = ctx.obj
    capture_dir = _model_capture_dir(cli_ctx)
    captures = json.loads((capture_dir / "staging" / "captures.json").read_text(encoding="utf-8"))
    manifest_data = json.loads((capture_dir / "manifest.json").read_text(encoding="utf-8"))
    if every_accepted == bool(subjects):
        console.print("[red]Name subjects as arguments, or approve every accepted capture with --all.[/red]")
        raise typer.Exit(1)
    selected = list(subjects or ())
    if every_accepted:
        skipped = set(excluded or ())
        selected = [
            result["subject"]
            for result in captures["results"]
            if result["status"] == "accepted" and result["subject"] not in skipped
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


def _project_accounts(cli_ctx: CLIContext) -> tuple[str, tuple[str, ...]]:
    """The bot account, and every account whose uploads are the project's: the bot and the operator's.

    The operator's account is the user of the interface and administrator bot passwords.
    """
    wiki_config = cli_ctx.config.global_.mediawiki
    bot = wiki_config.bot_username.partition("@")[0]
    usernames = (wiki_config.bot_username, wiki_config.interface_username, wiki_config.administrator_username)
    return bot, tuple(dict.fromkeys(name.partition("@")[0] for name in usernames if name))


@app.command("publish")
@require_preconditions(database_exists, database_valid, wiki_credentials)
def publish(
    ctx: typer.Context,
    revert_stamp: Annotated[
        str | None,
        typer.Option("--revert", help="Undo the publish run with this stamp"),
    ] = None,
) -> None:
    """Publish the picture catalog to the wiki, one file per picture.

    Lists the wiki's files once and gives every file title that a page names a
    verdict: create, update, unchanged, move, redirect, retire, describe, or
    conflict. Every other title of a picture redirects to its file, and a copy
    that the project uploaded is deleted. A file of the project that holds a
    picture at an old title moves to the picture's title with its history,
    and the redirects that named the old title follow it. A file whose latest
    version someone else uploaded is a conflict and stays. The bot's files that
    nothing produces and no page shows are orphans and are deleted too. Writes
    the plan and contact sheets of every changing picture to
    images/publish/<stamp>/. With the root --dry-run option, stops there.
    Otherwise uploads and edits with the bot account, moves and deletes with
    the administrator account, checks each title again first, and records every
    write in run.json.

    Examples:
        erenshor --dry-run images publish
        erenshor images publish
        erenshor images publish --revert 20261006T200000Z
    """
    from datetime import UTC, datetime

    from erenshor.application.services.image_publication import (
        LivePictureCache,
        LiveWiki,
        load_catalog,
        plan_publication,
        write_contact_sheets,
    )
    from erenshor.application.services.image_publication_run import RunRecord, execute, revert

    console = Console()
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    publish_dir = variant_config.resolved_images_output(cli_ctx.repo_root) / "publish"
    run_dir = publish_dir / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    bot, owners = _project_accounts(cli_ctx)

    if revert_stamp is not None:
        reverted = RunRecord.load(publish_dir / revert_stamp)
        done = [entry for entry in reverted.entries if entry.get("done")]
        if not done:
            console.print(f"[red]The run {revert_stamp} recorded no write.[/red]")
            raise typer.Exit(1)
        console.print(f"{len(done)} writes of run {revert_stamp} to undo")
        if cli_ctx.dry_run:
            console.print("[yellow]Dry run: nothing was written.[/yellow]")
            return
        record = RunRecord(run_dir)
        needed = any(entry["action"] in ("move", "retire", "orphan") for entry in done)
        with (
            closing(_bot_client(cli_ctx)) as writer,
            _administrator_client(cli_ctx, console, needed=needed) as administrator,
        ):
            writer.login()
            revert(reverted, writer, administrator, record, owners, f"Revert the picture publication of {revert_stamp}")
        _print_record(console, record)
        return

    catalog = load_catalog(variant_config.resolved_database(cli_ctx.repo_root), publish_dir.parent)
    with closing(create_readonly_mediawiki_client(cli_ctx)) as reader:
        files = reader.list_files()
        file_pages = reader.list_file_pages()
        live = LiveWiki({file.title: file for file in files}, file_pages.redirects, file_pages.pages)
        pictures = LivePictureCache(reader.download, publish_dir / "live")
        plan = plan_publication(catalog, live, bot, owners, pictures, reader.is_file_used)
        sheets = write_contact_sheets(plan, catalog, live, pictures, run_dir)
        pictures.save()
    (run_dir / "plan.json").write_text(json.dumps(plan.to_json(), indent=2, ensure_ascii=False) + "\n")

    counts = plan.counts()
    console.print(", ".join(f"{count} {verdict}" for verdict, count in counts.items()))
    moves = [item for item in plan.titles if item.verdict == "move"]
    if moves:
        table = Table(title="Moves: each file keeps its history, and its old title redirects to it")
        table.add_column("Old title", style="dim")
        table.add_column("New title", style="cyan")
        for item in moves:
            table.add_row(str(item.source), item.title)
        console.print(table)
    conflicts = [item for item in plan.titles if item.verdict == "conflict"]
    if conflicts:
        table = Table(title="Conflicts: the bot leaves these titles alone")
        table.add_column("Title", style="cyan")
        table.add_column("Reason", style="dim")
        for item in conflicts:
            table.add_row(item.title, item.reason)
        console.print(table)
    if plan.orphans:
        table = Table(title=f"Orphans of {bot}: the run deletes them with the redirects that name them")
        table.add_column("File", style="cyan")
        table.add_column("Uploaded", style="dim")
        table.add_column("Redirects", style="dim")
        for orphan in plan.orphans:
            table.add_row(orphan.title, orphan.timestamp[:10], ", ".join(orphan.redirects))
        console.print(table)
    if plan.unused:
        console.print(f"{len(plan.unused)} files of the operator that nothing produces or shows stay: see plan.json")
    console.print(f"Plan: {run_dir / 'plan.json'}")
    console.print(f"Contact sheets: {len(sheets)} under {run_dir}")
    if cli_ctx.dry_run:
        console.print("[yellow]Dry run: nothing was written.[/yellow]")
        return

    record = RunRecord(run_dir)
    with (
        closing(_bot_client(cli_ctx)) as writer,
        _administrator_client(cli_ctx, console, needed=plan.needs_administrator) as administrator,
    ):
        writer.login()
        execute(plan, catalog, writer, administrator, record, "Publish the game's pictures")
    _print_record(console, record)


@app.command("move-screenshots")
@require_preconditions(database_exists, database_valid, wiki_credentials)
def move_screenshots(ctx: typer.Context) -> None:
    """Move editors' character pictures from plain titles to their screenshot titles, once.

    An editor's file at a character's plain title, <name>.png, or at that
    title without a colon, moves to <subject> screenshot.png with its history.
    Its old title and every redirect that named it point at the new title.
    Files of the project stay for publish to move. Writes the plan to
    images/publish/<stamp>/. With the root --dry-run option, stops there.
    Otherwise moves with the administrator account, points redirects with the
    bot account, and records every write in run.json,
    so `images publish --revert <stamp>` undoes the run.

    Examples:
        erenshor --dry-run images move-screenshots
        erenshor images move-screenshots
    """
    from dataclasses import asdict
    from datetime import UTC, datetime

    from erenshor.application.services.image_publication import LiveWiki
    from erenshor.application.services.image_publication_run import RunRecord
    from erenshor.application.services.screenshot_move import execute_screenshot_moves, plan_screenshot_moves

    console = Console()
    cli_ctx: CLIContext = ctx.obj
    variant_config = cli_ctx.config.variants[cli_ctx.variant]
    run_dir = (
        variant_config.resolved_images_output(cli_ctx.repo_root)
        / "publish"
        / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    _, owners = _project_accounts(cli_ctx)
    database = variant_config.resolved_database(cli_ctx.repo_root)
    with closing(sqlite3.connect(f"file:{database}?mode=ro", uri=True)) as conn:
        characters = conn.execute("SELECT image_name, display_name FROM characters").fetchall()
    with closing(create_readonly_mediawiki_client(cli_ctx)) as reader:
        file_pages = reader.list_file_pages()
        live = LiveWiki({file.title: file for file in reader.list_files()}, file_pages.redirects, file_pages.pages)
    plan = plan_screenshot_moves(characters, live, owners)
    run_dir.mkdir(parents=True, exist_ok=True)
    plan_json = {"moves": [asdict(item) for item in plan.moves], "skipped": [list(item) for item in plan.skipped]}
    (run_dir / "plan.json").write_text(json.dumps(plan_json, indent=2, ensure_ascii=False) + "\n")

    table = Table(title=f"{len(plan.moves)} moves: each file keeps its history, and its old title redirects to it")
    table.add_column("Old title", style="dim")
    table.add_column("Screenshot title", style="cyan")
    table.add_column("Uploaded by", style="dim")
    table.add_column("Redirects that follow", style="dim")
    for item in plan.moves:
        table.add_row(item.source, item.title, item.uploader, ", ".join(item.redirects))
    console.print(table)
    for title, reason in plan.skipped:
        console.print(f"[yellow]Stays[/yellow] {title}: {reason}")
    console.print(f"Plan: {run_dir / 'plan.json'}")
    if cli_ctx.dry_run:
        console.print("[yellow]Dry run: nothing was written.[/yellow]")
        return

    record = RunRecord(run_dir)
    with (
        closing(_bot_client(cli_ctx)) as writer,
        _administrator_client(cli_ctx, console, needed=bool(plan.moves)) as administrator,
    ):
        writer.login()
        execute_screenshot_moves(
            plan, writer, administrator, record, "Give an editor's character picture its screenshot title"
        )
    _print_record(console, record)


def _bot_client(cli_ctx: CLIContext) -> MediaWikiClient:
    from erenshor.infrastructure.wiki.client import MediaWikiClient

    wiki_config = cli_ctx.config.global_.mediawiki
    return MediaWikiClient(
        api_url=wiki_config.api_url,
        bot_username=wiki_config.bot_username,
        bot_password=wiki_config.bot_password,
        batch_size=50,
    )


@contextmanager
def _administrator_client(cli_ctx: CLIContext, console: Console, *, needed: bool) -> Iterator[MediaWikiClient | None]:
    """A logged-in client of the administrator account when the work moves or deletes, after checking its rights.

    Exits before any write when the account is not configured or lacks a right
    that moving, deleting, or undoing them needs.
    """
    from erenshor.infrastructure.wiki.client import MediaWikiClient

    if not needed:
        yield None
        return
    wiki_config = cli_ctx.config.global_.mediawiki
    if not wiki_config.administrator_username.strip() or not wiki_config.administrator_password:
        console.print(
            "[red]This run moves or deletes files, which needs an administrator's bot password with the delete and "
            "file-move grants. Set [global.mediawiki].administrator_username and administrator_password in "
            ".erenshor/config.local.toml.[/red]"
        )
        raise typer.Exit(1)
    client = MediaWikiClient(
        api_url=wiki_config.api_url,
        bot_username=wiki_config.administrator_username,
        bot_password=wiki_config.administrator_password,
        batch_size=50,
    )
    try:
        client.login()
        missing = {"delete", "undelete", "movefile", "suppressredirect"} - client.get_current_user_rights(
            assertion="user"
        )
        if missing:
            console.print(f"[red]The administrator account lacks the right {', '.join(sorted(missing))}.[/red]")
            raise typer.Exit(1)
        yield client
    finally:
        client.close()


def _print_record(console: Console, record: RunRecord) -> None:
    from collections import Counter

    done = Counter(str(entry["action"]) for entry in record.entries if entry.get("done"))
    console.print("Written: " + (", ".join(f"{count} {action}" for action, count in sorted(done.items())) or "nothing"))
    for entry in record.entries:
        if not entry.get("done"):
            console.print(f"  [yellow]skipped[/yellow] {entry['action']} {entry['title']}: {entry.get('reason', '')}")
    console.print(f"[green]✓[/green] Record: {record.directory / 'run.json'}")
