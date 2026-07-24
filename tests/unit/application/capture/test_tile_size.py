from pathlib import Path

from PIL import Image

from erenshor.application.capture import orchestrator
from erenshor.application.capture.constants import TILE_SIZE
from erenshor.application.capture.tile_generator import generate_tile_pyramid


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
