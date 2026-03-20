"""Capture commands for map tile screenshotting pipeline.

This module provides commands for capturing map tiles from the game:
- Running the full capture pipeline (game + tiling)
- Re-tiling from existing master PNGs
- Interactive crop UI for adjusting zone bounds
- Showing capture status per zone/variant
- Estimating tile counts for budget planning
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from ..context import CLIContext

app = typer.Typer(
    name="capture",
    help="Map tile capture and tiling pipeline",
    no_args_is_help=True,
)

console = Console()


@app.command()
def run(
    ctx: typer.Context,
    zones: list[str] | None = typer.Option(
        None,
        "--zones",
        help="Zone names to capture (default: all)",
    ),
    variant: str | None = typer.Option(
        None,
        "--variant",
        help="Capture variant: 'clear' or 'open' (default: both per config)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-capture even if status is ok",
    ),
) -> None:
    """Run the full capture pipeline.

    Connects to the game via WebSocket, captures screenshots for each
    zone/variant, stitches master PNGs, and generates tile pyramids.
    Requires the MapTileCapture mod to be running in-game.
    """
    import asyncio

    from erenshor.application.capture.orchestrator import CaptureOrchestrator
    from erenshor.application.capture.state import CaptureState
    from erenshor.application.capture.zone_config import get_zone_keys, load_zone_config

    cli_ctx: CLIContext = ctx.obj
    config = load_zone_config(cli_ctx.repo_root)
    selected = get_zone_keys(config, zones)
    state = CaptureState.load(cli_ctx.repo_root)

    console.print()
    console.print("[bold cyan]Starting capture pipeline[/bold cyan]")
    console.print(f"  Zones: {len(selected)}")
    if variant:
        console.print(f"  Variant: {variant}")
    else:
        console.print("  Variant: both (per config)")
    if force:
        console.print("  [yellow]Force mode: re-capturing all[/yellow]")
    console.print()

    variants = [variant] if variant else None
    orch = CaptureOrchestrator(cli_ctx.repo_root, config, state)
    asyncio.run(orch.run(selected, variants=variants, force=force))

    console.print("[bold green]Capture pipeline complete[/bold green]")


@app.command()
def tile(
    ctx: typer.Context,
    zones: list[str] | None = typer.Option(
        None,
        "--zones",
        help="Zone names to re-tile (default: all)",
    ),
) -> None:
    """Re-tile from existing master PNGs.

    Regenerates tile pyramids without re-capturing from the game.
    Useful after adjusting crop bounds or tile settings.
    """
    from erenshor.application.capture.state import CaptureState
    from erenshor.application.capture.tile_generator import generate_tile_pyramid
    from erenshor.application.capture.zone_config import get_zone_keys, load_zone_config

    cli_ctx: CLIContext = ctx.obj
    config = load_zone_config(cli_ctx.repo_root)
    selected = get_zone_keys(config, zones)
    state = CaptureState.load(cli_ctx.repo_root)
    tiles_dir = cli_ctx.repo_root / "src" / "maps" / "static" / "tiles"

    console.print()
    console.print("[bold cyan]Re-tiling from master PNGs[/bold cyan]")
    console.print(f"  Zones: {len(selected)}")
    console.print()

    total_tiles = 0
    for zone_key in selected:
        zone_cfg = config[zone_key]
        for variant in zone_cfg.get("captureVariants", ["clear"]):
            variant_state = state.get_variant_state(zone_key, variant)
            if not variant_state or not variant_state.get("masterPath"):
                logger.warning(f"No captured master for {zone_key}/{variant}, skipping")
                continue
            master = cli_ctx.repo_root / variant_state["masterPath"]
            if not master.exists():
                console.print(f"[red]Error: master PNG missing: {master}[/red]")
                console.print("  State says it exists but file is gone. Re-capture with:")
                console.print(f"  uv run erenshor capture run --zones {zone_key} --variant {variant} --force")
                raise typer.Exit(1)

            count = generate_tile_pyramid(master, zone_key, variant, zone_cfg, tiles_dir)
            total_tiles += count
            console.print(f"  [green]{zone_key}/{variant}[/green]: {count} tiles")

    console.print()
    console.print(f"[bold]Total tiles generated: {total_tiles:,}[/bold]")


@app.command()
def crop(
    ctx: typer.Context,
    zone: str = typer.Option(
        ...,
        "--zone",
        help="Zone name to crop (required)",
    ),
) -> None:
    """Interactively adjust a zone's capture bounds by cropping the master PNG.

    Opens a browser UI where you drag to select the region of interest.
    The selection is converted from master-pixel coordinates to world-space
    bounds and written back to originX/Y and baseTilesX/Y in the zone config.
    Tiles are regenerated immediately.
    """
    import math

    from PIL import Image

    from erenshor.application.capture.cropper import serve_crop_ui
    from erenshor.application.capture.state import CaptureState
    from erenshor.application.capture.tile_generator import generate_tile_pyramid
    from erenshor.application.capture.zone_config import load_zone_config, save_zone_config

    cli_ctx: CLIContext = ctx.obj
    config = load_zone_config(cli_ctx.repo_root)

    if zone not in config:
        console.print(f"[red]Error: Unknown zone '{zone}'[/red]")
        console.print(f"Available zones: {', '.join(sorted(config.keys()))}")
        raise typer.Exit(1)

    state = CaptureState.load(cli_ctx.repo_root)
    variant_state = state.get_variant_state(zone, "clear")
    if not variant_state or not variant_state.get("masterPath"):
        console.print(f"[red]Error: No master PNG found for zone '{zone}'[/red]")
        console.print("\nCapture the zone first:")
        console.print(f"  uv run erenshor capture run --zones {zone}")
        raise typer.Exit(1)

    master_path = cli_ctx.repo_root / variant_state["masterPath"]
    if not master_path.exists():
        console.print(f"[red]Error: Master PNG not found: {master_path}[/red]")
        raise typer.Exit(1)

    console.print()
    console.print(f"[bold cyan]Opening crop UI for zone: {zone}[/bold cyan]")
    console.print()

    px = serve_crop_ui(master_path, zone, config[zone], cli_ctx.repo_root)
    if not px:
        console.print("[yellow]Crop cancelled[/yellow]")
        return

    # Convert pixel margins to world-space bounds.
    # Master pixel width = baseTilesX * 2^maxZoom * 256.
    # One master pixel = 1 / 2^maxZoom world units (tileSize is always 256).
    zc = config[zone]
    max_zoom: int = zc["maxZoom"]
    tile_size: int = zc.get("tileSize", 256)
    base_x: int = zc["baseTilesX"]
    base_y: int = zc["baseTilesY"]
    origin_x: float = zc["originX"]
    origin_y: float = zc["originY"]

    wpp = 1.0 / (2**max_zoom)  # world units per master pixel

    # image top = map north = high-Z edge; image bottom = south = originY side
    new_min_x = origin_x + px["left"] * wpp
    new_min_z = origin_y + px["bottom"] * wpp
    new_max_x = (origin_x + base_x * tile_size) - px["right"] * wpp
    new_max_z = (origin_y + base_y * tile_size) - px["top"] * wpp

    new_tiles_x = max(1, math.ceil((new_max_x - new_min_x) / tile_size))
    new_tiles_y = max(1, math.ceil((new_max_z - new_min_z) / tile_size))

    zc["originX"] = round(new_min_x, 4)
    zc["originY"] = round(new_min_z, 4)
    zc["baseTilesX"] = new_tiles_x
    zc["baseTilesY"] = new_tiles_y
    config[zone] = zc
    save_zone_config(cli_ctx.repo_root, config)

    console.print(f"[green]Bounds updated: origin=({zc['originX']}, {zc['originY']}) ", end="")
    console.print(f"tiles={new_tiles_x}x{new_tiles_y}[/green]")

    # Crop the master in-place to match the new bounds so the master
    # and config stay in sync. Tile generator scales the cropped master
    # to fill the tile grid, so content fills tiles correctly.
    with Image.open(master_path) as img:
        w, h = img.size
        box = (px["left"], px["top"], w - px["right"], h - px["bottom"])
        cropped = img.crop(box)
        cropped.save(master_path, "PNG")
    console.print(f"[dim]Master cropped to {cropped.width}x{cropped.height}[/dim]")

    console.print("[dim]Retiling...[/dim]")
    tile_out = cli_ctx.repo_root / "src" / "maps" / "static" / "tiles"
    count = generate_tile_pyramid(master_path, zone, "clear", zc, tile_out)
    console.print(f"[green]Tiled {zone}/clear: {count} tiles[/green]")


@app.command()
def status(
    ctx: typer.Context,
) -> None:
    """Show capture status per zone and variant.

    Reads the capture state file and displays a table showing
    which zones have been captured, their status, and variants.
    """
    from erenshor.application.capture.state import CaptureState
    from erenshor.application.capture.zone_config import load_zone_config

    cli_ctx: CLIContext = ctx.obj
    config = load_zone_config(cli_ctx.repo_root)
    state = CaptureState.load(cli_ctx.repo_root)

    table = Table(title="Capture Status")
    table.add_column("Zone", style="cyan")
    table.add_column("Clear", justify="center")
    table.add_column("Open", justify="center")

    for zone_key in sorted(config.keys()):
        clear_state = state.get_variant_state(zone_key, "clear")
        open_state = state.get_variant_state(zone_key, "open")

        clear_status = clear_state.get("status", "not captured") if clear_state else "not captured"
        open_status = open_state.get("status", "not captured") if open_state else "not captured"

        table.add_row(zone_key, _format_status(clear_status), _format_status(open_status))

    console.print()
    console.print(table)
    console.print()
    console.print(f"[dim]Total zones: {len(config)}[/dim]")


def _format_status(status: str) -> str:
    """Format a capture status string with Rich markup."""
    styles = {
        "ok": "[green]ok[/green]",
        "same_as_clear": "[green]same_as_clear[/green]",
        "error": "[red]error[/red]",
        "capturing": "[yellow]capturing[/yellow]",
        "not captured": "[dim]not captured[/dim]",
    }
    return styles.get(status, f"[yellow]{status}[/yellow]")


@app.command()
def budget(
    ctx: typer.Context,
) -> None:
    """Estimate tile count for all zones.

    Reads zone configuration and calculates the expected number
    of tiles per zone based on resolution and zoom settings.
    Useful for estimating storage and build time.
    """

    from erenshor.application.capture.budget import estimate_tile_count
    from erenshor.application.capture.zone_config import load_zone_config

    cli_ctx: CLIContext = ctx.obj
    config = load_zone_config(cli_ctx.repo_root)
    estimates = estimate_tile_count(config)

    table = Table(title="Tile Budget Estimate")
    table.add_column("Zone", style="cyan")
    table.add_column("Max Zoom", justify="right")
    table.add_column("Base Tiles", justify="right")
    table.add_column("Est. Tiles", justify="right")

    total_tiles = 0
    for zone_key in sorted(config.keys()):
        est = estimates.get(zone_key)
        if not est:
            continue
        zone_cfg = config[zone_key]
        tiles = est.get("tiles", 0)
        total_tiles += tiles
        table.add_row(
            zone_key,
            str(zone_cfg.get("maxZoom", "?")),
            f"{zone_cfg['baseTilesX']}x{zone_cfg['baseTilesY']}",
            str(tiles),
        )

    console.print()
    console.print(table)
    console.print()
    console.print(f"[bold]Total estimated tiles: {total_tiles:,}[/bold]")

    # Cloudflare limit warning
    if total_tiles > 18000:
        console.print("[yellow]Warning: approaching Cloudflare 20k file limit![/yellow]")
