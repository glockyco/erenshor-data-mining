from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from loguru import logger
from PIL import Image


def stitch_chunks(
    chunk_paths: list[Path],
    chunk_specs: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Stitch captured chunks into a single master image.

    Each entry in *chunk_specs* must contain ``pixelWidth``, ``pixelHeight``,
    ``index``, and grid position derived from the chunk list order.

    For a single chunk the file is simply moved to *output_path* (no decode
    needed).
    """
    if len(chunk_paths) == 1:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(chunk_paths[0]), str(output_path))
        logger.debug(f"Single chunk — moved to {output_path}")
        return

    # Determine master canvas size from chunk specs.
    # Chunks are laid out on a grid: index 0 is top-left, row-major.
    total_w = sum(s["pixelWidth"] for s in chunk_specs if s["index"] < _cols(chunk_specs))
    total_h = sum(
        s["pixelHeight"]
        for i, s in enumerate(chunk_specs)
        if i % _cols(chunk_specs) == 0
    )

    master = Image.new("RGBA", (total_w, total_h))
    cols = _cols(chunk_specs)

    for spec, path in zip(chunk_specs, chunk_paths, strict=True):
        idx = spec["index"]
        col = idx % cols
        row = idx // cols

        x_offset = sum(chunk_specs[r * cols + c]["pixelWidth"] for c in range(col) for r in [row])
        y_offset = sum(chunk_specs[r * cols]["pixelHeight"] for r in range(row))

        chunk_img = Image.open(path)
        master.paste(chunk_img, (x_offset, y_offset))
        chunk_img.close()
        logger.debug(f"Pasted chunk {idx} at ({x_offset}, {y_offset})")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    master.save(output_path, "PNG")
    logger.info(f"Stitched {len(chunk_paths)} chunks -> {output_path}")


def _cols(specs: list[dict[str, Any]]) -> int:
    """Infer column count from specs (contiguous indices in first row)."""
    # Chunks are row-major. The first row ends when pixelWidth pattern
    # restarts — but the simplest heuristic: look for the highest index whose
    # cumulative width doesn't exceed the first row's width.  Since we don't
    # store explicit col counts, derive from the grid: total chunks / rows.
    # The caller builds specs with known grid dims, so we can rely on the fact
    # that the grid is rectangular.  We just need to find the number of columns.
    # Convention: specs are sorted by index; the first row's indices are 0..cols-1.
    if not specs:
        return 1
    # Find where the x-position resets (second row starts).
    # Simplest: sqrt heuristic for square-ish grids, but callers know the grid.
    # We store the grid width in the first spec as a custom field if available.
    cols = specs[0].get("gridCols")
    if cols is not None:
        return int(cols)
    # Fallback: assume square grid
    n = len(specs)
    cols = 1
    while cols * cols < n:
        cols += 1
    return cols
