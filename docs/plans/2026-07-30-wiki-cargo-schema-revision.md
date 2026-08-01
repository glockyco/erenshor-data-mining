---
title: Cargo Schema Revision
type: spec
status: draft
created: 2026-07-30
parent: 2026-06-04-wiki-cargo-data-architecture
---

# Cargo Schema Revision

**Goal:** Fix the structural defects in the Cargo schema and the Lua data-module
layout before the tables are created on production. None of the ten designed tables
has ever existed on live (`2026-07-30-wiki-cutover-state-audit`), so every change
below is free today and expensive later: after first creation a schema change costs a
`cargorecreatetables` plus a manual replacement-table switch-in that only a sysop can
perform, and new fields stay invisible to queries until that switch.

**Scope:** the `{{#cargo_declare:}}` blocks in `wiki/templates/`, the generated Lua
data modules under `variants/{variant}/wiki/lua/Erenshor/Data/`, and the generators
in `src/erenshor/application/wiki_lua/`. Rendering parity is tracked separately.

## Non-issues, settled

Three suspected problems are not real. Recorded so they are not re-litigated.

- **No reserved-word collisions.** All roughly 175 declared column names avoid both
  Cargo's static `$sqlReservedWords` list in `CargoDeclare.php` and the current
  MariaDB and MySQL reserved lists. `End` on `Items` is **not** reserved in either
  database and is absent from Cargo's list, and Cargo quotes every identifier through
  `addIdentifierQuotes()` in `CargoUtils.php` when building DDL. The two historical
  traps, `Range` and `Character`, are on Cargo's list and were already renamed. Only
  near-misses remain: `Line` against `LINES` and `LINEAR`, and `End` against the
  compound-statement `END` token.
- **Lua memory is not the binding constraint.** Live ceilings are 52,428,800 bytes
  and 15.000 seconds. The heaviest real page, the armor overview, resolves 577
  `ItemLink`, 2,414 `ClassLink`, and 155 `AbilityLink` invocations and measures
  10,044,840 bytes and 0.847 seconds, so 19 percent of the memory ceiling with 5.2x
  headroom. `mw.loadData` evaluates a module once per page and shares it across every
  `#invoke`, so a page rendering hundreds of links pays for each module once.
  **`maxarticlesize` at 4,194,304 bytes is the real limit.**
- **List fields are not corrupting data.** No class or zone display name contains a
  comma, so `Items.Classes` and `Characters.Zones` are intact. They remain
  structurally delimiter-fragile and each costs a Cargo helper table.

## Defects

### 1. `Data/Characters` cannot deploy, and the cause is dead payload

The module is 5,099,976 bytes against a 4,194,304-byte limit, roughly 4 KB per
character across 1,254 characters. Sharding is the obvious fix and the wrong first
move, because much of the payload is unread.

`Character.lua` `ROOT_PUBLIC_PARAMETERS` never reads the generated `spawns` or
`abilities` arrays. They exist only to feed the Cargo store path. Separately,
`coordinates`, `spawnChance`, `spawnType`, and `respawn` duplicate what `Spawns`
holds, `dropRates` duplicates `ObtainedFrom`, and `spells` duplicates
`CharacterAbilities`. Section 8.1 of the design spec states that denormalized reverse
arrays were removed in favour of reverse queries. For characters they were not.

Cut the payload first, measure, then shard only if still needed.

### 2. Kind-based shards drift toward the limit

`Data/Items/Armor` is 3,608,766 bytes for 577 armor items, so 6,256 bytes per entity
with 585,538 bytes of headroom. **That is about 94 more armor items before it
breaches.** One content patch can do that. `Weapons` is 6,076 bytes per entity with
roughly 474 items of headroom. Every other shard has thousands.

Sharding by kind ties shard size to content-patch composition, and a breach forces a
reshuffle that reassigns entities and therefore redeploys everything.

