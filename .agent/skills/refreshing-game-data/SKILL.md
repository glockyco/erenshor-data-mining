---
name: refreshing-game-data
description: Order, gates, and per-consumer variant scope for refreshing a variant's data pipeline after a Steam game update. Use when a new Erenshor build needs to flow into raw/clean DBs, sheets, the interactive map, wiki, AdventureGuide, or tile capture.
---

# Refreshing a Variant After a Game Update

Wire the per-subsystem pipelines into the right order and surface the variant-scope cross-deploy hazards that are easy to get wrong. Subsystem mechanics live in the per-subsystem skills — start here, then follow the links.

`erenshor -V {v} …` — the variant flag is **top-level** on the CLI; subcommand-local placement fails with `No such option: --variant`.

## Variant scope of every consumer

| Consumer | Variant-scoped? | Hazard |
|---|---|---|
| Raw + clean SQLite | Yes | `variants/{v}/erenshor-{v}{-raw}.sqlite` |
| Google Sheets | Yes, per-spreadsheet | each variant has its own `spreadsheet_id` in `config.toml` |
| AdventureGuide `guide.json` | Input-variant scoped, single output | overwrites `quest_guides/guide.json` — only one variant ships at a time |
| Interactive map build | Yes via `build_dir`; deploy target is the single `src/maps/wrangler.jsonc` worker | shared DB symlink `src/maps/static/db/erenshor.sqlite` is swapped per build |
| Map tiles + `zone-capture-config.json` | **Shared** | tiles added for one variant are visible to all |
| `mapping.json` | **Shared** | overrides apply across all variants |
| MediaWiki | **Single target — `erenshor.wiki.gg`** | `wiki deploy -V playtest` overwrites main's pages |

## Preflight

Run the freshness check before starting:
```bash
python .agent/skills/refreshing-game-data/scripts/check_pipeline_freshness.py {v}
```
It reports whether the Unity `ExportedProject` is stale relative to `Erenshor_Data` (re-rip needed) and prints the variant's current asset counts.

## Canonical order

`rip → export → code-facts → build → validate → republish`. Each gate must pass before the next.

### 1. Re-rip if stale
`erenshor -V {v} extract rip` — wipes the Unity project, runs AssetRipper, recreates the `Assets/Editor` symlink and `Packages/` copy, and restores any user-added UPM deps + injects required ones (`com.unity.nuget.newtonsoft-json` today). See `skill://unity-export-system` for the listener architecture.

After re-ripping, commit the freshly-decompiled tree in its detached discovery repo and diff against the prior build to surface mechanics changes outside the code-facts registry (see `skill://code-facts`). The git-dir lives outside the work tree because `extract rip` `rmtree`s the whole Unity project; explicit flags need no `.git` inside the wiped dir, so history survives the rip:
```bash
G="git --git-dir=variants/{v}/decompile-history.git --work-tree=variants/{v}/unity/ExportedProject/Assets/Scripts/Assembly-CSharp"
$G add -A && $G commit -m "game build <version>"
$G diff HEAD~1 --stat   # churn outside known fact targets = new mechanics to model
```

### 2. Unity batch export
`erenshor -V {v} extract export` — writes raw SQLite. Compilation errors usually mean new content needs a listener field (see `skill://unity-export-system`). Unity license expiry (`Unity licensing validation failed`) is a recurring hands-on step: `open -a "Unity Hub"`, wait, retry.

### 3. Code facts
`erenshor -V {v} extract code-facts` — extracts hardcoded game constants from the assembly into raw SQLite. Fails loudly if hardcoded game logic changed shape; re-derive the affected specs in src/tools/CodeFacts/specs/erenshor-facts.json (see the code-facts skill).

### 4. Python build
`erenshor -V {v} extract build` — produces clean DB. Watch the log for `mapping.json` warnings about new entities lacking overrides; add minimal entries and re-run. Schema/processor errors surface here — fix at the source under `src/erenshor/application/processor/`.

### 5. Validate
Run `pytest tests/integration -v` against this variant. **Do not** run `golden capture` on a non-main variant — see Variant safety rules. Then run `skill://auditing-spawn-coverage` — new event scripts in a patch silently widen the spawn-coverage gap and that skill is the gate that catches them before sheets/wiki/map ship.

### 6. Republish only the variant-safe outputs
- **Sheets:** `erenshor -V {v} sheets deploy --all-sheets` (dry-run first with the global `--dry-run` flag).
- **Local map:** `erenshor -V {v} maps build && erenshor -V {v} maps dev` (or `preview`). The teardown script restores the main symlink at end of session.
- **Guide compile / Wiki / Cloudflare map deploy:** see Variant safety rules.

