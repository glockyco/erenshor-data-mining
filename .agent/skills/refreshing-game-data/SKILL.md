---
name: refreshing-game-data
description: Refresh one Erenshor variant after a Steam update. Use from the new install through extraction, review, validation, and approved publication.
---

# Refresh game data

Run these steps from the repository root. Put `-V {v}` before the command group. Use the variant installed in the CrossOver Steam bottle. Do not publish a non-shipping variant to a shared destination.

## 1. Prepare the installed build

1. Update the selected variant in Steam. Run `uv run erenshor -V {v} status` to check the resolved installation and tools.
2. Run `uv run erenshor extract packages` on a fresh checkout. It restores the Editor dependencies before the rip.
3. Run `uv run erenshor -V {v} extract rip` for each new build. It replaces the Unity project only after a successful staged extraction. Do not infer freshness from directory modification times.
4. Compare the new scripts with the preceding build's `variants/{v}/backups/build-{id}/scripts/`. Investigate changed mechanics outside the code-facts registry before publication.

If rip reports an unreadable old `Packages/manifest.json`, repair it before retrying. Rip must preserve manually added UPM dependencies. It also injects Newtonsoft.Json through `com.unity.nuget.newtonsoft-json`. Do not install another copy under `src/Assets/Packages`.

## 2. Export and build

1. Run `uv run erenshor -V {v} extract export`. The command replaces the raw SQLite database and backs up the raw database and decompiled scripts by Steam build ID.
2. If the pre-export field-coverage gate fails, reconcile `src/tools/ExportSurface/field-coverage.json` with the shipped DLL and listener types. Do not bypass the gate.
3. If export exits 3, classify the findings in `variants/{v}/.export/dynamic-spawn-errors.json`. Follow `skill://auditing-spawn-coverage` and rerun export until it passes.
4. Run `uv run erenshor -V {v} extract code-facts`. Resolve changed matcher bindings against the shipped assembly. Follow `skill://code-facts`.
5. Run `uv run erenshor -V {v} extract build`. The build requires the code-facts tables. It writes the clean database and adds it to the build's backup.
6. If the build rejects a stale `expected_npc_name`, review the new raw NPC name. Update or remove that `mapping.json` override, then rebuild. Fix processor errors at their source in `src/erenshor/application/processor/`.

If Unity reports `Unity licensing validation failed`, open Unity Hub, wait for licensing, and retry export. If exported data still shows the old build, rerip and export before rebuilding.

## 3. Review and validate

1. If an earlier clean backup exists, run `uv run erenshor -V {v} extract changes --limit 0`. Use `--since <build-id>` to select another backed-up build. Review removals and changed values, not only totals. Without an earlier backup, inspect the new clean database directly.
2. For `main`, run `uv run erenshor -V main test data`. This command always reads main's database. For other variants, inspect the selected clean database and consumer previews. Follow `skill://auditing-spawn-coverage` for the post-build orphan and mapping-exclusion audits. Resolve new orphans before publishing sheets, wiki, or map.
3. Run `uv run erenshor -V {v} wiki generate`. It validates every generated page and fails on a semantic error. For the shipping variant, generate Lua modules with `uv run erenshor -V {v} wiki generate-lua`.

## 4. Review consumers before publication

| Consumer | Scope and action |
| --- | --- |
| Sheets | Each variant has its own spreadsheet ID. Preview with `uv run erenshor -V {v} --dry-run sheets deploy --all-sheets`. Publish with `uv run erenshor -V {v} sheets deploy --all-sheets` only after approval. |
| Wiki | `erenshor.wiki.gg` is one shared target. Review local output. Publish the shipping variant only after approval. Use `skill://wiki-templates` to select pages for `wiki deploy-repo-pages`. |
| AdventureGuide | `uv run erenshor -V {v} guide compile` replaces the shared `quest_guides/guide.json`. `uv run erenshor -V {v} guide export-mod` replaces `quest_guides/quest-guide.json`, which the mod embeds. Run both for the shipping variant and commit both files before building the mod. |
| Map | `uv run erenshor -V {v} maps build` reads that variant's clean database. Check with `uv run erenshor -V {v} maps preview`. After approval, deploy the shipping variant with `uv run erenshor -V {v} maps deploy` to both Workers. |
| Tiles | Map tiles, `src/maps/src/lib/data/zone-capture-config.json`, `src/maps/src/lib/data/zone-positions.json`, and `mapping.json` are shared. Review cross-variant effects. |

For new zones, follow `skill://tile-capture` to add capture bounds and tiles. Add the overview position using `skill://interactive-map`. Without a capture-config entry, the map omits the zone and its markers. Without an overview position, `/map` can fail. Restart the game between bounds discovery and `capture run` if auto-login waits for `MainCam`.

Use `skill://sheets-queries` for sheet queries. The map keeps `/db/erenshor.sqlite` on both hosts. Do not create a database symlink in `src/maps/static/db`; the site publishes the database through its route. If the canonical Worker deploy succeeds and the legacy deploy fails, resume with `uv run erenshor -V {v} maps deploy --target legacy` after approval.