| Shard | Entities | Bytes | Headroom |
|---|---|---|---|
| `Items/Armor` | 577 | 3,608,766 | 585,538 |
| `Items/Weapons` | 216 | 1,312,337 | 2,881,967 |
| `Items/General` | 415 | 947,468 | 3,246,836 |
| `Items/SpellScrolls` | 158 | 312,306 | 3,881,998 |
| `Items/Charms` | 25 | 153,656 | 4,040,648 |
| `Items/Consumables` | 33 | 130,142 | 4,064,162 |
| `Items/SkillBooks` | 49 | 97,993 | 4,096,311 |
| `Items/Auras` | 44 | 83,656 | 4,110,648 |
| `Items/Molds` | 20 | 47,007 | 4,147,297 |
| `Data/Links` | — | 1,625,494 | 2,568,810 |
| `Data/Spells` | 348 | 861,936 | 3,332,368 |
| `Data/Characters` | 1,254 | 5,099,976 | **-905,672** |

### 3. `Items` is missing the auction-house flag entirely

Section 7.1 specifies `IsAuctionable` as a derived Boolean and section 8 makes it the
*sole* representation of auction availability, deliberately not an `ObtainedFrom`
row. The declaration has no such column, so the auction house cannot render at all.
The spec also names `IsRare` while the declaration carries `RareItem`.

### 4. Fourteen of `Items`' forty-six columns model one concept

Nine scalar stable-key columns, three chance columns, and two derived flags all
express "this item carries this ability in this role". Sparsity over 1,537 items:

| Column | Items set | Share |
|---|---|---|
| `TeachesSpellKey` | 158 | 10.3% |
| `WeaponProcKey` | 130 | 8.5% |
| `WornEffectKey` | 108 | 7.0% |
| `ClickEffectKey` | 80 | 5.2% |
| `TeachesSkillKey` | 49 | 3.2% |
| `AuraKey` | 44 | 2.9% |
| `WandEffectKey` | 20 | 1.3% |
| `BowEffectKey` | 13 | 0.8% |
| `SkillUseKey` | 1 | 0.07% |

Total populated relations: 603. Cargo materializes a physical column per field for
every row, so this is 14 columns and 21,518 cells to express 603 facts.

The cost is not storage, it is the reverse query. Cargo has no `UNION`, so "which
items grant or proc this ability" needs **nine separate queries plus a Lua merge**.
That lookup is not implemented on the wiki side at all today. The equivalent question
in Python is a single `OR` query in `repositories/items.py`.

The design spec justifies the scalars because `Item.cs` exposes each as an individual
reference. That is true of the game model and irrelevant to the storage model. The
project already chose typed junctions for exactly this shape in `ObtainedFrom` and
`UsedIn`, for exactly the no-`UNION` reason.

### 5. Derived flags are an incomplete, undocumented facet set

`Items.HasProc` and `HasWornEffect` are computed in `Item.lua` from
`weaponProc or procEffect` and `wornEffect`. `Characters.HasDrops` and `HasSpells`
are computed in `characters.py` from formatted relationship arrays. None is a game
field. There is no `HasClickEffect`, `HasAura`, `HasTeachSpell`, `HasWandEffect`,
`HasBowEffect`, `HasSkillUse`, `HasAbilities`, or `HasSpawns`, so the set answers
some boolean facets and not others for no stated reason. The source columns are
directly queryable, which makes the flags pure denormalization that can stale.

### 6. `classes` has no stable key, so one `SourceKey` value cannot be one

`classes` is keyed `class_name TEXT PRIMARY KEY`. Section 8 documents
`ObtainedFrom.SourceKey` as a ClassLink target for `SourceType='starting'`, which is
37 rows. Section 2.1 states that every column whose value is an entity StableKey is
suffixed `Key`. Those rules conflict: `SourceKey` would hold a bare class name for
exactly one source type. Every other source type resolves to a prefixed key —
`item:`, `character:`, `quest:`, `mining:`, `water:`, `itembag:`, `forge:` — which is
what makes the polymorphic column self-describing.

