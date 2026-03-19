from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import websockets
from loguru import logger

from .cropper import serve_crop_ui
from .state import CaptureState, _sha256
from .stitcher import stitch_chunks
from .tile_generator import generate_tile_pyramid
from .zone_config import save_zone_config

TILE_SIZE = 256
WS_PORT = 18586
MAX_CHUNK_PX = 4096


class CaptureOrchestrator:
    """Drives the capture pipeline over a WebSocket connection to the mod."""

    def __init__(
        self,
        repo_root: Path,
        config: dict[str, Any],
        state: CaptureState,
        ws_url: str = f"ws://localhost:{WS_PORT}",
    ) -> None:
        self.repo_root = repo_root
        self.config = config
        self.state = state
        self.ws_url = ws_url
        self._ws: Any = None

    async def connect(self) -> None:
        """Establish the WebSocket connection to the in-game mod."""
        try:
            self._ws = await websockets.connect(self.ws_url)
            logger.info(f"Connected to MapTileCapture mod at {self.ws_url}")
        except (ConnectionRefusedError, OSError) as exc:
            raise ConnectionError(
                f"Cannot connect to MapTileCapture mod at {self.ws_url}. "
                "Is the game running with the mod loaded?"
            ) from exc

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()

    # -- main loop ------------------------------------------------------------

    async def run(
        self,
        zones: list[str],
        variants: list[str] | None,
        force: bool = False,
        out_dir: Path | None = None,
    ) -> None:
        """Capture, stitch, crop-if-needed, and tile every zone x variant."""
        tile_out = out_dir or (self.repo_root / "src" / "maps" / "static" / "tiles")
        master_dir = self.repo_root / ".erenshor" / "masters"
        master_dir.mkdir(parents=True, exist_ok=True)

        for zone_key in zones:
            zc = self.config[zone_key]
            zone_variants = variants or zc.get("captureVariants", ["open"])

            for variant in zone_variants:
                master_path = master_dir / f"{zone_key}_{variant}.png"

                if self.state.should_skip(zone_key, variant, master_path, force=force):
                    logger.info(f"Skipping {zone_key}/{variant} (up-to-date)")
                    continue

                logger.info(f"Capturing {zone_key}/{variant}")
                try:
                    await self._capture_zone(zone_key, variant, zc, master_path)
                except _CaptureError as exc:
                    logger.error(f"Capture failed for {zone_key}/{variant}: {exc}")
                    continue

                # Crop UI if no cropRect configured
                if zc.get("cropRect") is None:
                    crop = serve_crop_ui(master_path, zone_key, zc, self.repo_root)
                    if crop:
                        zc["cropRect"] = crop
                        self.config[zone_key] = zc
                        save_zone_config(self.repo_root, self.config)
                        _apply_crop(master_path, crop)

                # Tile generation
                count = generate_tile_pyramid(
                    master_path, zone_key, variant, zc, tile_out
                )
                logger.info(f"Tiled {zone_key}/{variant}: {count} tiles")

                # Update state
                self.state.set_variant_state(zone_key, variant, {
                    "status": "ok",
                    "masterChecksum": _sha256(master_path),
                    "tileCount": count,
                })
                self.state.save(self.repo_root)

    # -- zone capture ---------------------------------------------------------

    async def _capture_zone(
        self,
        zone_key: str,
        variant: str,
        zc: dict[str, Any],
        master_path: Path,
    ) -> None:
        """Send capture_zone, collect chunks, stitch into master."""
        chunks = _build_chunk_grid(zc, master_path.parent)
        hide_roofs = variant == "clear"

        msg = {
            "type": "capture_zone",
            "zone": zone_key,
            "sceneName": zc["sceneName"],
            "variant": variant,
            "hideRoofs": hide_roofs,
            "sceneLoadTimeoutSecs": 30,
            "stabilityFrames": 10,
            "exclusionRules": zc.get("exclusionRules", []),
            "chunks": chunks,
        }
        await self._ws.send(json.dumps(msg))

        chunk_paths: list[Path] = []
        while True:
            raw = await self._ws.recv()
            resp = json.loads(raw)
            msg_type = resp.get("type")

            if msg_type == "chunk_complete":
                path = Path(resp["path"])
                chunk_paths.append(path)
                logger.debug(
                    f"  chunk {resp['chunkIndex']} complete: {path}"
                )

            elif msg_type == "capture_zone_complete":
                logger.info(
                    f"Zone {zone_key}/{variant} capture complete "
                    f"(roofs hidden: {resp.get('roofObjectCount', 0)})"
                )
                break

            elif msg_type == "capture_error":
                raise _CaptureError(resp.get("reason", "unknown error"))

        # Stitch chunks into master
        if chunk_paths:
            stitch_chunks(chunk_paths, chunks, master_path)


class _CaptureError(Exception):
    """Raised when the mod reports a capture failure."""


# -- chunk grid ---------------------------------------------------------------


def _build_chunk_grid(
    zc: dict[str, Any], output_dir: Path
) -> list[dict[str, Any]]:
    """Compute the chunk grid for a zone capture.

    The master image dimensions are ``baseTilesX * 2^maxZoom * 256`` by
    ``baseTilesY * 2^maxZoom * 256``.  If either dimension exceeds
    ``MAX_CHUNK_PX`` the image is split into multiple chunks.
    """
    max_zoom: int = zc["maxZoom"]
    base_x: int = zc["baseTilesX"]
    base_y: int = zc["baseTilesY"]
    origin_x: float = zc.get("originX", 0)
    origin_y: float = zc.get("originY", 0)

    master_w = base_x * (2**max_zoom) * TILE_SIZE
    master_h = base_y * (2**max_zoom) * TILE_SIZE

    cols = max(1, -(-master_w // MAX_CHUNK_PX))  # ceil division
    rows = max(1, -(-master_h // MAX_CHUNK_PX))

    # World-space dimensions that each pixel covers
    # We don't know world size here; the mod figures out camera placement.
    # We just divide the pixel canvas evenly.
    chunk_w = master_w // cols
    chunk_h = master_h // rows

    chunks: list[dict[str, Any]] = []
    idx = 0
    for row in range(rows):
        for col in range(cols):
            px_w = chunk_w if col < cols - 1 else master_w - chunk_w * (cols - 1)
            px_h = chunk_h if row < rows - 1 else master_h - chunk_h * (rows - 1)

            chunks.append({
                "index": idx,
                "gridCols": cols,
                "centerX": origin_x + (col + 0.5) * (px_w / master_w) * master_w / TILE_SIZE,
                "centerZ": origin_y + (row + 0.5) * (px_h / master_h) * master_h / TILE_SIZE,
                "worldWidth": px_w / TILE_SIZE,
                "worldHeight": px_h / TILE_SIZE,
                "pixelWidth": px_w,
                "pixelHeight": px_h,
                "outputPath": str(output_dir / f"chunk_{idx}.png"),
            })
            idx += 1

    return chunks


def _apply_crop(master_path: Path, crop: dict[str, int]) -> None:
    """Crop the master image in place according to the crop rect."""
    from PIL import Image

    img = Image.open(master_path)
    left = crop["left"]
    top = crop["top"]
    right = img.width - crop["right"]
    bottom = img.height - crop["bottom"]
    cropped = img.crop((left, top, right, bottom))
    cropped.save(master_path, "PNG")
    logger.info(f"Cropped master to {cropped.width}x{cropped.height}")
