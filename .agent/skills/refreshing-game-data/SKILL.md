---
name: refreshing-game-data
description: Canonical end-to-end process for refreshing one variant's data after a Steam game update. Use when the Erenshor (main/playtest/demo) game build changes and downstream consumers (DBs, sheets, map, wiki, guide, mods) need to catch up.
---

# Refreshing a Variant After a Game Update

This skill captures the **order, gates, and per-consumer variant scope** that are easy to get wrong when refreshing data after a new Steam build. Per-subsystem mechanics live in the subsystem skills — this skill is about wiring them together correctly.

## Variant scope of every consumer (memorize this table)

| Consumer | Variant-scoped? | Notes / Risk |
|---|---|---|
| Raw + clean SQLite | Yes | `variants/{v}/erenshor-{v}{-raw}.sqlite` |
| Images output | Yes | `variants/{v}/images/` |
| Google Sheets | Yes, **per-spreadsheet** | playtest/main have distinct `spreadsheet_id` in `config.toml`; demo has none |
| AdventureGuide compiled `guide.json` | Yes (input variant) | Output is single-file at `quest_guides/guide.json`; embedded into mod DLL at build time. **Only one variant's guide ships at a time.** |
| Interactive map (build output) | Yes via `build_dir` | `[variants.{v}.maps]` section required; map's DB symlink (`src/maps/static/db/erenshor.sqlite`) is **swapped per build**, not per variant directory |
| Map tiles (`src/maps/static/tiles/`) | **Shared** | Tiles are variant-agnostic on disk; new zones added for one variant become visible to all |
| `zone-capture-config.json` | **Shared** | Same |
| `mapping.json` | **Shared** | Display/wiki overrides apply across all variants |
| MediaWiki | **SINGLE TARGET — `erenshor.wiki.gg`** | `wiki deploy --variant playtest` overwrites main's pages. NEVER deploy a non-main variant to wiki without an explicit decision. |
| Cloudflare map deployment | Yes via `deploy_target` | Configure distinct `deploy_target` per variant to make accidental cross-deploys impossible |

## Stale-state symptoms

Before running anything, sanity-check freshness:

```bash
stat -f "%Sm %N" \
  variants/{v}/game/Erenshor_Data \
  variants/{v}/unity/ExportedProject \
  variants/{v}/erenshor-{v}.sqlite
```

- `ExportedProject` mtime older than `Erenshor_Data` → **re-rip required**. Skipping this exports stale data silently.
- `erenshor-{v}-raw.sqlite` missing while `erenshor-{v}.sqlite` exists → an earlier export was wiped/never ran; treat the clean DB as untrusted until re-built.
- Steam touching `Erenshor_Data` mtime does **not** mean content changed. Compare asset counts (`ls game/Erenshor_Data/level* | wc -l` and `sharedassets*.assets | wc -l`) against the previous baseline to confirm a content delta vs. a metadata-only patch.

## CLI flag placement (easy gotcha)

`--variant` / `-V` is a **top-level** flag on `erenshor`, not on subcommands. Always write `erenshor -V {v} extract rip`, never `erenshor extract rip --variant {v}` (the latter fails with `No such option: --variant`).

## Canonical order

The pipeline is `rip → export → build → validate → republish`. Each gate must pass before the next. Don't skip.

### 1. Re-rip if stale
`erenshor -V {v} extract rip` — wipes `variants/{v}/unity/`, runs AssetRipper, **automatically** recreates `Assets/Editor` symlink and copies `Packages/`. Don't try to do these by hand.

### 2. Unity batch export
`erenshor -V {v} extract export` — writes raw SQLite. Failures usually mean the listeners need a new field for content introduced in this version (see `skill://unity-export-system`).

### 3. Python build
`erenshor -V {v} extract build` — produces clean DB. **Watch the log** for:
- `mapping.json` warnings about new entities lacking overrides → fix in `mapping.json` (see existing entries for the shape: `wiki_page_name`, `display_name`, `image_name`, optional `is_wiki_generated`/`is_map_visible`)
- Schema/processor errors → fix in `src/erenshor/application/processor/`

### 4. Validate + golden refresh (main only)
Run integration tests against this variant. `tests/integration/test_golden.py` and `tests/golden/{wiki,sheets,map}/*` are **main-only** — the tests hardcode `variants/main/...` paths, but `erenshor -V {v} golden capture` accepts any variant and writes to the shared `tests/golden/` dir. Running golden capture with a non-main variant silently overwrites main's baselines with that variant's data and breaks main's regression tests. **Only run `golden capture` when the variant is main.** For non-main variants, skip this step.

### 5. Republish only what's variant-safe

