---
title: Spawn Coverage Audit — Method & Findings
type: audit
status: implemented
created: 2026-05-28
parent:
archived: 2026-06-28
---

# Spawn Coverage Audit — Method & Findings

**Variant:** playtes
**Date:** 2026-05-28
**Trigger:** Confirming whether characters lacking `character_spawns` rows are
truly dead data or are placed in the world by code paths the export pipeline
doesn't yet observe.

## Why This Audit Exists

The export pipeline scans `SpawnPoint` (and `SpawnPointTrigger`) components and
emits one row per (character × spawn point) into `character_spawns`. Anything
spawned by other means — fight-event scripts, trigger volumes, zone-tick
random spawners, scripted ward replacements, chess pieces, scripted boss
fawns — is invisible to those listeners. The affected characters look
"unplaced" on wiki/map even though they appear in-game.

When the game updates, new event scripts (or new prefab fields on existing
ones) appear and silently widen the gap. This audit is the workflow for
detecting and closing it.

## Findings (playtest, 2026-05-28)

| Bucket | Count | Status |
|---|---:|---|
| Total characters in `characters` | 1202 | — |
| Have ≥1 `character_spawns` row | 1002 | covered |
| No spawn row, but a dedup sibling has one | 55 | covered via dedup |
| No spawn row, no covering dedup sibling | **145** | **orphan** |
| └─ Of which: summoned by a spell (`spells.pet_to_summon_stable_key`) | 13 | reachable via spell join — not really "missing" |
| └─ Of which: need a new MonoBehaviour listener to surface | **132** | **export gap** |

The full orphan list is at `playtest-no-spawn.tsv` (repo root, untracked).

The 132 export-gap orphans are concentrated in **~20 MonoBehaviour types**
that hold serialized prefab references (`GameObject` or `Character` fields)
and `Object.Instantiate` them at runtime. One listener per host type closes
multiple orphans at once.

## Spawn-source taxonomy

| Pathway | Already exported? | Listener / table |
|---|---|---|
| `SpawnPoint.PossibleChars` | yes | `SpawnPointListener` → `character_spawns` |
| `SpawnPointTrigger.Spawnables` + `Alt` | yes | `SpawnPointTriggerListener` → `character_spawns` (is_trigger_spawn=1) |
| `Character.SpawnOnDeath` | no | new (post-death replacement; map node already exists) |
| `NPCDialog.Spawn` | no | new (NPC summons during dialog) |
| `Spell.pet_to_summon_stable_key` | yes (via spell-character join) | `spells` table — but no `character_spawns` row, by design |
| `Misc.SivakayanSpectres[]` (referenced by `ZoneAnnounce.SpawnSivakayanSpecter`) | no | new (random per-scene tick spawn) |
| Event-script `GameObject`/`Character` fields | no | new (one listener per script type, or one generic) |

The event-script category contains the bulk of the gap. The scripts found in
playtest (with the orphan(s) they expose):

