---
title: Playtest Release Data Refresh
type: plan
status: implemented
created: 2026-07-11
parent: 2026-07-09-erenshor-planning-overview
archived: 2026-07-11
---

# Playtest Release Data Refresh

## Context
Refresh the `playtest` variant from the current Steam installation before the Monday, July 13 release: update game files, rebuild raw and clean data, validate export coverage, publish playtest Google Sheets, generate local wiki outputs, compile the release guide, build the playtest map, and recapture configured map tiles. The MediaWiki site and Cloudflare map worker are shared production targets, so no wiki or map deployment is performed. The run must stop at each gate and leave a verified, locally built release candidate rather than silently publishing partial data.

## Approach

1. **Capture the pre-refresh baseline and download the current playtest build.**
   - From the repository root, run the read-only preflight first and record its output: `python .agent/skills/refreshing-game-data/scripts/check_pipeline_freshness.py playtest`.
   - Record the current clean-DB scene list before downloading so post-refresh zone additions can be identified without comparing against the unavailable main schema:
     ```bash
     sqlite3 variants/playtest/erenshor-playtest.sqlite \
       "SELECT scene_name FROM zones WHERE scene_name IS NOT NULL ORDER BY scene_name;" \
       > /tmp/erenshor-playtest-scenes-before.txt
     ```
     If the clean DB is absent, record an empty baseline and continue; the later build gate is authoritative.
   - Update Steam files with checksum validation: `uv run erenshor -V playtest extract download --validate`. This requires the configured Steam credentials and playtest app ID `3090030`; do not substitute the main variant.
   - Re-run the freshness checker after download. A pre-download “fresh” result is not sufficient because Steam may have installed a new build.
   - If the post-download checker reports the Unity `ExportedProject` is stale or missing, run `uv run erenshor -V playtest extract rip`. `rip` intentionally removes and recreates `variants/playtest/unity`, restores the `src/Assets/Editor` symlink, copies required packages, and regenerates IDE project files. If it reports fresh, skip `rip`.
   - If `rip` ran, commit the freshly decompiled Assembly-CSharp tree to the detached discovery repository and inspect the change, using the project’s external git directory (not a `.git` inside the wiped Unity tree):
     ```bash
     G="git --git-dir=variants/playtest/decompile-history.git --work-tree=variants/playtest/unity/ExportedProject/Assets/Scripts/Assembly-CSharp"
     $G add -A && $G commit -m "game build playtest"
     $G diff HEAD~1 --stat
     ```
     Do not invent a build identifier for the commit message. A failed detached-history commit is a gate: preserve the extracted tree and report it before continuing.

2. **Export, derive code facts, and build the clean database in canonical order.**
   - Run the strict Unity export with profiling enabled: `uv run erenshor -V playtest extract export --profile`. It must pass field-coverage, Unity-project, Editor-link, and Unity-version preconditions. Export exit 3 is the dynamic-spawn coverage gate, not a recoverable warning.
   - If export exits 3, stop downstream consumers; read `variants/playtest/.export/dynamic-spawn-errors.json`, classify every `findings[]` entry against the freshly decompiled script and GUID-resolved prefab, remove stale catalog entries, update `src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml` only with evidence-backed `allowed`/`denied` entries and mandatory denial reasons, then rerun export until exit 0. Do not bypass the gate or publish an unresolved finding.
   - Run `uv run erenshor -V playtest extract code-facts` against the shipped `variants/playtest/game/Erenshor_Data/Managed/Assembly-CSharp.dll`. If the analyzer reports a matcher drift, re-derive the named method with the pinned decompiler, update `src/tools/CodeFacts/specs/erenshor-facts.json` and every tagged consumer together, then rerun code-facts; never point the analyzer at Unity’s locally recompiled assemblies.
   - Run `uv run erenshor -V playtest extract build`. This consumes the raw export plus `code_facts` tables and writes `variants/playtest/erenshor-playtest.sqlite`; mapping warnings for genuinely new entities must be resolved at the source mapping before continuing.
   - Print the extraction profile for evidence: `uv run erenshor -V playtest extract profile report --latest`. The report must include successful `extract export`, `extract code-facts`, and `extract build` spans for this run.