### 7. `CharacterFactionModifiers` is missing and already has a consumer

`character_faction_modifiers` holds 1,387 rows across 533 characters, is exported
through `CharacterFactionModifierRecord.cs`, and the Character template already
renders a "Faction Changes on Kill" section fed by `character.py`. Cargo carries only
the scalar `Characters.FactionKey`. The combat `Faction` enum stays name-only and
correctly gets no junction.

### 8. `Characters` has no `Image` column

`Items`, `Spells`, `Skills`, and `Stances` all declare `Image` as `File`. Nothing in
the spec justifies the omission.

### 9. Declaration and prose have drifted five ways

| Table | Declared but undocumented | Documented but undeclared |
|---|---|---|
| `Spawns` | `EventX`, `EventY`, `EventZ` | — |
| `Characters` | `MapSelector` | `Image` |
| `Spells` | `ArmorPenPercent`, `LevelScaledManaRestoration` | — |
| `Skills` | `SkillCanCrit` | — |
| `Items` | `HasProc`, `HasWornEffect` | `IsAuctionable`, `IsRare` |

`ClassLinks` is correctly absent, matching the instruction to drop it.

### 10. Two type declarations are inconsistent with their siblings

Measured against the clean DB:

| Column | Declared | Observed | Verdict |
|---|---|---|---|
| `Spells.DurationSeconds` | Integer | 0 to 1000, no fractions | Inconsistent with `CastTimeSeconds` as Float. Both derive from ticks, so a duration that is not a whole multiple of 60 ticks would be rejected. |
| `Spells.CastRange` | Float | 0 to 99999, no fractions | Float unjustified by data. |
| `Items.Delay` | Float | 111 fractional | Correct. |
| `Skills.PercentDmg` | Float | fractional | Correct. |
| `Spells.LevelScaledManaRestoration` | Float | 2 fractional | Correct. |
| `Spawns.X`, `Y`, `Z` | Float | roughly 9,000 fractional each | Correct. |
| `Spawns.SpawnChance` | Float | 3,649 fractional | Correct. |
| `Characters.Enrage`, `Spawns.LevelMod`, `Spawns.RareNpcChance` | Float | integral this build | Defensible as future-proofing a game float. |

Every declared Integer column maps to a SQLite INTEGER source, so no other Integer
carries a fractional-rejection risk.

### 11. The `Items` declaration lives inside a 500-transclusion template

wiki.gg's Cargo guide instructs segregating declarations into their own
low-transclusion template, because editing a transcluded declaration enqueues a job
for every transcluding page and can interfere with an in-flight recreation. `Items`
is declared inside `Template:Item`, which has more than 500 main-namespace
transclusions.

Worse, `wiki/templates/Item/CargoDeclare.wiki` contains a `<noinclude><pre>` copy of
the same schema. It never fires, so it is a second definition that can silently drift
from the real one. `Character/CargoDeclare.wiki` has the same problem.
`Template:AbilityClasses` is already correctly declare-only.

### 12. Two pages would store more than 170 rows each

Recreate runs one job per contributing page and rows are written at parse time.

| Table | Rows | Pages | Max per page | p95 |
|---|---|---|---|---|
| `Spawns` | 8,955 | 856 | 173 (`Molorai Truthseeker`) | 45 |
| `ObtainedFrom` | 6,947 | 1,441 | 187 (`Star Stone`) | 14 |
| `CharacterAbilities` | 1,043 | 281 | 68 | 8 |
| `AbilityClasses` | 344 | 264 | 6 | 4 |
| `UsedIn` | 325 | 242 | 6 | 3 |
| `Items` | 1,537 | 1,508 | 22 | — |
| `Characters` | 1,254 | 875 | 160 | 3 |

