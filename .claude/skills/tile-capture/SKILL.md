# Tile Capture

Capture and generate map tiles for all Erenshor zones using the in-game MapTileCapture BepInEx mod.

## Architecture

### Components

1. **MapTileCapture mod** (`src/mods/MapTileCapture/`) -- BepInEx mod running inside the game
   - WebSocket server on port **18586** (separate from InteractiveMapCompanion's 18585)
   - Receives `capture_zone` commands, renders PNG chunks via orthographic camera
   - Reports `chunk_complete`, `capture_zone_complete`, `capture_error` back to Python
   - `GeometrySuppressor` (IDisposable) hides UI, characters, particles, fog, etc.
   - `ZoneBoundsProbe` auto-detects terrain bounds and `northBearing` from `ZoneAnnounce`

2. **Python capture pipeline** (`src/erenshor/application/capture/`)
   - `orchestrator.py` -- WebSocket client driving zone/variant capture sequence
   - `tile_generator.py` -- master PNG to tile pyramid (Pillow, downscale only)
   - `stitcher.py` -- concatenates chunks when master exceeds GPU RT limit (~4096px)
   - `cropper.py` -- local HTTP server + browser UI for interactive crop selection
   - `zone_config.py` -- reads/writes `zone-capture-config.json`
   - `state.py` -- capture state tracking (`.erenshor/capture-state.json`, gitignored)
   - `budget.py` -- tile count estimation

3. **CLI** (`src/erenshor/cli/commands/capture.py`)

4. **Config** (`src/maps/static/data/zone-capture-config.json`) -- single source of truth

### Data Flow

```
uv run erenshor capture run
  -> connects to MapTileCapture mod (ws://localhost:18586)
  -> for each zone x variant:
     -> sends capture_zone with chunk grid
     -> mod: loads scene, suppresses geometry, renders chunks as PNG
     -> Python: stitches chunks -> master.png
     -> Python: interactive crop (first capture only)
     -> Python: generates tile pyramid (all zoom levels, downscale only)
     -> writes {zone}/{variant}/{z}/{x}/{y}.webp
```

## CLI Commands

```bash
# Full pipeline (game must be running with MapTileCapture mod loaded)
uv run erenshor capture run
uv run erenshor capture run --zones Abyssal Azure
uv run erenshor capture run --zones Abyssal --variant clear
uv run erenshor capture run --force

# Tile-only (no game needed; re-tiles from existing masters)
uv run erenshor capture tile
uv run erenshor capture tile --zones Abyssal

# Interactive crop (opens browser UI)
uv run erenshor capture crop --zone Abyssal

# Status and budget
uv run erenshor capture status
uv run erenshor capture budget
```

## Key Files

| File | Purpose |
|---|---|
| `src/maps/static/data/zone-capture-config.json` | Zone spatial parameters (single source of truth) |
| `.erenshor/capture-state.json` | Per-zone capture status (gitignored) |
| `.erenshor/captures/{zone}/{variant}/master.png` | Raw capture masters (gitignored) |
| `src/maps/static/tiles/{zone}/{variant}/{z}/{x}/{y}.webp` | Generated tile pyramid |
| `src/mods/MapTileCapture/` | BepInEx mod source |
| `src/erenshor/application/capture/` | Python pipeline |
| `src/erenshor/cli/commands/capture.py` | CLI commands |

## zone-capture-config.json Schema

```json
{
  "Abyssal": {
    "sceneName": "Abyssal",
    "baseTilesX": 3,
    "baseTilesY": 3,
    "tileSize": 256,
    "maxZoom": 2,
    "originX": -40.0,
    "originY": -120.0,
    "northBearing": null,
    "captureVariants": ["clear", "open"],
    "cropRect": null,
    "exclusionRules": []
  }
}
```

- `originX`/`originY`: world coordinates of tile grid origin (top-left)
- `northBearing`: auto-detected from `ZoneAnnounce`, null until first capture
- `cropRect`: `{top, right, bottom, left}` in master pixels, null until crop
- `exclusionRules`: non-Roof geometry always hidden (both variants)

## Tile Coordinate System

- z=0: `baseTilesX x baseTilesY` tiles at 256 world units/tile
- z>0: finer (more tiles); z<0: coarser (fewer tiles)
- x: 0-indexed from left (west)
- y: negative (-1 at top/north)
- min_zoom = `-ceil(log2(max(baseTilesX, baseTilesY)))` if max > 1, else 0

## Variants

- `clear`: Roof layer culling mask removed
- `open`: full geometry visible
- If zone has zero Roof-layer objects: only `clear` generated, `open` marked `same_as_clear`

## Geometry Suppression (GeometrySuppressor)

Always in `using` block (IDisposable). Suppresses:
- Time, fog, WorldFogController
- Characters (except MiningNode, TreasureChest), particles, Canvas
- Nameplates, damage numbers, target rings, XP orbs, cast bars, world-space text
- LOD bias, maximum LOD level, camera clear flags

`clear` only: camera.cullingMask removes Roof layer.

## 20k File Limit

Cloudflare/Wrangler limits at ~20k files. Currently ~18,315. Managed via:
- Per-zone `maxZoom` (large zones: 0, medium: 1, small: 2)
- Skipping `open` variant for outdoor zones (no Roof objects)
- Use `capture budget` to estimate before regenerating

## Building the Mod

```bash
uv run erenshor mod setup           # Copy game DLLs
uv run erenshor mod build --mod map-tile-capture
uv run erenshor mod deploy --mod map-tile-capture
```

## Adding a New Zone

1. Add entry to `zone-capture-config.json` with baseTilesX/Y from game observation
2. Run `uv run erenshor capture run --zones NewZone`
3. Interactive crop UI opens automatically for first capture
4. Tiles generated and deployed with `uv run erenshor maps build && uv run erenshor maps deploy`