3. **Validate the new database and enforce spawn coverage before any consumer publish.**
   - Run the playtest integration suite exactly as configured by `tests/integration/conftest.py`: `uv run pytest tests/integration -v`. It uses `variants/playtest/erenshor-playtest.sqlite`; do not run `golden capture` because its output is shared and this is not an approved playtest-to-main baseline cutover.
   - Run all three post-build audits from the spawn-coverage gate:
     ```bash
     uv run python src/tools/audit_spawn_coverage.py --variant playtest --json
     uv run python src/tools/audit_mapping_exclusions.py --variant playtest --only-content --json
     ```
     For every orphan or content-bearing exclusion, run `uv run python src/tools/trace_character_sources.py --variant playtest --stable-key "<stable-key-from-audit>" --json`. Continue only when the remaining orphans are documented Category-C/runtime-position residuals or every new orphan has an explicit catalog/mapping decision; otherwise fix the source/export/mapping and repeat export through build.
   - Verify that `variants/playtest/erenshor-playtest.sqlite` opens, has nonzero items, and contains the expected post-refresh scene list. Save the post-refresh list for tile selection:
     ```bash
     sqlite3 variants/playtest/erenshor-playtest.sqlite \
       "SELECT scene_name FROM zones WHERE scene_name IS NOT NULL ORDER BY scene_name;" \
       > /tmp/erenshor-playtest-scenes-after.txt
     ```

4. **Refresh and verify map tiles for the configured playtest zones.** (Depends on step 3; shared tile files are intentionally updated, but no map worker deployment occurs.)
   - Confirm the configured set and tile budget before opening the game: `uv run erenshor -V playtest capture status` and `uv run erenshor -V playtest capture budget`. The capture command’s own `--variant` means tile style (`clear`/`open`), not the data variant; omit it so each zone’s `captureVariants` is honored. Proceed only if the configured estimate remains within the documented Cloudflare file budget; do not change zone bounds/config in this refresh.
   - Validate that every scene in `/tmp/erenshor-playtest-scenes-after.txt` has a matching `sceneName` in `src/maps/src/lib/data/zone-capture-config.json`. If a new scene lacks a config entry, stop and report it rather than inventing bounds; the user’s existing configuration is the source of truth.
   - Build/deploy the capture mod for the playtest game before starting capture: `uv run erenshor mod build --mod map-tile-capture`, then `uv run erenshor -V playtest mod deploy --mod map-tile-capture`. If `ERENSHOR_GAME_PATH` is set, verify it resolves to the playtest installation; unset or correct it for this invocation so the DLL cannot land in main’s BepInEx directory. Run `uv run erenshor -V playtest mod setup` only if the build reports missing game reference DLLs, then rerun the targeted build and deploy.
   - Before capture, snapshot `.erenshor/capture-state.json` and the `st_mtime_ns` of every configured master path listed by that state into `/tmp/erenshor-playtest-capture-before.json` (or an equivalent session-local read-only snapshot). The expected set is every zone key in `zone-capture-config.json` crossed with that zone’s `captureVariants` (defaulting to `clear` only when the key is absent). This baseline is required because a failed forced capture can otherwise leave a stale `ok` record behind.
   - Start the playtest game with the deployed MapTileCapture mod and leave the WebSocket server listening on `localhost:18586`. Run the full configured capture with forced recapture so changed geometry in the newly added zones is not hidden by the checksum skip: `uv run erenshor -V playtest capture run --force`. This intentionally captures every configured zone/variant rather than passing `--variant playtest`; the capture output is shared under `src/maps/static/tiles/` and `.erenshor/masters/`.
   - After capture, run `uv run erenshor -V playtest capture status`; every expected zone/variant must have a post-run `ok` or config-defined `same_as_clear` state, its master must exist, and its master mtime must be newer than the pre-run snapshot in `/tmp/erenshor-playtest-capture-before.json`. Also require a capture-complete log record and newly written tile output for every expected pair in this invocation; a checksum may legitimately remain equal when the scene rendered identically, but unchanged mtime or missing completion/tile evidence is a failure. Do not accept an unchanged pre-run state merely because status still says `ok`. Inspect the generated tile count for each newly added scene; if a master is dark, blank, off-center, or missing, use the tile-capture lighting/bounds diagnostics and recapture that zone with `--zones <scene> --force` before proceeding.

