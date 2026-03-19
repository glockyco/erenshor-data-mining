# Tile Capture

Capture and generate map tiles for all Erenshor zones using the in-game MapTileCapture BepInEx mod.

## Architecture

### Components

1. **MapTileCapture mod** (`src/mods/MapTileCapture/`) -- BepInEx mod running inside the game
   - WebSocket server on port **18586** (separate from InteractiveMapCompanion's 18585)
   - Receives `capture_zone` commands, renders PNG chunks via orthographic camera
   - Reports `chunk_complete`, `capture_zone_complete`, `capture_error` back to Python
   - `GeometrySuppressor` (IDisposable) hides UI, characters, particles, fog, spawn points
   - Creates temporary directional light + ambient overrides (scenes lack sun when loaded directly)
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

4. **Config** (`src/maps/src/lib/data/zone-capture-config.json`) -- single source of truth

### Data Flow

```
uv run erenshor capture run
  -> connects to MapTileCapture mod (ws://localhost:18586)
  -> for each zone x variant:
     -> sends capture_zone with chunk grid
     -> mod: loads scene, creates temp sun, suppresses geometry, renders chunks as PNG
     -> Python: stitches chunks -> master.png
     -> Python: interactive crop (first capture only, if no cropRect in config)
     -> Python: generates tile pyramid (all zoom levels, downscale only)
     -> writes tiles to static/tiles/{zone}/{z}/{x}/{y}.webp
```

## Development Cycle

The mod runs inside a CrossOver Wine bottle. The full edit-test cycle is:

```bash
# 1. Build and deploy mod
cd src/mods/MapTileCapture && dotnet build --configuration Debug
cd /path/to/repo && CROSSOVER_BOTTLE=Steam uv run erenshor mod deploy --mod map-tile-capture

# 2. Kill any running game instance
pkill -f "Erenshor.exe"

# 3. Launch game and wait for plugin
export ERENSHOR_GAME_PATH="..."  # see below
> "$ERENSHOR_GAME_PATH/BepInEx/LogOutput.log"
/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine \
  --bottle Steam "$ERENSHOR_GAME_PATH/Erenshor.exe" &

# 4. Wait for "Map Tile Capture ... loaded" in BepInEx/LogOutput.log (~10-15s)

# 5. Run capture
uv run erenshor capture run --zones Tutorial --variant clear --force
```

### CrossOver / Wine Path Mapping

The mod runs inside Wine and writes PNG files to Wine-mapped paths. The
orchestrator converts macOS paths to `Z:\path` format (Wine's mapping of
the host filesystem) via `_wine_path()`, and converts responses back via
`_from_wine_path()`. This is transparent to the CLI user.

### Diagnosing Capture Issues

Check the BepInEx log for errors:
```bash
grep -i "Map Tile Capture\|capture\|error\|exception" "$ERENSHOR_GAME_PATH/BepInEx/LogOutput.log"
```

Common issues:
- **TypeLoadException**: Missing DLL in ILRepack merge (check ILRepack.targets)
- **NullReferenceException from game code** (NPCDialogManager, SpawnPoint, etc.): Expected when loading scenes directly -- these are game objects that fail without a player. Not our bug.
- **Black/dark capture**: Scene lighting broken. GeometrySuppressor creates a temp sun; if it's still dark, check that the directional light is being created correctly.
- **Blank/transparent capture**: Camera not configured. Check ChunkRenderer sets orthographic, cullingMask, clearFlags.

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

To skip the crop UI during development, set a dummy cropRect in the zone config:
```python
config['ZoneName']['cropRect'] = {'top': 0, 'right': 0, 'bottom': 0, 'left': 0}
```

## Key Files

| File | Purpose |
|---|---|
| `src/maps/src/lib/data/zone-capture-config.json` | Zone spatial parameters (single source of truth) |
| `.erenshor/capture-state.json` | Per-zone capture status (gitignored) |
| `.erenshor/masters/{zone}_{variant}.png` | Raw capture masters (gitignored) |
| `src/maps/static/tiles/{zone}/{z}/{x}/{y}.webp` | Generated tile pyramid |
| `src/mods/MapTileCapture/` | BepInEx mod source |
| `src/erenshor/application/capture/` | Python pipeline |
| `src/erenshor/cli/commands/capture.py` | CLI commands |

## Scene Lighting

Scenes loaded via `SceneManager.LoadScene` lack a directional light -- the game's
day/night system never initialises. `GeometrySuppressor` handles this by:

1. Creating a temporary directional light (warm daylight, Euler 50/-30/0, no shadows)
2. Overriding `RenderSettings.ambientMode` to Flat with gray ambient at 60% intensity
3. Both are destroyed/restored in `Dispose()`

The existing spot/point lights (torches, fire effects) are left enabled -- they
contribute local color. Only the missing sun is synthesised.

## Tile Coordinate System

- z=0: `baseTilesX x baseTilesY` tiles at 256 world units/tile
- z>0: finer (more tiles); z<0: coarser (fewer tiles)
- x: 0-indexed from left (west)
- y: negative. **y=-1 = southernmost (bottom of master), y=-num_y = northernmost (top)**
- min_zoom = `-ceil(log2(max(baseTilesX, baseTilesY)))` if max > 1, else 0
- Negative zoom levels generated by 2x2 combine from level above (not by resizing master)

## Tile Generation Details

Positive/zero zoom: slice master image directly. Negative zoom: combine 2x2 tiles
from the level above into one tile. This preserves aspect ratio for non-square grids.
Pairs are formed south-to-north: the partial (padded) tile goes at the north end.

## Variants

- `clear`: Roof layer culling mask removed
- `open`: full geometry visible
- If zone has zero Roof-layer objects: only `clear` generated, `open` marked `same_as_clear`

## Geometry Suppression (GeometrySuppressor)

Always in `using` block (IDisposable). Suppresses:
- Time, fog, WorldFogController
- SpawnPoints (gameplay markers, not map content)
- Characters (except MiningNode, TreasureChest), particles, Canvas
- Nameplates, damage numbers, target rings, XP orbs, cast bars, world-space text
- LOD bias, maximum LOD level, camera clear flags

Creates:
- Temporary directional light (sun) + ambient overrides

`clear` only: camera.cullingMask removes Roof layer.

## 20k File Limit

Cloudflare/Wrangler limits at ~20k files. Currently ~18,315. Managed via:
- Per-zone `maxZoom` (large zones: 0, medium: 1, small: 2)
- Skipping `open` variant for outdoor zones (no Roof objects)
- Use `capture budget` to estimate before regenerating

## Building the Mod

```bash
uv run erenshor mod setup           # Copy game DLLs (first time only)
uv run erenshor mod build --mod map-tile-capture
uv run erenshor mod deploy --mod map-tile-capture
```

The mod uses Newtonsoft.Json (not System.Text.Json -- the latter is incompatible
with Unity's Mono runtime). ILRepack merges Fleck + Newtonsoft.Json into a single DLL.

## Adding a New Zone

1. Add entry to `src/maps/src/lib/data/zone-capture-config.json`
2. Add display name to `DISPLAY_NAMES` in `src/maps/src/lib/maps.ts`
3. Run `uv run erenshor capture run --zones NewZone`
4. Interactive crop UI opens automatically for first capture
5. Tiles generated and deployed with `uv run erenshor maps build && uv run erenshor maps deploy`

## Known Issues

- **Crop UI**: Apply button POST doesn't always land before browser closes. Workaround: set cropRect manually in zone-capture-config.json.
- **Baked lightmap shadows**: Removing roofs leaves their baked shadows on floors. No fix short of rebaking lightmaps.
- **Game NullReferenceExceptions**: Expected when loading scenes without a player. Game objects (NPCDialogManager, SpawnPoint, ZoneAnnounce) fail in Start(). Does not affect capture.
