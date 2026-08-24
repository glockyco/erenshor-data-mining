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
- **`maps dev --port N` ignored (resolved 2026-06-27)**: old CLI used `pnpm run dev -- --port 5180`, so Vite still bound `5173`. The maps CLI now calls Vite directly; use `uv run erenshor maps dev --port <port>`.

Tile capture / map incidents:
- **New zones invisible on map until tile-capture config exists**: after `extract build`, playtest map served local data fine for the 43 pre-existing zones but rendered 0 markers in the 4 new raid planes. `src/maps/src/lib/map/zone-config.ts` derives its zone list from `zone-capture-config.json` — any scene not listed is filtered out of marker queries entirely. Phase 4 (tile capture) is a hard prerequisite for new zones being visible at all, not just for tile imagery.
- **MapTileCapture auto-login requires fresh game state**: capture-mod's `EnsureInWorldCoroutine` only triggers from scene `Menu` or `LoadScene`. HotRepl `SceneManager.LoadScene(...)` during bounds discovery had jumped past the title; the mod waited for `MainCam` forever. Always restart the game between bounds discovery and capture run.
- **MapTileCapture deployment must be variant-isolated**: the mod CLI resolves standard CrossOver installs by the selected variant's Steam App ID before considering the legacy `ERENSHOR_GAME_PATH` fallback, and rejects an override whose `steam_appid.txt` contradicts `-V`. Use an explicit variant and loader, for example `uv run erenshor -V playtest mod deploy --mod map-tile-capture --loader bepinex`. Promoted to `skill://mod-pipeline`.
- **Bounds discovery missed NPC clusters**: median-filtered `MeshRenderer` bounds for `PlaneOfBrax` captured the static geometry footprint but missed the NPC spawn cluster outside it. The captured master rendered fine but cut off live markers. Promoted to `skill://tile-capture`: union with `SELECT MIN/MAX(x), MIN/MAX(z) FROM map_character_spawns WHERE scene = '<Zone>'`.
- **Zone-line entry points can fall outside the capture footprint**: `PlaneOfBrax` zone-line from Reliquary lands at game `(16, 480)` but the original capture had `originX=150` — the portal landing was cropped off the master. Promoted to `skill://tile-capture`: always verify per new zone that `zone_lines.landing_position_{x,z}` is within `originX..originX+baseTilesX*tileSize`.
- **`zone-positions.json` is a separate per-zone requirement**: adding to `zone-capture-config.json` and `DISPLAY_NAMES` is not enough — `/map` overview returns 500 (`Cannot read properties of null` in `buildZoneWorldPositions`) until the new zone also has a `worldX`/`worldY` entry in `zone-positions.json`. Promoted to `skill://interactive-map`.
- **`northBearing` source is the DB, not the JSON**: `zone-capture-config.json` carries `"northBearing": null` for every zone but that's an override slot — the actual bearing comes from `zones.north_bearing` in the variant DB (`buildZoneConfigs` in `src/maps/src/lib/map/zone-config.ts`). 3 of the 4 raid planes had bearing 0 (X-flip), but `PlaneOfVitheo` had bearing ~105° so its rendered AABB was 941×941 not 768×768. Layout math assuming uniform orientation produced visible overlap. Promoted to `skill://interactive-map`.

Historical session teardown incidents:
- **Conhost windows remained after a wineserver kill**: Wine reparented `conhost.exe` and the Unity crash handler to PID 1. Process-name searches could not prove which session owned them. `mod launch` now remains attached through CrossOver `--wait-children` and stops its validated process group.
- **Ad hoc shell signals were unreliable**: some bash `kill` forms rejected multiple PIDs or signal names. The owning commands now signal one dedicated process group. They do not construct a target list from global process names.
- **A detached `maps dev` server died after its orchestrator**: the server was started with `nohup`, and its database link had no reliable lifecycle owner. `maps dev` now stays in the foreground, owns its Vite process group, and restores its exact prior link state.
- **`erenshor -V main maps build` is not a link restoration command**: it copies the database into `src/maps/static/db/erenshor.sqlite` for a production build. `maps dev` restores only the link state that existed when it started.