| Script | Spawn fields | Example orphans |
|---|---|---|
| `Chessboard` | `PeonNPC`, `EmberNPC`, `BlazeNPC`, `MonarchNPC`, `KingsmanNPC`, `CandlekeeperNPC`, `FacelessDuel/Arc/Pal/Dru/Storm/Reaver` | Peon, Ember Acolyte, Blazefiend, Monarch of the Flame, Kingsman, Candlekeeper, six Faceless |
| `Constellation` | `Spawns[]` | the 5 `Constellation*` / `Forming Constellation*` |
| `FaithEvent` | `HealObject` (Faith itself comes from `MySpawn.SpawnedNPC`) | Faith |
| `GraceEvent` | `AnimDupe` | Echo of Grace |
| `MizukiEvent` | `MizChar`, `Remnants[]`, `FinalPush[]`, `DoubleSpawn` | Fiery Remnant, Icy Remnant |
| `AstraListener` | `Dragon`, `Beam` | Astra, Rogue of the Stars |
| `PhantomFightEvent` | `WardsToSpawn` | Ward of the Forest |
| `FernallaFightEvent` | `FinalFernalla`, `FawnToSpawn`, `Phase2Ward`, `Phase2Assault` | Fallen Fernalla, Fernallan High Guard, Fernallan High Priest, Fernallan Planar Guard |
| `FernallaPortalEvent` | `Arcanist`, `Knight`, `Hound`, `Invader` | Fernalla-portal raid adds |
| `FernallaPortalBoss` | `Ward1/2/3` | Fernalla portal wards |
| `SiraetheEvent` | `WardSpawnable` | Ward of Siraethe |
| `SprinklesEvent` | `Sprinkles`, `ForestWard` | Ward of the Forest |
| `StowawayPortal` | `Keeper`, `Skeletons[]`, `KeeperSac` | A Skeleton Captain, sacrifice mobs |
| `TreasureChestEvent` | `Guardians[]` | Vithean Chest, Lost Treasure guardians |
| `VithArena` | `_npc[]`, `AwardChests` | Vithean Executioner, Honsus, Expert Gladiator |
| `WaveEvent` | `WeakWave[]`, `StrongWave[]`, `StrongestWave[]`, `BossMob` | wave/boss enemies |
| `ZenithNadirScript` | `Zenith`, `Nadir`, `Syzygy`, `ConstellationStar` | Syzygy, constellation stars |
| `ZoneAnnounce.SpawnSivakayanSpecter` (reads `Misc.SivakayanSpectres`) | — | Sivakayan Voidmaster, High Shadow, Doomshade, Shadow, Shrouded Sivakayan |
| `HonsusScript` | `AddToSpawn` | Honsus-zone adds |
| `MalarothFeed` | `_npc` argument | Demented Malaroth |
| `NPCFightEvent` | `obj`, `spawnAdd`, `SpawnOnDeath` | scripted fight adds |
| `NPCDialog` | `Spawn` | (TBD: per-dialog adds) |
| `ShiveringPhantomWardListener` | `ward1`, `ward2` | (runtime-rebound; same as FaithEvent pattern) |
| `RewardListener` | `Frost`, `Inferno` (runtime-rebound) | (no new orphan; just a tracker) |

`NPCSpawnEnvDmg.DmgToSpawn`, `FernallaFightEvent.Phase2Assault`,
`Phase2Ward` etc. resolve to damage-area objects, not Characters — verify
the prefab has a `Character` component before emitting a row.

## Audit workflow (do this after every Steam update)

### Step 1 — Pull the orphan lis

Run against `variants/{v}/erenshor-{v}.sqlite`:

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

Diff the count against the previous run. New orphans = new event scripts or
new prefab fields on old ones.

### Step 2 — Enumerate dynamic-spawn pathways

Read-only reference: `variants/{v}/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/`.
Roslyn is loaded against this tree — use `lsp` for navigation.

```
# Serialized prefab fields on MonoBehaviours
search '^\s*public\s+Character\s+\w+\s*;'                  → 33 files
search '^\s*public\s+(Character\[\]|List<Character>)\s+\w+\s*[;=]'
search '^\s*public\s+(GameObject|GameObject\[\]|List<GameObject>)\s+\w+\s*[;=]'

# Runtime instantiation sites
search 'Instantiate\s*\('                                  → 60 files
```

For each newly-appearing script: read it, list serialized `Character`/
`GameObject` fields, and confirm via `Object.Instantiate(<field>, …)` tha
the field is a spawn source (vs. UI/FX/projectile prefab). If the
`Instantiate` target chains `.GetComponent<Character>()` or
`.GetComponent<NPC>()`, it is a character spawn.

### Step 3 — Map orphans to scripts

Tools per orphan (in priority order):

1. **DB joins first**: `spells.pet_to_summon_stable_key`,
   `character_spawns.protector_stable_key`,
   `character_spawns.spawn_upon_quest_complete_stable_key`,
   `character_deduplications.group_key`. Anything reachable here is not a
   real gap.