5. **Build and locally smoke-test the playtest map without deploying it.** (Depends on step 3; run after tile capture so the generated tile manifest includes the refreshed files.)
   - Run `uv run erenshor -V playtest maps build`. This executes the CLI-owned maps lint/check/test, publishes mod artifacts for the site, regenerates tile/OG/icon assets, copies the playtest DB into the shared maps DB path, builds into the variant-isolated `src/maps/build-playtest`, and stamps input hashes.
   - Start `uv run erenshor -V playtest maps preview --port 4173` in a managed background session and use the browser/Playwright smoke path from `skill://interactive-map`: load `http://localhost:4173/map`, wait for the app to initialize, assert the `/map` response succeeds with no console errors, and request at least one tile URL for each newly captured scene from `src/maps/static/tiles/tiles-manifest.json` (expect HTTP 200). If a development-only marker/debug assertion is needed, use `uv run erenshor -V playtest maps dev` instead of assuming `window.__mapDebug` exists in the production preview. Stop the preview through the normal session teardown. Do not run `maps deploy`; `src/maps/wrangler.jsonc` is the single shared Cloudflare target.

6. **Compile shared release guide output for the playtest release.** (Depends on step 3.)
   - Because playtest is the imminent release variant, run `uv run erenshor -V playtest guide compile`, which overwrites the single `quest_guides/guide.json` consumed by the next AdventureGuide build. Parse the resulting JSON and record the reported node/edge, quest, and item counts; run focused checks `uv run pytest tests/integration/test_guide_compiler.py tests/integration/test_entity_graph.py -v`.
   - If the release decision changes and playtest is not the shipping/cutover variant, skip this step and restore the shipping guide by compiling the shipping variant before any AdventureGuide packaging; never leave a main/playtest-ambiguous shared guide behind.

7. **Refresh local wiki caches and generate all playtest wiki outputs, but do not deploy.** (Depends on steps 3 and 6 where applicable.)
   - Preview each local producer without writes: `uv run erenshor -V playtest --dry-run wiki fetch --force` and `uv run erenshor -V playtest --dry-run wiki generate`.
   - Fetch current live page text into the variant-scoped cache with `uv run erenshor -V playtest wiki fetch --force`. This is an API read/cache write, not a deployment; credentials/API failures are a gate because generation must preserve current manual fields.
   - Generate legacy local article pages with `uv run erenshor -V playtest wiki generate`. Full unfiltered generation is required so stale generated entries are removed; do not replace it with a targeted `--pages-file` run. Lua/Cargo module generation is not part of this release because that pipeline is not fully implemented yet; do not run `wiki generate-lua`.
   - Do not run `wiki deploy`, `wiki deploy-repo-pages`, `wiki refresh-embedded`, or any other MediaWiki write. The only wiki-side network operation in this plan is fetching current source pages.

8. **Deploy playtest Sheets after a dry-run and stop owned sessions.** (Depends on steps 3 and 7.)
   - Preview all configured tabs against the playtest clean DB: `uv run erenshor -V playtest --dry-run sheets deploy --all-sheets`. Confirm the command reports the playtest spreadsheet target, not main, and no query failures.
   - Deploy the playtest spreadsheet: `uv run erenshor -V playtest sheets deploy --all-sheets`. This is safe because `config.toml` gives playtest its own spreadsheet ID; require the Google service-account credentials to have Editor access. A failed tab is a failed release gate, not a partial success to ignore.
   - Stop each foreground `maps dev` or `mod launch` command with one interrupt. Each command owns its process group, and `maps dev` restores its prior database link. Do not use the retired global teardown procedure from this historical plan. Re-run the final read-only freshness and status checks if an owning command reports a cleanup failure.

