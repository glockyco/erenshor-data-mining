---
name: tile-capture
description: Use when capturing or re-tiling zone maps, setting new bounds, or diagnosing MapTileCapture output and tile budgets.
---

# Tile capture

MapTileCapture is an internal native mod. Use `mod-pipeline` to build and deploy `map-tile-capture` for the chosen loader. For HotRepl tuning, use BepInEx and the `runtime-eval` procedure. Close the game before deployment.

## Capture and check

1. Deploy `map-tile-capture`, start the selected game, then run `uv run erenshor capture status`.
2. Run `uv run erenshor capture budget` before producing tiles. Keep the total below Cloudflare's 20,000-file limit.
3. Capture selected zones with `uv run erenshor capture run --zones ZoneName`. Repeat `--zones` for more zones. Use `--force` after changing bounds or lighting, because a valid master checksum otherwise skips recapture.
4. Run `uv run erenshor capture status` again. If the command reports a partial set, fix every failed zone before publishing.
5. Exit the game. To regenerate tiles from unchanged master PNGs without the game, run `uv run erenshor capture tile --zones ZoneName`.

Each zone in `src/maps/src/lib/data/zone-capture-config.json` must declare exactly one `captureVariants` entry: `clear` or `open`. Tiles share one zone directory. A second variant would erase the first pyramid. `clear` hides Roof-layer roots; `open` retains them. An explicit `--variant` override must match the zone's declared variant.

`capture tile` replaces the selected zone's entire tile directory. It removes obsolete zoom levels when settings shrink. Check the total from a complete retile against `capture budget`. Masters and status records live under `.erenshor/masters/` and `.erenshor/capture-state.json`.

## Set bounds for a new zone

1. Enter the zone in the running game. Probe only roots of the active scene. Persistent objects near world origin can distort bounds.
2. Get the static mesh bounds through HotRepl:

```bash
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

3. Check NPC spawn positions and zone-line landing positions in the selected variant's clean database. Static meshes alone can omit important map content:

```sql
SELECT MIN(x), MAX(x), MIN(z), MAX(z) FROM map_character_spawns WHERE scene = 'ZoneName';
SELECT landing_position_x, landing_position_z FROM zone_lines
 WHERE destination_zone_stable_key IN (SELECT stable_key FROM zones WHERE scene_name = 'ZoneName');
```

4. Include all three footprints. Inspect outlying meshes before discarding them, and pad the union by about 64 world units.
5. With `tileSize: 256`, set `baseTilesX = ceil(width / 256)` and `baseTilesY = ceil(depth / 256)`. Set `originX = centerX - baseTilesX * 128` and `originY = centerZ - baseTilesY * 128`.
6. Add the entry to `src/maps/src/lib/data/zone-capture-config.json` and its display name to `DISPLAY_NAMES` in `src/maps/src/lib/maps.ts`.
7. Capture with `uv run erenshor capture run --zones ZoneName --force`. Inspect the master in `.erenshor/masters/` for clipping and centering. Adjust bounds and recapture if necessary.
8. Start `uv run erenshor maps dev` in another terminal. Run `uv run erenshor maps thumbnails --zones ZoneName --url http://localhost:5173`, then stop the server.

## Diagnose a failed capture

- Run `uv run erenshor -V playtest mod status` with the intended variant. Check `BepInEx/LogOutput.log` for BepInEx or the in-game log UI for Lunaris.
- For dark indoor zones, verify `usingSun: false`. Both adapters expose `IndoorDirectional*` and `IndoorAmbient*` through `MapTileCapture.Plugin` for HotRepl tuning. Outdoor zones use their scene sun.
- For a blank master, inspect `ChunkRenderer` camera settings. For a type-load error, inspect `src/mods/MapTileCapture/ILRepack.targets` and redeploy a complete DLL.
- When editing capture cleanup, stop the active coroutine before disposing the WebSocket server. Dispose `GeometrySuppressor` so it restores camera, renderer, canvas, lighting, fog, and time scale.
- Load capture scenes through `GameData.SceneChange.ChangeScene()`, not `SceneManager.LoadScene()`. The former sets sun and atmosphere state for each zone.
