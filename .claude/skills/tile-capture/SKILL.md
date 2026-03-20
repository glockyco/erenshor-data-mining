# Tile Capture

Capture and generate map tiles for all Erenshor zones using the in-game MapTileCapture BepInEx mod.
For mod build/deploy and tunable constants, see `src/mods/MapTileCapture/CLAUDE.md`.

## Architecture

- **MapTileCapture mod** — BepInEx plugin, WebSocket server on port **18586**. Receives
  `capture_zone`, renders PNG chunks via orthographic camera, reports back to Python.
- **Python pipeline** — `src/erenshor/application/capture/`: orchestrator, tile_generator,
  stitcher, zone_config, state, budget.
- **Config** — `src/maps/src/lib/data/zone-capture-config.json` is the single source of truth
  for zone spatial parameters.

### Data Flow

```
uv run erenshor capture run
  -> connects to mod (ws://localhost:18586)
  -> for each zone x variant:
     -> sends capture_zone with chunk grid
     -> mod: loads scene via GameData.SceneChange.ChangeScene(), suppresses geometry,
             creates temp sun (scenes lack day/night when loaded directly), renders chunks
     -> Python: stitches chunks -> master.png -> tile pyramid (downscale only)
     -> writes tiles to src/maps/static/tiles/{zone}/{z}/{x}/{y}.webp
```

### CrossOver / Wine

Mod runs inside Wine. Orchestrator converts macOS paths to `Z:\path` format via
`_wine_path()` — transparent to CLI users.

### Diagnosing Capture Issues

```bash
grep -i "Map Tile Capture\|capture\|error\|exception" "$ERENSHOR_GAME_PATH/BepInEx/LogOutput.log"
```

- **TypeLoadException**: Missing DLL in ILRepack merge — check `ILRepack.targets`.
- **NullReferenceException from game code**: Expected (NPCDialogManager, SpawnPoint, etc. fail
  without a player). Does not affect capture.
- **Dark capture**: `GeometrySuppressor` directional light not created correctly.
- **Blank/transparent capture**: `ChunkRenderer` camera flags not set.

## CLI Commands

```bash
uv run erenshor capture run [--zones A B] [--variant clear] [--force]
uv run erenshor capture tile [--zones A B]   # re-tile from existing masters, no game needed
uv run erenshor capture status
uv run erenshor capture budget
uv run erenshor maps thumbnails [--zones A B]  # regenerate zone-maps gallery images
```

## Scene Lighting

Scenes loaded directly lack a directional light (day/night system never initialises).
`GeometrySuppressor` creates a temporary sun and ambient override, destroyed on `Dispose()`.
Zones with `usingSun: false` in config get a separate indoor light profile — tunable via
constants in `Plugin.cs` or at runtime via HotRepl.

## Tile Coordinate System

- `z=0`: `baseTilesX × baseTilesY` tiles; each covers 256 world units
- `z>0`: finer; `z<0`: coarser (2×2 combine, not master resize — preserves non-square aspect)
- `x`: 0-indexed from west; `y`: negative — `y=-1` = southernmost row
- `minZoom = -ceil(log2(max(baseTilesX, baseTilesY)))` when max > 1, else 0

## Variants

- `clear`: Roof layer removed from culling mask
- `open`: full geometry
- Zones with no Roof-layer objects: only `clear` generated; `open` marked `same_as_clear`

## 20k File Limit

Cloudflare/Wrangler hard limit ~20k files. Currently ~18,315. Managed via per-zone `maxZoom`
(large zones: 0, medium: 1, small: 2) and skipping `open` for outdoor zones.
Use `capture budget` before regenerating.

## Setting Bounds for a New Zone

Use HotRepl — do not guess. Query scene-owned objects only to exclude DontDestroyOnLoad
objects at the world origin that inflate bounds.

```bash
uv run erenshor eval run 'SceneManager.LoadScene("ZoneName");'; sleep 4

uv run erenshor eval run '
var scene = SceneManager.GetActiveScene();
var bounds = new Bounds(); bool first = true; int n = 0;
foreach (var go in scene.GetRootGameObjects())
    foreach (var r in go.GetComponentsInChildren<MeshRenderer>()) {
        var s = r.bounds.size;
        if (s.x > 200 || s.z > 200) continue;
        if (first) { bounds = r.bounds; first = false; } else bounds.Encapsulate(r.bounds);
        n++;
    }
string.Format("n={0} minX={1:F2} maxX={2:F2} minZ={3:F2} maxZ={4:F2}",
    n, bounds.min.x, bounds.max.x, bounds.min.z, bounds.max.z)
'
```

If outliers inflate the bounds, filter to within 100 world units of the median — see session
history for the median-filter snippet.

### Computing the origin

- `baseTilesX = ceil(width / 256)`, `baseTilesY = ceil(depth / 256)` — add 1 if very tight
- `originX = centerX - baseTilesX * 128`
- `originY = centerZ - baseTilesY * 128`

After capture, verify content is centered in the master:

```bash
uv run python -c "
from PIL import Image; import numpy as np
img = Image.open('.erenshor/masters/ZoneName_clear.png').convert('RGB')
arr = np.array(img)
# Background is dark slate (0.06, 0.07, 0.10) -> approx (15, 18, 26)
bg = (15, 18, 26)
diff = np.abs(arr.astype(int) - bg).sum(axis=2)
ys, xs = np.where(diff > 20)
cx, cy = (xs.min()+xs.max())//2, (ys.min()+ys.max())//2
print(f'content center ({cx},{cy}), image center ({img.width//2},{img.height//2})')
"
```

Content center should be within ~50 px of image center.

## Adding a New Zone

1. Add entry to `zone-capture-config.json` (use HotRepl bounds above)
2. Add display name to `DISPLAY_NAMES` in `src/maps/src/lib/maps.ts`
3. `uv run erenshor capture run --zones NewZone`
4. `uv run erenshor maps thumbnails --zones NewZone`
5. Deploy: `uv run erenshor maps build && uv run erenshor maps deploy`

## Known Issues

- **Baked lightmap shadows**: Removing roofs leaves their baked shadows on floors. No fix
  short of rebaking Unity lightmaps.
- **Game NullReferenceExceptions**: Expected when loading scenes without a player
  (NPCDialogManager, ZoneAnnounce, etc. fail in Start). Does not affect capture.