## Critical files & anchors

- `skill://refreshing-game-data` — canonical order, variant scope, shared-output rules, and command-owned shutdown.
- `skill://auditing-spawn-coverage` — export exit-3 handling and mandatory residual audits before publishing.
- `skill://tile-capture` — MapTileCapture WebSocket, forced recapture, shared tile output, budget, and visual checks.
- `src/erenshor/cli/commands/extract.py` (`download`, `rip`, `export`, `code_facts`, `build`) — exact extraction side effects and gate order.
- `src/erenshor/cli/commands/maps.py`/`capture.py` and `src/erenshor/cli/commands/wiki.py` — exact local build/capture/generation commands and variant option semantics.

## Verification

- Freshness: post-download `check_pipeline_freshness.py playtest` reports the installed game and Unity project relationship; after any rip it reports a fresh project, and raw/clean paths exist after export/build.
- Export/build: export exits 0 (and deletes `.export/dynamic-spawn-errors.json`), code-facts succeeds, build succeeds, and `extract profile report --latest` reports successful spans for all three extraction commands.
- Data behavior: integration tests pass against the explicit playtest DB; the three audit commands produce JSON with no unexplained orphan/exclusion findings; SQLite queries show nonzero item rows and post-refresh scene names.
- Tiles: `capture status` has no error states after forced capture; every expected zone×variant has a successful post-run state, a capture-complete record, a newly written master/tile output newer than the pre-run snapshot (not merely a stale `ok` state), and each newly added configured scene has a generated tile pyramid. A concrete visual check loads `/map` in local map preview without console errors and requests one manifest-listed tile for each newly captured scene, receiving HTTP 200.
- Map build: `maps build` succeeds, creates/stamps `src/maps/build-playtest`, and `maps preview` serves `/map` on port 4173 with the refreshed playtest database.
- Guide/wiki: `quest_guides/guide.json` parses and focused guide tests pass; wiki dry-runs show planned outputs, real fetch/generate complete without failed pages, and generated articles are present under the playtest wiki directory. Lua/Cargo generation is intentionally skipped until that pipeline is fully implemented.
- Sheets: dry-run formats every tab; real `--all-sheets` completes with zero failed tabs and targets the configured playtest spreadsheet.
- Boundaries: no command writes to `erenshor.wiki.gg` or deploys the Cloudflare worker; each long-running command stops its own processes, and `maps dev` restores its prior database link.

## Assumptions & contingencies

- The current playtest freshness check observed game files at 2026-07-02 21:23, ExportedProject at 2026-07-10 14:51, raw DB at 15:15, and clean DB at 15:24, with 95 levels and 49 sharedassets bundles; Steam download is still mandatory because the release requires the current remote build.
- The top-level variant option is always `-V playtest`; capture’s nested `--variant` is never used for data-variant selection and is omitted in the full capture command.
- Playtest is treated as the imminent shipping variant for `guide compile`. If that release role is withdrawn, use the explicit fallback in step 6 before leaving the shared guide output.
- The existing tile configuration is treated as correct; if the budget exceeds the documented limit or a scene is missing from configuration, stop before capture and report the exact scene/budget rather than editing bounds or silently skipping it.
- If Steam reports no update, still rerun the post-download freshness gate and continue through export/build; current timestamps do not substitute for a successful pipeline run.
- If Unity licensing, Steam authentication, Google credentials, MediaWiki fetch credentials, BepInEx deployment, or the MapTileCapture WebSocket is unavailable, stop at that gate with the exact command output and preserve all completed local outputs; do not bypass the gate or run a shared deployment as a workaround.
- `golden capture` is intentionally omitted because it writes shared `tests/golden/` baselines and no playtest-to-main cutover was requested. `maps deploy` and all wiki deployment commands are intentionally omitted because their targets are shared across variants.
