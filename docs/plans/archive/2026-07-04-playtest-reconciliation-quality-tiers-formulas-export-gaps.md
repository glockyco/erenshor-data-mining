---
title: "Playtest Reconciliation: Quality Tiers, Formulas & Export Gaps"
type: spec
status: implemented
created: 2026-07-04
archived: 2026-07-05
---

# Playtest Reconciliation: Quality Tiers, Formulas & Export Gaps

Reconcile the export pipeline with the playtest game build's new item quality
tier naming, stat-calculation method split, and the gameplay-relevant fields
identified as missing from the export surface by the 2026-07-04 main-vs-playtest
script audit.

## Background

The audit
(`docs/plans/archive/2026-07-04-main-vs-playtest-script-audit.md` and
`docs/plans/archive/2026-07-04-export-gap-analysis.md`) compared all decompiled C#
scripts between the main and playtest builds. It found formula changes, new
fields, and a quality-tier rename that all affect the data exports (wiki,
sheets, map, AdventureGuide).

## 1. Quality Tier Rename

The developer confirmed the official quality tier names:

- Quality 1: **Normal** (unchanged)
- Quality 2: **Blessed** (unchanged)
- Quality 3: **Ascended** (was "Godly")
- Qualities 11–15: **Improved +1 through +5** (new, forged items)

"Godly" must be renamed to "Ascended" consistently across C#, Python, SQL, and
Lua. Quality tiers 4–10 do not exist in the game — the calc methods return
base stats for those values, and no rows should be produced for them.
Qualities 11–15 are produced by the smithing combine path (template `2265228`),
but they use the same `CalcStat`/`CalcResists`/`CalcAC`/`CalcACHPMC` methods
as the other tiers. The export must produce `ItemStatsRecord` rows for them,
just as it does for Normal/Blessed/Ascended, and the wiki must display them
in item stat tables.

### Affected locations

| File | Change |
|---|---|
| `src/Assets/Editor/ExportSystem/AssetScanner/Listener/ItemListener.cs:293` | `"Godly"` → `"Ascended"` |
| `src/Assets/Editor/Database/ItemStatsRecord.cs:14` | Comment: `"Godly"` → `"Ascended"` |
| `src/erenshor/shared/game_constants.py` | `TIER_ORDER_MAP`, `TIER_STRING_MAP`, `REQUIRED_TIER_COUNT` docstring: `"Godly"` → `"Ascended"` |
| `src/erenshor/domain/entities/item_stats.py:16,24` | Docstrings |
| `src/erenshor/domain/entities/__init__.py:9` | Docstring |
| `src/erenshor/domain/enriched_data/item.py:36` | Docstring |
| `src/erenshor/infrastructure/database/repositories/items.py:150,189-190` | SQL CASE: `'Godly'` → `'Ascended'` |
| `src/erenshor/application/sheets/queries/items.sql:96-97` | `'Godly'` → `'Ascended'` |
| `src/erenshor/application/wiki_lua/items.py:398` | `_summary_stat` filter is `{"Normal", "0"}` — no change needed (Normal stays) |
| `wiki/modules/Erenshor/Item/Tooltip.lua:30` | `QUALITY_RANK`: `Godly = 2` → `Ascended = 2` |
| `wiki/modules/Erenshor/Item/Tooltip.lua:17` | Comment: `"Godly"` → `"Ascended"` |
| `wiki/modules/Erenshor/Item.lua:264` | `normalStats` filter: `quality == "Normal"` — no change needed |

### Quality tiers 11–15 in the export loop