### 7. Tile capture for new zones
Compute the delta of `SELECT DISTINCT scene_name FROM zones` minus the keys of `zone-capture-config.json`. For each new scene, follow `skill://tile-capture` end-to-end: bounds discovery, config entry, `DISPLAY_NAMES`, `capture run`, verification, commit per zone. New zones also need a `zone-positions.json` entry — see `skill://interactive-map`.

## Timing and profiling refreshes

Extraction commands persist profile runs under `variants/{variant}/profiles/`.
Use them to separate Steam download, AssetRipper, Unity subprocess overhead,
Unity C# export, listener `OnAssetFound`, listener `OnScanFinished`, code-facts,
and clean build cost before optimizing.

```bash
uv run erenshor -V playtest extract profile report --latest
```

For slow Unity exports, rerun only the export with listener profiling:

```bash
uv run erenshor -V playtest extract export --profile
```

Compare `unity.batch_subprocess` against Unity's `[EXPORT_COMPLETE]` or
`unity.ExportBatch` span. Large gaps before the C# export usually mean Unity
license refresh, package restore, asset import, or script compilation rather
than listener work. Use `listener.OnAssetFound.*` rows for per-asset extraction
cost and `listener.OnScanFinished.*` rows for table creation/delete/insert cost.
Open the `.trace.json` artifact in Perfetto when the nested timeline matters.

## Variant safety rules

Shared-output actions require an explicit variant gate before running:

- `golden capture` writes to shared `tests/golden/`. During an intentional
  playtest→main cutover, capture from `playtest` when the golden tests'
  integration database also resolves to `playtest` (the Phase 3 cutover
  workflow); otherwise capture from `main`.
- `wiki deploy` overwrites `erenshor.wiki.gg` (single target across all variants).
- `guide compile` overwrites the single `quest_guides/guide.json` embedded into the next AdventureGuide build.
- `maps deploy` publishes the single `src/maps/wrangler.jsonc` Worker target. Build/playtest locally, but deploy only the shipping variant.

## End-of-session teardown

```bash
python .agent/skills/refreshing-game-data/scripts/teardown_session.py
```
Stops the maps dev server, kills the game and its wine satellites (Erenshor.exe, conhost.exe holding BepInEx console windows, UnityCrashHandler64.exe zombies), quits Unity Hub if it was opened, and restores the map DB symlink to main. The cleanup has multiple pitfalls (bash `kill` builtin quirks, wine processes reparenting to launchd, conhost surviving `pkill -f wineserver`) — the script handles all of them. Don't reinvent it manually.

## Recovering from common mistakes

| Symptom | Cause | Recovery |
|---|---|---|
| Map shows wrong content during main work | DB symlink left on another variant | run the teardown script, or `ln -snf "$(pwd)/variants/main/erenshor-main.sqlite" src/maps/static/db/erenshor.sqlite` |
| `extract export` produces unchanged data despite new game files | Forgot to re-rip; Unity scanned stale ExportedProject | re-rip, then re-export |
| Wiki deploy from non-main variant overwrote main's pages | Variant safety rule ignored | `erenshor -V main wiki generate && erenshor -V main wiki deploy` |
| `golden capture` from non-main variant broke main's tests | Capture writes to shared `tests/golden/` | `git checkout tests/golden/`, re-capture from main after main's DB is current |
| Master tile clipped, NPC cluster cut off | Bounds computed from geometry alone | see `skill://tile-capture` "Setting Bounds for a New Zone" |
| `/map` returns 500 after adding a new zone | Missing `zone-positions.json` entry | see `skill://interactive-map` |
| `guide.json` shipped wrong variant's data | `guide compile` run for non-shipping variant | re-run for the shipping variant, rebuild AdventureGuide |

## See also

- `skill://auditing-spawn-coverage` — post-build orphan audit, gate for sheets/wiki/map deploy
- `skill://unity-export-system` — listener and record architecture
- `skill://tile-capture` — bounds discovery, capture mod, exclusion rules
- `skill://interactive-map` — overview rendering, `zone-positions.json`, `north_bearing`, debug hooks
- `skill://mod-pipeline` — dual-loader build/deploy and variant install resolution
- `skill://runtime-eval` — HotRepl prerequisites and snippets
- `skill://wiki-templates` — wiki page generation and field preservation
- `skill://sheets-queries` — sheets query patterns
- `references/incident-log.md` — dated session notes from prior refreshes