`ObtainedFrom` by source type: drop 5,111, vendor 662, mining 510, fishing 437, quest
99, starting 37, item_bag 32, dialog 24, craft 23, item_use 12. `UsedIn` by use type:
quest_requirement 246, craft_material 76, upgrade_material 2,
blessing_removal_material 1. `Spawns` is the 8,832-row wiki view plus 123
treasure-chest rows. `AbilityClasses` is 260 spell plus 84 skill memberships.

Other `Spawns` outliers: `Rottenfoot Swampwalker` 164, `A Brittle Skeleton` 137,
`A Wisp` 128, `Molorai Outrider` 126. Other `ObtainedFrom` outliers: `Luminstone`
159, `Water` 124, `Citrine Stone` 124, `Rock` 111, `Ancient Coal` 110.

These are within Lua limits but they are the pages to watch during a recreate.

### 13. Cargo cannot become the record, confirmed

Moving own-entity fields into Cargo and having the infobox self-query is not viable.
Cargo writes rows on page parse, so a page querying the row it stores during the same
parse reads the previous parse's row or nothing. Both the official Cargo storing
documentation and section 10 of the design spec state the ordering rule. This settles
the architecture: **the Lua data module stays the record.**

## Recommendations

1. **Strip dead payload from the character record, then measure.** Remove the
   `spawns` and `abilities` arrays, which no renderer reads, and the `coordinates`,
   `spawnChance`, `spawnType`, `respawn`, `dropRates`, and `spells` arrays that
   duplicate `Spawns`, `ObtainedFrom`, and `CharacterAbilities`, feeding the Cargo
   store from the query layer instead. *Justification:* section 8.1 already requires
   this and characters were missed. *Cost:* one generator change plus the Character
   Lua renderer's reverse-query sections. This may remove the need to shard at all.
2. **If sharding is still needed, shard on a hash of the stable key, never on a
   sorted-index modulo.** Character type buckets are Boss 210, Enemy 427, NPC 588,
   Rare 29, which is stable under additions and mirrors `Items`, but it inherits the
   same drift problem that puts `Items/Armor` about 94 entities from breaching. A
   direct stable-key hash into four buckets balances to roughly 1.28 MB each and
   confines an addition to one bucket. A sorted-index modulo would reshuffle every
   bucket on any insertion and force a full redeploy. *Cost:* a generator change and
   a one-time full data redeploy.
3. **Replace the fourteen item-to-ability columns with `ItemEffects(ItemKey,
   EffectType, AbilityKey, ProcChance)`.** 603 rows. `Items` drops from 46 to 32
   columns. The reverse lookup becomes one query by `AbilityKey` instead of nine plus
   a merge, and `HasProc` and `HasWornEffect` become existence tests. *Justification:*
   it matches the typed-junction pattern already chosen for `ObtainedFrom` and
   `UsedIn`, and Cargo's lack of `UNION` is exactly why that pattern was chosen.
   *Cost:* near zero now, because the table has never been created.
4. **Keep the ability-side scalars.** `Spells.StatusEffectKey` 22 of 348,
   `AddProcKey` 16, `PetToSummonKey` 13, `Skills.StanceToUseKey` 6 of 52,
   `EffectToApplyKey` 4, `CastOnTargetKey` 8, `SpawnOnUseKey` 0. *Justification:* each
   is one fixed semantic slot, read forward on the ability's own page, and no consumer
   asks the reverse question. The asymmetry with items is deliberate: items have nine
   competing roles and a real reverse consumer, abilities have neither. *Cost:* none.
5. **Add `IsAuctionable` and rename `RareItem` to `IsRare`.** *Justification:* without
   `IsAuctionable` the auction house cannot render, and section 8 makes it the only
   representation. *Cost:* two columns plus the derivation
   `NOT sim_players_cant_get AND item_level BETWEEN 1 AND 39 AND item_value > 0`.
