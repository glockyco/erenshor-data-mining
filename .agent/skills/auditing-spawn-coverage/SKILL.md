---
name: auditing-spawn-coverage
description: After a Steam update, find characters that the export pipeline failed to place in the world via SpawnPoint scanning. Use when investigating "no spawn data" reports, or as a routine post-update gate before sheets/wiki/map deploy.
---

# Auditing Spawn Coverage After a Game Update

`SpawnPointListener` + `SpawnPointTriggerListener` cover only world-placed
`SpawnPoint` components. The game also spawns characters from dozens of
event scripts, dialog `Spawn` fields, summon spells, and zone-tick random
spawners. New scripts (or new prefab fields on existing ones) ship in every
patch — this audit catches the gap before downstream consumers (wiki/map)
silently mis-render those characters as "unplaced".

This skill complements `skill://refreshing-game-data` (runs *after* `extract
build` succeeds) and consumes `skill://unity-export-system` (for adding the
listener that closes the gap).

## When to run

- After **every** `extract build` against a freshly-rerun game version,
  before deploying sheets/wiki/map for that variant.
- When a wiki/map reader reports an in-game character with no spawn data.
- After making changes to the dedup or character-resolution logic.

## Step 1 — Pull orphans from the clean DB

```sql
-- Run against variants/{v}/erenshor-{v}.sqlite
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

The filter drops two categories that look orphaned but are actually covered:

- Characters whose **dedup sibling** has a spawn row (resolved via
  `character_deduplications.group_key`).
- Characters that are **summoned by a spell** (`spells.pet_to_summon_stable_key`).
  These are surfaced through the spell join, not via `character_spawns`.

Diff the resulting count against the previous run. Stable count → nothing
new this patch. Growth → new event script or new prefab field on an old one.

## Step 2 — Enumerate dynamic-spawn pathways in the new scripts

**Always use the variant's decompiled scripts**, not main's. Different
variants ship different content; cross-variant searches produce phantom
"new" findings.

```
variants/{v}/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/
```

Roslyn is loaded against this tree (verify with `lsp status`). Use `lsp
definition` / `lsp references` to navigate. Use `search` for these patterns:

```text
^\s*public\s+Character\s+\w+\s*;
^\s*public\s+(Character\[\]|List<Character>)\s+\w+\s*[;=]
^\s*public\s+(GameObject|GameObject\[\]|List<GameObject>)\s+\w+\s*[;=]
Instantiate\s*\(
```

For each new MonoBehaviour or new field on an old MonoBehaviour:

- Confirm the field is a **spawn source** by checking that some
  `Object.Instantiate(<field>, …)` chains `.GetComponent<Character>()` or
  `.GetComponent<NPC>()`. UI / FX / projectile / damage-area prefabs do not
  count — they have no `Character` component.
- Note the **host script type** (one listener per type).
- Note whether the field is **rebound at runtime** from another source (e.g.
  `Faith = MySpawn.SpawnedNPC.GetChar();`). Runtime-rebound fields do not
  add a new world placement — the originating `SpawnPoint` already covers
  them. Skip those.

Known spawn-source pathways (audit each at least once per major patch):

| Pathway | Where to look |
|---|---|
| `SpawnPoint.PossibleChars` / `SpawnPointTrigger` | already exported |
| `Spell.pet_to_summon_stable_key` | already exported (spell join) |
| `Character.SpawnOnDeath` | `Character.cs`, `Despawn.cs` |
| `NPCDialog.Spawn` | `NPCDialog.cs`, `NPCDialogManager.cs` |
| `Misc.SivakayanSpectres[]` via `ZoneAnnounce.SpawnSivakayanSpecter` | `Misc.cs`, `ZoneAnnounce.cs` |
| Boss-fight event scripts | `FernallaFightEvent`, `FernallaPortalEvent`, `FernallaPortalBoss`, `MizukiEvent`, `PhantomFightEvent`, `SiraetheEvent`, `SprinklesEvent`, `ZenithNadirScript`, `AstraListener`, `FaithEvent`, `GraceEvent`, `HonsusScript`, `MalarothFeed`, `StowawayPortal`, `WaveEvent`, `VithArena` |
| Interactive triggers | `Chessboard`, `Constellation`, `TreasureChestEvent`, `NPCFightEvent` |

## Step 3 — Map orphans to scripts

For each row in Step 1's output, walk this resolution chain (stop at first
hit):

1. **DB joins**: `spells.pet_to_summon_stable_key`,
   `character_spawns.protector_stable_key`,
   `character_spawns.spawn_upon_quest_complete_stable_key`,
   `character_deduplications.group_key`. Hit here → not a gap.
2. **Stable key → prefab file**: the suffix after `character:` is the
   prefab's lowercased `object_name`. Use `find` for
   `<object_name>.prefab` under `variants/{v}/unity/.../Assets`.
3. **Prefab GUID → referrers**: grab the GUID from the prefab's `.meta`,
   `search` it across `*.unity` and `*.prefab`. Each hit is a script holding
   a spawn ref.
4. **Script class GUID → host scene**: `search` the script's class GUID
   across `*.unity` to find which scene instantiates the component. That
   scene name becomes the spawn row's `scene`.

Group orphans by host script. Each group is one listener.

## Step 4 — Add the listener

Per `skill://unity-export-system`, add a listener under
`src/Assets/Editor/ExportSystem/AssetScanner/Listener/` and register it in
`ExportBatch.cs`. The listener emits to `character_spawns` with:

- `character_stable_key` from `StableKeyGenerator.ForCharacter(prefab)` —
  must equal an existing row in `characters` or the export will silently
  drop the link.
- `(scene, x, y, z)` from the host MonoBehaviour's transform.
- `is_directly_placed = 0`, `is_trigger_spawn = 1`,
  `spawn_point_stable_key = NULL`.
- `zone_stable_key` resolved from the host's scene via the existing
  zone-by-scene index used by `SpawnPointListener`.

When 5+ near-identical listeners would be needed, prefer one
**generic `DynamicSpawnSourceListener`** that walks every MonoBehaviour by
reflection, reads each serialized `Character` / `GameObject` field, and
emits a row when the field's GameObject has a `Character` component. Trade
explicitness for breadth.

## Step 5 — Re-run, diff, ship

```bash
uv run erenshor -V {v} extract export
uv run erenshor -V {v} extract build
# Re-run Step 1's SQL — the orphan count must drop by the number of
# orphans the new listener was meant to cover. If it didn't:
#   - listener isn't registered in ExportBatch.cs
#   - StableKeyGenerator output doesn't match characters.stable_key
#   - host scene wasn't included in the scan
```

Refuse to ship sheets/wiki/map (`skill://refreshing-game-data` step 5) until
either the orphan count is at the documented baseline **or** every newly
orphaned character has a Step 4 entry in this patch's worktree.

## Non-orphan look-alikes — do not export

- **Runtime-rebound trackers**: `RewardListener.Frost/Inferno`,
  `FaithEvent.Faith`, `ShiveringPhantomWardListener.ward1/2`. Fields are
  reassigned at runtime from `MySpawn.SpawnedNPC`; the host SpawnPoint
  already covers them.
- **`bkp` / `_dupe` prefab names**: intentional duplicates referenced only
  by event scripts. Once the matching listener runs they are no longer
  orphaned; do not add a separate spawn row for the "real" version.
- **`TOWNSPERSON` templates**: inspector-time placeholders for the
  `SimPlayerMngr` system. Filter these out at Step 1, do not export.

## See also

- `skill://refreshing-game-data` — calls this skill at the validate gate.
- `skill://unity-export-system` — listener / record / `StableKeyGenerator`
  boilerplate.
- Working notes from the 2026-05-28 playtest audit:
  `docs/plans/2026-05-28-spawn-coverage-audit.md` — full orphan-by-script
  mapping, plus the script taxonomy used to build this skill.