- **Sheets:** `erenshor -V {v} sheets deploy` is safe — each variant has its own spreadsheet.
- **Map (local):** swap symlink via `erenshor -V {v} maps build`, then `erenshor -V {v} maps dev` (or `preview`).
- **Guide compile:** `erenshor -V {v} guide compile` overwrites `quest_guides/guide.json` for whichever variant ran last. Only compile for the variant whose AdventureGuide release you intend to ship.
- **Wiki:** see the warning above. Default is "do not deploy unless this is the production variant whose pages should live at `erenshor.wiki.gg`".

### 6. Tile capture for new zones
Compute the delta:
```python
playtest_scenes = {r[0] for r in db.execute("SELECT DISTINCT scene_name FROM zones WHERE scene_name IS NOT NULL")}
configured = set(json.load(open("src/maps/src/lib/data/zone-capture-config.json")).keys())
new_zones = sorted(playtest_scenes - configured)
```
Per zone: bounds discovery via HotRepl (`skill://tile-capture`) → add `zone-capture-config.json` entry → add `DISPLAY_NAMES` in `src/maps/src/lib/maps.ts` → `erenshor -V {v} capture run --zones <Z>` → verify centered → commit per zone.

`capture budget` before committing — Cloudflare ~20k file ceiling.

## Session teardown (mandatory)

Tile capture spawns long-lived processes that don't die when the orchestrator returns. End every non-main session with:

1. **Stop the maps dev server.** `pkill -KILL -f "vite dev"` may miss it — Vite runs as `node`. Find via `lsof -i :5173 -P -sTCP:LISTEN` and `kill -9` the listed PID directly.
2. **Stop the playtest game and its wine satellites.** Visible BepInEx console windows are owned by `conhost.exe`, not `wineserver`. Every fresh launch produces a stack of:
   - `Erenshor.exe` (the game itself)
   - `UnityCrashHandler64.exe` × N (often 2–3, one per game launch attempt)
   - `conhost.exe` × N (one per BepInEx console window — these are what stay visible)
   - `winedevice.exe` × N (recent ones from today; older ones from prior sessions can be left)

   They all get reparented to launchd (PID 1) and stay alive after `pkill -f wineserver`. List with `ps aux | grep -iE "Erenshor Playtest|conhost|UnityCrashHandler"` and kill via `os.kill(pid, signal.SIGKILL)` from Python. The bash `kill` builtin rejects multi-PID and bare `-KILL` invocations on macOS (use `kill -9` one PID at a time, or `python -c "import os, signal; [os.kill(p, signal.SIGKILL) for p in [...]]"`). Leave older-dated `winedevice.exe` zombies (CrossOver keeps these around per-bottle) and processes from unrelated games (e.g. Ancient Kingdoms) alone.
3. **Quit Unity Hub** if you opened it for licensing: `osascript -e 'quit app "Unity Hub"'`, then `pkill -9 -f UnityLicensingClient`.
4. **Restore the main map symlink.** The map's DB symlink at `src/maps/static/db/erenshor.sqlite` is the most error-prone shared state. The simplest restore is direct (one line, no rebuild, no dev server, idempotent):
   ```bash
   ln -snf "$(pwd)/variants/main/erenshor-main.sqlite" src/maps/static/db/erenshor.sqlite
   ```
   Caveat: `erenshor -V main maps build` **copies** the DB (and refuses if `src/maps/build/` exists without `--force`), while `erenshor -V main maps dev` does the symlink but leaves a server running. The `ln -snf` form above is the right tool when all you want is the symlink restored cleanly.

## Per-variant commit hygiene

Commits that touch only `variants/{v}/...` outputs aren't needed — those paths are gitignored. The commits that **do** land during a refresh:
- `chore(mapping): add overrides for <variant> <feature> entities`
- Any `feat(export)` / `fix(pipeline)` for schema/processor adjustments
- `chore(tests): refresh <variant> golden baselines for v<X>`
- `feat(config): add maps section for <variant>` (first time only)
- `feat(map): capture <Zone> tiles` (one per zone — `zone-capture-config.json` + `maps.ts` + tiles + thumbnail)

## Recovering from common mistakes

