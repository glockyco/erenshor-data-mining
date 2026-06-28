---
name: auditing-spawn-coverage
description: After a Steam update, find characters the export pipeline failed to place in the world. Use when the dynamic-spawn gate fails the export (exit 3), when investigating a "no spawn data" report, or as a routine post-update gate before sheets/wiki/map deploy.
---

# Auditing Spawn Coverage After a Game Update

`SpawnPointListener` + `SpawnPointTriggerListener` cover world-placed
`SpawnPoint` components. Everything else a character can be spawned from —
event scripts, dialog `Spawn` fields, chained `Spawns[]` lists, summon
spells — is covered by `DynamicSpawnSourceListener` driven by a tristate
catalog and a **fail-fast gate**. This skill is how you respond when the gate
fires after a patch, and how you audit the residual orphans and `mapping.json`
exclusions afterward.

Complements `skill://refreshing-game-data` (runs at its validate gate) and
`skill://unity-export-system` (listener/record boilerplate).

## Coverage model — what is automated

| Pathway | How it's covered |
|---|---|
| `SpawnPoint` / `SpawnPointTrigger` | exported directly |
| `Spell.pet_to_summon_stable_key` | spell join |
| Event-script / dialog / chained spawns | `DynamicSpawnSourceListener` + catalog |
| Zone-tick random spawners (Category C, e.g. `SivakayanSpectres`) | **deferred — not covered** |

`DynamicSpawnSourceListener` walks every Assembly-CSharp `MonoBehaviour` by
reflection and classifies each serialized `Character`/`GameObject`/`IList`
field against `src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml`:

- **allowed, Category A** (direct event-script spawn) → raw
  `DynamicCharacterSpawns` → merged into `character_spawns` (with
  `source_script` set) by the Python build.
- **allowed, Category B** (chained `Spawns[]` on a Character prefab) → raw
  `CharacterChainedSpawns` → expanded by `expand_chained_spawns()`.
- **denied** → skipped; the `reason` is the audit trail.
- **unknown** (the `(script, field)` pair is in neither list) → **gate fails,
  export exits 3** and writes the error envelope.

## Primary workflow — respond to the gate

1. `uv run erenshor -V {v} extract export`.
2. **Exit 0** → coverage classified. Go to *Audit residuals*.
3. **Exit 3** → read the envelope at
   `variants/{v}/.export/dynamic-spawn-errors.json`. Two arrays:
   - `findings[]` — unclassified candidates. Each has `script_type`,
     `field_name`, `field_kind`, and (when resolvable) `example_prefab_path`,
     `example_stable_key`, `example_display_name`, `host_scene_path`. The
     example fields already did the GUID resolution for you.
   - `stale_entries[]` — catalog entries whose `script_type` no longer exists
     in the assembly (the script was renamed or cut this patch).
4. Classify every finding (next section); remove every stale entry from the
   catalog.
5. Re-run export until exit 0. The gate auto-deletes the envelope on success.

The gate makes coverage **non-optional**: a new spawn-source script (or a new
field on an old one) cannot ship silently — it shows up as a finding. There is
no separate "diff the orphan count to detect new pathways" step anymore; the
gate is that step.

## Classify a finding

For each `(script_type, field_name)`, open
`variants/{v}/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/<script_type>.cs`
(Roslyn is loaded against this tree — `lsp definition`/`lsp references` work):

- **allowed** iff some `Object.Instantiate(<field>, …)` yields a GameObject
  carrying a `Character`/`NPC` component. UI, FX, projectile, ward-toggle, and
  damage-area prefabs are **denied** — they have no `Character`.
- **Field name ≠ prefab name**: always trust the GUID, not the identifier.
  `MalarothFeed.Malaroth` references `Shivunax.prefab`. The envelope's
  `example_prefab_path`/`example_stable_key` resolve this; verify against the
  decompiled `Instantiate` call.
- **Runtime-rebound fields** (`Faith = MySpawn.SpawnedNPC.GetChar();`,
  `RewardListener.Frost/Inferno`, `ShiveringPhantomWardListener.ward1/2`) are
  **denied** — the originating `SpawnPoint` already covers the placement.
- A field whose prefab is spawned but **positioned at runtime** (singleton
  access, random NavMesh point) cannot be emitted by the listener; deny it with
  a reason and handle visibility through `mapping.json` (see *Residuals*).

Edit the catalog:

```toml
[[allowed]]
script = "ScriptType"
fields = ["FieldA", "FieldB"]
position_field = "SpawnLoc"   # optional; comma-separated; omit → host transform

[[denied]]
script = "ScriptType"
fields = ["WardA"]
reason = "Visual effect toggles (SetActive), not Instantiate spawns."
```