6. **Add `CharacterFactionModifiers(CharacterKey, FactionKey, ModifierValue)`.** 1,387
   rows. *Justification:* the data is exported and a template already renders it, so
   the schema is the only missing piece, and reverse lookup by faction becomes
   possible. *Cost:* one junction plus a store call.
7. **Give `classes` a `class:` stable key in the export.** *Justification:* it restores
   the invariant that every `*Key` column holds a stable key, and `starting` is the
   only source type violating it. *Cost:* one export field, 37 affected rows.
8. **Add `Characters.Image`.** *Justification:* every other detail table has it and no
   rationale exists for the omission. *Cost:* one column.
9. **Resolve the type inconsistencies.** Make `Spells.DurationSeconds` Float to match
   `CastTimeSeconds`, since both derive from ticks and a non-multiple of 60 would be
   rejected. Make `Spells.CastRange` Integer, since no value is fractional. Leave
   `Enrage`, `LevelMod`, and `RareNpcChance` as Float. *Cost:* two declarations.
10. **Decide the derived-flag policy explicitly.** Either drop `HasProc`,
    `HasWornEffect`, `HasDrops`, and `HasSpells`, or document a complete facet set and
    generate all of it. *Justification:* the current four are an arbitrary subset of a
    pattern and the underlying columns are queryable. *Recommendation:* drop them, and
    revisit when a list page needs a boolean facet. *Cost:* four columns, two
    generator lines.
11. **Move every declaration into its own declare-only template and delete the `<pre>`
    copies.** Follow `Template:AbilityClasses`, which is already correct.
    *Justification:* wiki.gg warns that a declaration inside a high-use template
    enqueues a job per transclusion and can interfere with recreation, and the `<pre>`
    duplicates are a second schema that can drift. *Cost:* mechanical, and it must
    land before first creation because the declaring template is the recreate target.
12. **Add a CI reserved-word denylist.** *Justification:* Cargo's static list is stale
    relative to current database reserved words, LIBRARIAN is a fork whose list may
    differ, and a rejected declaration fails silently by not creating the table and
    turning stores into no-ops. *Cost:* one test over the declarations.
13. **Reconcile declarations and prose in the same commit as any change.** Five drifts
    exist today. *Cost:* documentation only.

## Acceptance criteria

- Every generated Lua data module is under 4,194,304 bytes with at least 25 percent
  headroom, asserted by a test that fails on regression.
- No generated Lua record contains a field that no renderer and no Cargo store reads.
- `Items` declares 32 or fewer columns and no item-to-ability scalar keys.
- `ItemEffects`, `CharacterFactionModifiers`, `Characters.Image`, and
  `Items.IsAuctionable` exist, and `IsRare` replaces `RareItem`.
- Every `*Key` column value is a prefixed stable key, including `SourceKey` for
  `SourceType='starting'`.
- Every Cargo table is declared by a declare-only template, and no `<pre>` schema copy
  remains in the repo.
- A test fails if any declared column name appears on Cargo's reserved list or the
  target database's reserved list.
- Declared columns and the design spec's sections 7 and 8 agree exactly.
- The harness recreates every table from the revised declarations and stores the
  projected row counts: `ObtainedFrom` 6,947, `Spawns` 8,955, `CharacterAbilities`
  1,043, `ItemEffects` 603, `CharacterFactionModifiers` 1,387, `AbilityClasses` 344,
  `UsedIn` 325.

## Execution owner

`2026-08-01-wiki-cargo-cutover-foundation` owns implementation order. Its task 1
requires human approval of this technical contract. Its task 4 applies the payload,
headroom, junction, declaration, and schema changes below, and task 7 performs first
production table creation only after selector, deploy-safety, and module prerequisites
pass.

All schema work lands before the first production `cargorecreatetables`. This spec
remains `draft` until reviewed and is not promoted automatically by the planning
cleanup.