| Symptom | Cause | Recovery |
|---|---|---|
| Map shows wrong content while on `main` work | Symlink left pointing at another variant | `erenshor -V main maps build` |
| `extract export` exits with `Unity licensing validation failed` | Unity Personal license needs periodic refresh; CLI cannot do this headlessly | Open Unity Hub (GUI) on the host to refresh, then retry `erenshor -V {v} extract export` |
| `golden capture` with `-V playtest` broke main's regression tests | Capture writes to shared `tests/golden/`; tests read main's DB | Don't capture goldens from non-main variants. Restore via `git checkout tests/golden/` then `erenshor -V main golden capture` once main DB is rebuilt. |
| `extract export` writes same data as before despite new game files | Forgot to re-rip; Unity scanned stale ExportedProject | `erenshor -V {v} extract rip`, then re-export |
| Wiki deploy from playtest variant changed main's pages | Used `erenshor -V playtest wiki deploy` against `erenshor.wiki.gg` | Re-run `erenshor -V main wiki generate && erenshor -V main wiki deploy` to overwrite back |
| Master tile clipped/off-centre for a new zone | Bounds snippet caught outliers, OR snippet relied only on `MeshRenderer` and missed NPC spawn locations (NPCs use `SkinnedMeshRenderer` and are often clustered outside the static-mesh footprint) | Use the median-filter snippet referenced in `skill://tile-capture`. Also **union the bounds with `SELECT MIN/MAX(x), MIN/MAX(z) FROM map_character_spawns WHERE scene = '<Zone>'`** from the variant's clean DB — spawn coordinates are the authoritative source for where players will be. |
| `guide.json` ships wrong variant's data | `guide compile` overwritten by a later run against another variant | Re-run `erenshor -V {v} guide compile` for the variant whose mod you'll publish, then rebuild the mod |
| `/map` route returns 500 after adding new zones to `zone-capture-config.json` | `buildZoneWorldPositions` (in `src/maps/src/lib/map/zone-config.ts`) requires a matching entry in `src/maps/src/lib/data/zone-positions.json` — adding a zone to capture-config without a world-position entry crashes the overview map | Add the new zone to `zone-positions.json` with `worldX`/`worldY` placing it sensibly on the overview map. There is no autocomputed default. |

## Issues log

Append new failure modes here as they're encountered. Format: variant + version + symptom + root cause + fix. Keep it terse — link to commit/PR for detail. If a pattern recurs across versions, promote it to the "Recovering from common mistakes" table above.

