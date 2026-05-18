# Refreshing-Game-Data Incident Log

Append-only log of failure modes encountered during real refresh sessions. Searchable corpus for "has this happened before?" Patterns that recur across versions should be promoted to the SKILL.md recovery table or to the relevant subsystem skill.

Entry format: dated H2 heading per refresh session, terse bullets per incident with symptom + root cause + commit/fix reference.

---

## 2026-05-18 — playtest raid update (4 new Ethereal Planes)

Context: playtest game build added `PlaneOfBrax`, `PlaneOfFernalla`, `PlaneOfSoluna`, `PlaneOfVitheo` (raid content, level 40-42 deities accessed from Reliquary via `quest:alterplane`). +140 items, +45 spells, +10 quests over prior playtest baseline.

Pipeline incidents:
- **CLI flag placement**: First-time pipeline attempt used `extract rip --variant playtest`; the CLI rejected with `No such option: --variant`. `--variant`/`-V` is top-level. Now documented in SKILL.md preamble.
- **Unity license expired**: `extract export` failed with `Unity licensing validation failed`. Recurring hands-on step: `open -a "Unity Hub"`, wait, retry. Promoted to recovery table.
- **`Newtonsoft.Json` missing after fresh rip** (commit `8ab87985`): AssetRipper rewrites `Packages/manifest.json` to only `com.unity.modules.*` entries, wiping the UPM Newtonsoft package the Editor scripts hard-depend on. Main had survived only because `com.coplaydev.unity-mcp` (added manually post-rip) transitively pulled Newtonsoft. Fixed: `extract rip` now snapshots non-modules deps before AssetRipper runs and re-applies them, and unconditionally injects `REQUIRED_UPM_PACKAGES` (Newtonsoft today) after.
- **Golden capture is variant-shared**: `golden capture` accepts `--variant` and writes to the shared `tests/golden/` dir, but the test suite is main-only. Running on a non-main variant overwrites main's baselines. Promoted to Variant safety rules.
- **`maps dev --port N` ignored**: passed `--port 5180`; Vite still bound `5173`. The CLI's `pnpm run dev -- --port 5180` shape doesn't forward correctly. Non-blocking; just use the printed URL.

Tile capture / map incidents:
- **New zones invisible on map until tile-capture config exists**: after `extract build`, playtest map served local data fine for the 43 pre-existing zones but rendered 0 markers in the 4 new raid planes. `src/maps/src/lib/map/zone-config.ts` derives its zone list from `zone-capture-config.json` — any scene not listed is filtered out of marker queries entirely. Phase 4 (tile capture) is a hard prerequisite for new zones being visible at all, not just for tile imagery.
- **MapTileCapture auto-login requires fresh game state**: capture-mod's `EnsureInWorldCoroutine` only triggers from scene `Menu` or `LoadScene`. HotRepl `SceneManager.LoadScene(...)` during bounds discovery had jumped past the title; the mod waited for `MainCam` forever. Always restart the game between bounds discovery and capture run.
- **MapTileCapture mod deploys to `$ERENSHOR_GAME_PATH`, not `--variant`**: with the env var set to main's install in the CrossOver bottle, `erenshor -V playtest mod deploy` landed the DLL in main's plugins/. Override per-invocation: `ERENSHOR_GAME_PATH="<playtest install path>" uv run erenshor -V playtest mod deploy --mod map-tile-capture`. Promoted to `skill://mod-pipeline`.
- **Playtest install in bottle missing HotRepl dependencies**: fresh playtest install had three mod DLLs but no `HotRepl.BepInEx.dll` or `mcs.dll`. HotRepl needs both (`mcs.dll` required by `HotRepl.Evaluator.MonoCSharpEvaluator`). Copy from main's `BepInEx/plugins/` and restart. Promoted to `skill://runtime-eval`.
- **Bounds discovery missed NPC clusters**: median-filtered `MeshRenderer` bounds for `PlaneOfBrax` captured the static geometry footprint but missed the NPC spawn cluster outside it. The captured master rendered fine but cut off live markers. Promoted to `skill://tile-capture`: union with `SELECT MIN/MAX(x), MIN/MAX(z) FROM map_character_spawns WHERE scene = '<Zone>'`.
- **Zone-line entry points can fall outside the capture footprint**: `PlaneOfBrax` zone-line from Reliquary lands at game `(16, 480)` but the original capture had `originX=150` — the portal landing was cropped off the master. Promoted to `skill://tile-capture`: always verify per new zone that `zone_lines.landing_position_{x,z}` is within `originX..originX+baseTilesX*tileSize`.
- **`zone-positions.json` is a separate per-zone requirement**: adding to `zone-capture-config.json` and `DISPLAY_NAMES` is not enough — `/map` overview returns 500 (`Cannot read properties of null` in `buildZoneWorldPositions`) until the new zone also has a `worldX`/`worldY` entry in `zone-positions.json`. Promoted to `skill://interactive-map`.
- **`northBearing` source is the DB, not the JSON**: `zone-capture-config.json` carries `"northBearing": null` for every zone but that's an override slot — the actual bearing comes from `zones.north_bearing` in the variant DB (`buildZoneConfigs` in `src/maps/src/lib/map/zone-config.ts`). 3 of the 4 raid planes had bearing 0 (X-flip), but `PlaneOfVitheo` had bearing ~105° so its rendered AABB was 941×941 not 768×768. Layout math assuming uniform orientation produced visible overlap. Promoted to `skill://interactive-map`.

Session teardown incidents:
- **Conhost windows held BepInEx UI open after wineserver kill**: visible BepInEx console windows belong to `conhost.exe` processes, not `wineserver` or `Erenshor.exe`. `pkill -f wineserver` doesn't catch them. Now handled by `scripts/teardown_session.py`.
- **Process cleanup via bash `kill` is broken**: bash `kill -9 a b c` errors "too many jobs or processes specified" (multi-PID rejected); `kill -KILL pid` errors "invalid signal name" (long-form rejected by builtin). Workaround embedded in `scripts/teardown_session.py`: Python's `os.kill(pid, signal.SIGKILL)`.
- **`maps dev` server outlives the orchestrator and silently dies later**: spawned via `nohup ... &`; after `mod launch` was killed by `pkill -f wineserver`, the dev server caught a SIGTERM cascade and shut down, removing the symlink on the way out. Check the dev log before declaring "still running"; restart explicitly if needed. `scripts/teardown_session.py` now restores the symlink unconditionally.
- **`erenshor -V main maps build` is not a symlink restore tool**: it _copies_ the DB, and refuses to run if `src/maps/build/` exists unless given `--force`. Teardown script uses `ln -snf` directly.
