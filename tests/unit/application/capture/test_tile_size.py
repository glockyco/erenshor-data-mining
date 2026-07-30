from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image

from erenshor.application.capture import orchestrator, zone_config
from erenshor.application.capture.budget import estimate_tile_count
from erenshor.application.capture.constants import TILE_SIZE
from erenshor.application.capture.tile_generator import generate_tile_pyramid
from erenshor.application.capture.zone_config import load_zone_config
from erenshor.cli.commands import capture as capture_command


def test_zone_config_reads_explicit_nondefault_path(tmp_path: Path) -> None:
    config_path = tmp_path / "configured" / "maps" / "zone-capture-config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({"zone": {"sceneName": "Scene"}}), encoding="utf-8")

    assert load_zone_config(config_path) == {"zone": {"sceneName": "Scene"}}


def test_capture_cli_uses_selected_variant_maps_source(tmp_path: Path, monkeypatch) -> None:
    maps_source_dir = tmp_path / "variant-maps"
    loaded_paths: list[Path] = []

    def load(path: Path) -> dict:
        loaded_paths.append(path)
        return {}

    monkeypatch.setattr(zone_config, "load_zone_config", load)
    monkeypatch.setattr("erenshor.application.capture.state.CaptureState.load", lambda _root: Mock())
    maps = SimpleNamespace(resolved_source_dir=lambda _repo_root: maps_source_dir)
    variant = SimpleNamespace(maps=maps)
    cli_ctx = SimpleNamespace(
        repo_root=tmp_path,
        variant="playtest",
        config=SimpleNamespace(variants={"playtest": variant}),
    )

    capture_command.status(SimpleNamespace(obj=cli_ctx))

    assert loaded_paths == [maps_source_dir / zone_config.CONFIG_RELATIVE_PATH]


def test_capture_uses_explicit_tile_output_dir(tmp_path: Path, monkeypatch) -> None:
    tile_output_dir = tmp_path / "configured" / "maps" / "static" / "tiles"
    config = {
        "zone": {
            "sceneName": "Scene",
            "captureVariants": ["open"],
            "baseTilesX": 1,
            "baseTilesY": 1,
            "maxZoom": 0,
        }
    }

    class State:
        def should_skip(self, zone: str, variant: str, master_path: Path, *, force: bool = False) -> bool:
            return False

        def set_variant_state(self, zone: str, variant: str, data: dict[str, object]) -> None:
            pass

        def save(self, repo_root: Path) -> None:
            pass

    async def fake_capture(zone: str, variant: str, zone_config: dict, master_path: Path) -> None:
        master_path.write_bytes(b"master")

    output_dirs: list[Path] = []
    monkeypatch.setattr(
        orchestrator,
        "generate_tile_pyramid",
        lambda master, zone, variant, cfg, output: output_dirs.append(output) or 1,
    )
    monkeypatch.setattr(orchestrator, "_sha256", lambda _path: "hash")

    capture = orchestrator.CaptureOrchestrator(tmp_path, config, State(), tile_output_dir=tile_output_dir)
    monkeypatch.setattr(capture, "_capture_zone", fake_capture)
    monkeypatch.setattr(capture, "connect", lambda: asyncio.sleep(0))
    monkeypatch.setattr(capture, "close", lambda: asyncio.sleep(0))

    asyncio.run(capture.run(["zone"], variants=None))

    assert output_dirs == [tile_output_dir]


def test_chunk_grid_uses_shared_tile_size_for_capture_pixels(tmp_path: Path) -> None:
    chunks = orchestrator.build_chunk_grid(
        {
            "baseTilesX": 2,
            "baseTilesY": 1,
            "maxZoom": 1,
            "tileSize": 64,
        },
        tmp_path,
    )

    assert chunks == [
        {
            "index": 0,
            "gridCols": 1,
            "centerX": 64.0,
            "centerZ": 32.0,
            "worldWidth": 128.0,
            "worldHeight": 64.0,
            "pixelWidth": 4 * TILE_SIZE,
            "pixelHeight": 2 * TILE_SIZE,
            "outputPath": "Z:" + str((tmp_path / "chunk_0.png").resolve()).replace("/", "\\"),
        }
    ]


def test_tile_budget_matches_non_power_of_two_pyramid() -> None:
    result = estimate_tile_count(
        {
            "zone": {
                "baseTilesX": 7,
                "baseTilesY": 10,
                "maxZoom": 0,
                "captureVariants": ["clear"],
            }
        }
    )

    # 7x10 at z0, then 4x5, 2x3, 1x2, and 1x1.
    assert result == {"zone": {"tiles": 99}, "_total": {"tiles": 99}}


def test_tile_pyramid_replaces_stale_zone_output(tmp_path: Path) -> None:
    master = tmp_path / "master.png"
    Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (10, 20, 30, 255)).save(master)
    output = tmp_path / "tiles"
    stale_tile = output / "test-zone" / "3" / "0" / "-1.webp"
    stale_tile.parent.mkdir(parents=True)
    stale_tile.write_bytes(b"stale")

    count = generate_tile_pyramid(
        master,
        "test-zone",
        "clear",
        {"baseTilesX": 1, "baseTilesY": 1, "maxZoom": 0},
        output,
    )

    tiles = list((output / "test-zone").glob("*/*/*.webp"))
    assert count == 1
    assert tiles == [output / "test-zone" / "0" / "0" / "-1.webp"]
    assert not stale_tile.exists()


def test_tile_pyramid_keeps_every_zoom_at_shared_tile_size(tmp_path: Path) -> None:
    master = tmp_path / "master.png"
    Image.new("RGBA", (2 * TILE_SIZE, TILE_SIZE), (10, 20, 30, 255)).save(master)
    output = tmp_path / "tiles"

    count = generate_tile_pyramid(
        master,
        "test-zone",
        "open",
        {"baseTilesX": 2, "baseTilesY": 1, "maxZoom": 0},
        output,
    )

    tiles = sorted((output / "test-zone").glob("*/*/*.webp"))
    assert count == 3
    assert len(tiles) == 3
    assert {Image.open(tile).size for tile in tiles} == {(TILE_SIZE, TILE_SIZE)}