`CreateItemStatsRecords()` currently loops `quality = 1` through `maxQuality`
(where `maxQuality = 3` for equippable items). This must change to produce
rows for qualities 1, 2, 3, **and** 11, 12, 13, 14, 15 — skipping 4–10
(which don't exist in the game). The quality string map must include:

```csharp
Quality = quality switch
{
    1 => "Normal",
    2 => "Blessed",
    3 => "Ascended",
    11 => "Improved +1",
    12 => "Improved +2",
    13 => "Improved +3",
    14 => "Improved +4",
    15 => "Improved +5",
    _ => quality.ToString()
},
```

The loop should iterate over an explicit list: `int[] { 1, 2, 3, 11, 12, 13, 14, 15 }`
instead of a contiguous range.

### Tests

- `tests/unit/application/wiki_lua/test_items_module.py` — update any fixture asserting `"Godly"`.
- `tests/unit/infrastructure/database/repositories/test_items.py` — update tier-order assertions.
- `tests/golden/` — regenerate after export (quality strings in CSV output change).

## 2. Item Stat Calculation Method Fix

`ItemListener.CreateItemStatsRecords()` calls the game DLL's own calc methods
to pre-compute quality-scaled stats. The playtest `Item.cs` split the formula
into separate methods for resists and AC. The listener must call the new
methods.

### Affected locations

| File | Current call | New call | Stats affected |
|---|---|---|---|
| `ItemListener.cs:300` | `item.CalcACHPMC(item.AC, quality)` | `item.CalcAC(item.AC, quality)` | AC |
| `ItemListener.cs:310` | `item.CalcStat(item.MR, quality)` | `item.CalcResists(item.MR, quality)` | Magic Resist |
| `ItemListener.cs:311` | `item.CalcStat(item.ER, quality)` | `item.CalcResists(item.ER, quality)` | Elemental Resist |
| `ItemListener.cs:312` | `item.CalcStat(item.PR, quality)` | `item.CalcResists(item.PR, quality)` | Poison Resist |
| `ItemListener.cs:313` | `item.CalcStat(item.VR, quality)` | `item.CalcResists(item.VR, quality)` | Void Resist |

`Res` (Resonance) stays on `CalcStat` — it is not a resist. HP and Mana stay
on `CalcACHPMC`. `WeaponDmg` stays on `CalcDmg`. These methods don't exist on
the main DLL, but we only target playtest.

No architecture change. The export already calls the game's own methods at
export time — formula changes are picked up automatically on re-export. This
is just calling the right methods.

### Tests

- No unit test directly — the calc methods run inside Unity. Verify via export + golden comparison.

## 3. New Missing Fields

### 3.1 Spell: `SimsNeedHelpToLearn` (bool)

Currently ignored as "spell AI/runtime hint." This is player-facing: SimPlayers
only auto-learn spells when `!SimsNeedHelpToLearn || MyAcquiredSpells.Contains(spell)`.
Item tooltips warn players. 18 playtest spell assets have it set to `true`.

**Pipeline:** `SpellRecord.cs` (add column) → `SpellListener.cs` (capture) →
`writer.py` (clean schema) → `domain/entities/spell.py` (field) →
`wiki_lua/spells.py` (`_BOOL_FIELD_MAP`) → `sheets/queries/spells.sql` (column) →
`wiki/templates/Spell.wiki` + `wiki/modules/Erenshor/Spell.lua` (Cargo fields)
→ `field-coverage.json` (status: captured).

### 3.2 NPC gameplay fields (8 high-priority bool/float/spell-ref fields)

These are public serialized fields on `NPC.cs` (a MonoBehaviour), captured
through the `CharacterListener` which reads the `NPC` component. The manifest
does not track `NPC` as a separate type — it must be added (see §4).

| Field | Type | Prefabs with non-default | Why |
|---|---|---|---|
| `NeverAggro` | bool | 14 | Skips all nav/behavior/threat loops. Hard threat blocker. |
| `NoDmgCap` | bool | 103 | Bypasses `Level * 15 * ServerDMGMod` physical damage cap. |
| `CanPhantomStrike` | bool | 41 | 33% chance to splash-hit a random nearby enemy at 30% BaseAtkDmg. |
| `Enrage` | float | 17 | Encounter enrage timer. |
| `SpawnWithStatus` | Spell ref | Non-null on 2+ prefabs | NPC spawns with pre-applied buff. Capture as spell stable key. |
| `NoSelfHeal` | bool | Non-default on Sapling | Disables self-heal at low HP. |
| `AggroRegardlessofLOS` | bool | 12 | Aggro acquisition ORs with LOS check result. |
| `IgnoreLOSForAggro` | bool | 8 | `CheckLOS()` short-circuits to `true`. Skips raycast entirely. |

**Pipeline:** `CharacterRecord.cs` (add columns) → `CharacterListener.cs` (capture
from `npc.` component) → `writer.py` (characters schema) → `characters.py`
(`_char_row` mapping) → `wiki_lua/characters.py` (`_CHARACTER_FIELD_MAP`) →
`sheets/queries/characters.sql` (columns) → `wiki/templates/Character.wiki` +
`wiki/modules/Erenshor/Character.lua` (Cargo fields).

For `SpawnWithStatus` (Spell ref): capture as `spawn_with_status_stable_key`
foreign key, same pattern as existing `PetSpellStableKey`.

### 3.3 NPC medium-priority fields (5 fields)

| Field | Type | Why |
|---|---|---|
| `GroupHOTSpell` | Spell ref | Raid group HOT spell. Capture as stable key. |
| `MyEmitVitaeSpell` | Spell ref | Emit vitae spell. Capture as stable key. |
| `MyHOTSpell` | Spell ref | Single-target HOT. Already not captured. |
| `AETaunt` | Spell ref | AE taunt spell. Already not captured. |
| `SimPlayersIgnoreUntilOrdered` | bool | Raid sim waits for orders. |

Same pipeline as §3.2. Lower priority — no non-default prefab values found
for the spell refs, but the behavior is real when set.

### 3.4 Stats fields (3 fields)

Public serialized fields on `Stats.cs`, captured through `CharacterListener`
which reads the `Stats` component.

| Field | Type | Prefabs with non-default | Why |
|---|---|---|---|
| `BaseArmorPenPercentage` | int | 8 (Opus=60, Jinx=20) | Base armor penetration. Affects physical mitigation. |
| `BaseAttackRollModifier` | int | 4 (God Brax=3, Vitheo=2) | Base attack roll modifier. Affects hit chance. |
| `CannotBeSnared` | bool | 33 | Snare/root immunity. |

**Pipeline:** Same as §3.2 — add to `CharacterRecord.cs`, `CharacterListener.cs`
(read from `stats.` component), `writer.py`, `characters.py`, wiki/sheets/Cargo.

### 3.5 Zone fields (2 fields)

| Field | Type | Zones with non-default | Why |
|---|---|---|---|
| `RaidCapable` | bool | 5 (PlaneOfVitheo, PlaneOfSoluna, Reliquary, PlaneOfBrax, PlaneOfFernalla) | Non-raid zones end active raids. |
| `UseZoneAsTempBind` | string | 4 (same planar zones) | Death redirects respawn to Reliquary. |

**Pipeline:** `ZoneRecord.cs` (add columns) → `ZoneAnnounceListener.cs` (capture) →
`writer.py` (zones schema) → `wiki_lua/zones.py` (field map) →
`sheets/queries/zones.sql` (columns) → `field-coverage.json` (status: captured,
update ignore reasons).

## 4. Field-Coverage Manifest Expansion

Add `NPC` and `Stats` as tracked types in `field-coverage.json`. Without them,
future field additions on these MonoBehaviours are invisible to the coverage gate.

For each new type, enumerate all public fields, classifying each as `captured`
or `ignored` with a valid reason. The `CharacterListener` already captures many
NPC and Stats fields — those are `captured`. Visual/audio/animation/runtime
fields are `ignored`.

## 5. Wiki Tooltip: Improved Quality Tiers

The `Tooltip.lua` `QUALITY_RANK` and `SPARKLE` tables currently only recognise
`Normal=0`, `Blessed=1`, `Ascended=2` (after rename). Now that the export
produces stat rows for qualities 11–15, the tooltip must handle them:

- `QUALITY_RANK`: add entries for `Improved +1` through `Improved +5` (rank 3)
- `SPARKLE`: add `[3] = { file = "Green_Sparkle.gif", size = "80px" }`
- The quality label display should show the quality string ("Improved +N")
  for tiers >10
- The item tooltip should render one quality block per stat row, same as
  it already does for Normal/Blessed/Ascended

## 6. What Is NOT Changing

- **Architecture:** No change. The export calls the game's own calc methods at
  export time. Quality tiers are data-driven. Cargo stores Normal-quality base
  stats for querying; per-quality display comes from the Lua data module.
- **Quality tiers 4–10:** Do not exist in the game. The calc methods return
  base stats for these values. The export must not produce rows for them.
- **Low-priority NPC fields:** `HoldDPS`, `ChestDurability` — leave ignored.
  `HoldDPS` has no non-default prefabs. `ChestDurability` is runtime-randomized.
- **`HardcodedUseCase`, `ForHardEncounters` on Spell:** Leave ignored as
  AI/runtime hints. Not player-facing data.
- **Dynamic spawn coverage:** No new gaps beyond the deferred Category C
  (Sivakayan Spectres).

## 7. Verification

1. Run `uv run pytest` — all tests pass with updated fixtures.
2. Run `uv run erenshor -V playtest extract export` → `code-facts` → `build` —
   export succeeds, new fields appear in clean DB with correct values.
3. Run `uv run erenshor golden capture` — review diff: quality strings change
   (Godly → Ascended), AC/resist values change (new formulas), new Improved
   stat rows appear, new columns appear.
4. Run `uv run pytest` again — golden tests pass with regenerated baselines.
5. Run `uv run omp-plans check` — planning docs valid.