`reason` is mandatory on `denied` — it is the only record of *why* a candidate
was rejected, and it is what a future auditor reads instead of re-deriving it.
Never deny a field globally just to silence the gate; an over-broad denial
suppresses the next patch's real finding.

## Audit residuals (after exit 0 + `extract build`)

Three reproducible scripts in `src/tools/` (all accept `--variant {v}` and
`--json`):

- **`audit_spawn_coverage.py`** — orphans: characters with no spawn row, no
  covering dedup sibling, and no summoning spell. Categorized and
  cross-referenced against `mapping.json`. `--include-disabled` adds characters
  whose every spawn is initially disabled. This script runs the canonical
  orphan SQL below.
- **`audit_mapping_exclusions.py`** — excluded characters
  (`is_wiki_generated=0`/`is_map_visible=0`) that still have content
  (loot/dialog/vendor) → potential false positives. `--only-content`.
- **`trace_character_sources.py`** — GUID-traces a character through every
  `.unity`/`.prefab` file. `--stable-key`, `--only-excluded`, `--verdict`,
  `--json`. Verdicts: `has_enabled_spawns`, `initially_disabled_spawns`,
  `dead`, etc. C# files hold no prefab GUIDs, so script-instantiation evidence
  comes from the catalog and the dynamic-spawn tables, not from this trace.

Canonical orphan SQL (run against `variants/{v}/erenshor-{v}.sqlite`):

```sql
WITH no_spawn AS (
  SELECT c.stable_key, c.display_name
  FROM characters c
  LEFT JOIN (SELECT DISTINCT character_stable_key FROM character_spawns) s
    ON s.character_stable_key = c.stable_key
  WHERE s.character_stable_key IS NULL
)
SELECT ns.display_name, ns.stable_key
FROM no_spawn ns
LEFT JOIN character_deduplications d ON d.member_stable_key = ns.stable_key
WHERE (
        d.group_key IS NULL
        OR NOT EXISTS (
          SELECT 1 FROM character_spawns sp
          JOIN character_deduplications d2 ON d2.member_stable_key = sp.character_stable_key
          WHERE d2.group_key = d.group_key
        )
      )
  AND NOT EXISTS (SELECT 1 FROM spells sp WHERE sp.pet_to_summon_stable_key = ns.stable_key)
ORDER BY ns.display_name, ns.stable_key;
```

The filter drops two false orphans: characters whose **dedup sibling** has a
spawn (`character_deduplications.group_key`), and characters **summoned by a
spell** (`spells.pet_to_summon_stable_key`). The documented residual is the
Category C set plus prefabs spawned at runtime-determined positions. Anything
beyond that is either a new dead prefab to exclude or — if it had a serialized
spawn field — a finding the gate would already have surfaced.

## Deciding an orphan / exclusion

- **`is_enabled=0` is not a reachability verdict.** The GameObject may be
  `SetActive(true)` at runtime (quest-gated, trigger-radius). `is_enabled=1`
  conversely does not guarantee reachable coordinates.
- **Wiki inclusion and map visibility are independent.** A character with loot
  but only a runtime-determined position is wiki-visible
  (`is_wiki_generated=1`) and map-hidden (`is_map_visible=0`).
- **A `dead` verdict is not final.** Confirm via GUID re-trace **and**
  name-search the decompiled scripts for the alias pattern (field name pointing
  at a differently-named prefab, the Shivunax case). Only exclude
  (`is_wiki_generated=0, is_map_visible=0`) once all three come back empty.
- **Do not blanket-exclude by type.** Treasure chests have loot and belong on
  the wiki even when their position is player-triggered.

Refuse to ship sheets/wiki/map (`skill://refreshing-game-data` step 5) until
the export exits 0 **and** the orphan count is at the documented residual or
every new orphan has a catalog/mapping decision in this patch's worktree.

## Non-orphan look-alikes — do not export

- **Runtime-rebound trackers**: fields reassigned at runtime from
  `MySpawn.SpawnedNPC`; the host `SpawnPoint` already covers them.
- **`bkp` / `_dupe` prefab names**: intentional duplicates referenced only by
  event scripts; the matching catalog entry covers them. Do not add a separate
  row for the "real" version.
- **`TOWNSPERSON` templates**: inspector-time placeholders for `SimPlayerMngr`.
  Filtered at the orphan SQL, never exported.

## See also

- `skill://refreshing-game-data` — calls this skill at the validate gate.
- `skill://unity-export-system` — `DynamicSpawnSourceListener`, record, and
  `StableKeyGenerator` boilerplate.
- `docs/plans/2026-05-28-spawn-coverage-audit.md` — the original orphan-by-
  script mapping and the taxonomy this catalog was built from.