### 2026-05-18 — playtest raid update
- **CLI flag placement**: First-time pipeline attempt used `extract rip --variant playtest`; the CLI rejected with `No such option: --variant`. `--variant`/`-V` is top-level only. Skill updated; see "CLI flag placement" section above.
- **Unity license expired**: `extract export` failed with `Unity licensing validation failed`. CLI's error message correctly directs to "Start Unity Hub". This is a recurring hands-on step on every machine running Unity Personal — promoted to the recovery table.
- **`Newtonsoft.Json` missing after rip**: `extract export` failed on a freshly-ripped playtest with `CS0246: type 'Newtonsoft' not found` on `GuildTopicListener` / `LootTableListener`. Root cause: AssetRipper rewrites `Packages/manifest.json` to only `com.unity.modules.*` entries, wiping the UPM Newtonsoft package the Editor scripts hard-depend on. Main had survived only because `com.coplaydev.unity-mcp` (added manually post-rip) transitively pulled Newtonsoft. Fixed in commit `8ab87985`: `extract rip` now snapshots non-modules deps before AssetRipper runs and re-applies them, and unconditionally injects `REQUIRED_UPM_PACKAGES` (Newtonsoft today) after the rip. Future fresh rips on any variant compile out-of-the-box; user-added deps like `unity-mcp` survive too.
- **Golden capture is variant-shared**: noticed `golden capture` accepts `--variant` and writes to a shared `tests/golden/` dir, but the test suite is main-only. Promoted to the recovery table. For this run, skipped golden capture entirely — main hasn't received the new content so its baselines are still valid.
- **New zones invisible on map until tile-capture config exists**: After `extract build`, the playtest map served local data fine for the 43 pre-existing zones but rendered 0 markers in the 4 new raid planes (`PlaneOfBrax`/`Fernalla`/`Soluna`/`Vitheo`). Root cause: `src/maps/src/lib/map/zone-config.ts` derives its zone list from `zone-capture-config.json` — any scene not listed there is filtered out of marker queries entirely. This is intentional (the page needs bounds/origin to place markers in world space) but means Phase 4 of the refresh is a hard prerequisite for new zones being visible at all, not just for tile imagery.
- **`maps dev --port N` ignored**: passed `--port 5180`; Vite still bound `5173`. The CLI's `pnpm run dev -- --port 5180` shape doesn't forward correctly. Non-blocking; just use the printed URL.
- **`maps dev` server outlives the orchestrator and silently dies later**: spawned via `nohup ... &`; after `mod launch` was killed by `pkill -f wineserver`, the dev server caught a SIGTERM cascade and shut down, removing the symlink on the way out. Always check the dev log before declaring "still running"; restart explicitly if needed.
- **MapTileCapture auto-login requires fresh game state**: capture-mod's `EnsureInWorldCoroutine` only triggers from scene `Menu` or `LoadScene`. If HotRepl `SceneManager.LoadScene(...)` jumped past the title screen during bounds discovery, the mod just waits for `MainCam` forever and times out. **Always restart the game between bounds discovery and capture run**, or load `LoadScene` via HotRepl first.
- **MapTileCapture mod deploys to `$ERENSHOR_GAME_PATH`, not `--variant`**: `_get_game_path()` consults the env var first and falls back to the variant's `game_files` dir. With `ERENSHOR_GAME_PATH` set to main's install in the CrossOver bottle, `erenshor -V playtest mod deploy --mod map-tile-capture` lands the DLL in main's plugins/, not playtest's. Override per-invocation: `ERENSHOR_GAME_PATH="$HOME/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/Erenshor Playtest" uv run erenshor -V playtest mod deploy --mod map-tile-capture`. Same applies to `mod launch`.
- **Playtest install in bottle missing HotRepl dependencies**: fresh playtest install had `ErenshorLogs.dll`, `InteractiveMapCompanion.dll`, `JusticeForF7.dll` only — no `HotRepl.BepInEx.dll` or `mcs.dll`. HotRepl needs both (`mcs.dll` is required by `HotRepl.Evaluator.MonoCSharpEvaluator`). Copy both from main's `BepInEx/plugins/` and restart the game.
- **Bounds discovery missed NPC clusters**: median-filtered `MeshRenderer` bounds for `PlaneOfBrax` captured the static geometry footprint (~1213x524) but missed the NPC spawn cluster that extended outside. The captured master rendered fine but cut off live markers. Fix: union with `SELECT MIN/MAX(x), MIN/MAX(z) FROM map_character_spawns WHERE scene='<Zone>'` from the variant's clean DB before computing `baseTilesX`/`baseTilesY`/`originX`/`originY`. Promoted to recovery table.
- **`zone-positions.json` is a separate per-zone requirement**: adding a new zone to `zone-capture-config.json` and `DISPLAY_NAMES` is not enough — the overview `/map` route crashes server-side with `Cannot read properties of null` in `buildZoneWorldPositions` until the zone also has an entry in `src/maps/src/lib/data/zone-positions.json` with `worldX`/`worldY` (these are the zone's offset on the overview world map; placeholder values work but make the zone overlap others until tuned). Promoted to recovery table.
- **Process cleanup is non-trivial**: bash `kill -9 a b c` errors "too many jobs or processes specified" because `kill` is a shell builtin that parses each token as a job spec; `kill -KILL pid` errors "invalid signal name" because the builtin doesn't accept long signal names. Workaround: use Python's `os.kill(pid, signal.SIGKILL)` (also reliably reports `ProcessLookupError` so you can verify), or `/bin/kill -9 <pid>` one at a time. Wine processes reparent to launchd, so the parent chain doesn't help.
- **Conhost windows held BepInEx UI open after wineserver kill**: visible BepInEx console windows belonged to `conhost.exe` processes (PIDs 5804, 6427 today), not `wineserver` or `Erenshor.exe`. `pkill -f wineserver` and the `UnityCrashHandler64.exe` sweep both missed them, so the windows stayed on screen even after every other process was dead. Added `conhost.exe` to the teardown checklist above.
- **`maps build` is not a symlink restore tool**: assumed `erenshor -V main maps build` would re-symlink `src/maps/static/db/erenshor.sqlite` to main; it actually _copies_ the DB, and refuses to run if `src/maps/build/` exists unless given `--force`. The symlink that the dev workflow creates is left dangling at the wrong variant. Teardown section now uses `ln -snf` directly.
- **`northBearing` source is the DB, not the JSON**: `src/maps/src/lib/data/zone-capture-config.json` carries `"northBearing": null` for every zone, which looks like the source of truth but is actually the override slot. The render-time bearing comes from `zones.north_bearing` in the variant clean DB (see `buildZoneConfigs` in `src/maps/src/lib/map/zone-config.ts`). Three of the four raid planes have `north_bearing = 0.0` (renders as a simple X-flip), but `PlaneOfVitheo` has `north_bearing ≈ 105°` so its overview rendering is rotated 75°. Layout math that assumes the same orientation for all zones produces visible overlap — the rotated AABB of Vitheo is 941×941, not the raw 768×768 of its tile rectangle.
- **Zone-line entry points can fall outside the capture footprint**: tile capture bounds are derived from MeshRenderer geometry + spawn-point coords, but the `zone_lines` landing point where you arrive from another zone is a third input that's not included. PlaneOfBrax's entry from Reliquary lands at game `(16, 480)` but the original capture had `originX=150` — the portal landing and surrounding terrain were cropped clean off the master. Always verify per new zone: `SELECT landing_position_x, landing_position_z FROM zone_lines WHERE destination_zone_stable_key IN (SELECT stable_key FROM zones WHERE scene_name = '<Zone>')` falls within `originX..originX+baseTilesX*tileSize` and `originY..originY+baseTilesY*tileSize`. Fix the capture config first, then re-capture, before placing the zone on the overview.