2. **Stable-key → prefab name**: a stable key like
   `character:summoned dire wolf` is the prefab's lowercased `object_name`.
   The prefab lives at `variants/{v}/unity/.../Assets/**/<object_name>.prefab`
   (use `find`).
3. **Prefab GUID → scene/prefab referrers**: open the prefab, grab the GUID
   from its `.meta`, `search` the GUID across `*.unity` scenes and other
   `*.prefab` files. The referrers are the MonoBehaviours that hold spawn
   refs to that prefab.
4. **MonoBehaviour script → host scene**: open the script in the editor or
   `search` for the script's class GUID across `*.unity` to find which
   scene(s) instantiate the component. That scene's name is the spawn
   location's `scene`.

Group orphans by host script. Each group is one listener.

### Step 4 — Add listener(s)

For each unique script type with ≥1 orphan, add a listener under
`src/Assets/Editor/ExportSystem/AssetScanner/Listener/`. The listener:

- Implements `IAssetScanListener<TScript>` (or `IAssetScanListener<GameObject>`
  with a runtime cast if the host is a scene object only).
- Reads each serialized `Character`/`GameObject` field, casts to `Character`,
  resolves the prefab's `stable_key` via `StableKeyGenerator.ForCharacter`.
- Writes one `character_spawns` row per (host scene × transform × prefab),
  with `is_trigger_spawn = 1`, `is_directly_placed = 0`,
  `spawn_point_stable_key = NULL`, and `zone_stable_key` derived from the
  host's scene.
- Register in `ExportBatch.cs` via the appropriate
  `scanner.RegisterComponentListener(…)`. See `skill://unity-export-system`.

Common-case shortcut: a single `DynamicSpawnSourceListener` that walks every
MonoBehaviour, reads every serialized `Character`/`GameObject` field by
reflection, and emits a row when the field's GameObject has a `Character`
component. This avoids one listener per event script at the cost of being
less explicit. Use this when the alternative is >5 near-identical listeners.

### Step 5 — Re-run, diff, ship

```bash
uv run erenshor -V {v} extract expor
uv run erenshor -V {v} extract build
# Re-run Step 1's SQL → orphan count must drop by the number of new pathway hits.
```

If the count didn't move, the listener isn't registered, the
`StableKeyGenerator` is producing keys that don't match `characters.stable_key`,
or the host scene isn't being scanned. Verify in order.

## Non-goals / known dead data

- **Pure runtime trackers** (`RewardListener.Frost/Inferno`, `FaithEvent.Faith`,
  `ShiveringPhantomWardListener.ward1/2`): these fields are reassigned a
  runtime from `MySpawn.SpawnedNPC` etc. and do not represent a new spawn —
  the host SpawnPoint already covers them.
- **`bkp` / `_dupe` prefab names** (`fernalla planar guard bkp`,
  `animation of grace dupe`, etc.): these are intentional duplicates referenced
  only by event scripts, not free-standing world placements. Their orphan
  status disappears once the matching event-script listener runs.
- **Townsperson templates** (`character:ch…`, two `character:sm…`,
  `display_name='TOWNSPERSON'`): inspector-time placeholders for the
  `SimPlayerMngr` system; they are never instantiated as world Characters and
  should be filtered out of orphan reports rather than exported.

## Open questions for follow-up

- Does the deduplication system already collapse some bkp/dupe prefabs a
  Python-build time? If so, those orphans should be added to dedup groups in
  `mapping.json` instead of getting their own spawn rows. Check the
  `character_deduplications` builder.
- The Sivakayan spectre random spawner (`ZoneAnnounce.SpawnSivakayanSpecter`)
  fires once per scene per tick under low odds. Modeling this as a per-zone
  "may appear" relationship may make more sense than emitting one
  `character_spawns` row per SpawnPoint × spectre prefab.
