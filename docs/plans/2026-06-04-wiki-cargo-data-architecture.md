---
title: Wiki Lua Migration & Cargo Data Architecture
type: spec
status: active
created: 2026-06-04
parent:
---

# Wiki Lua Migration & Cargo Data Architecture

Umbrella spec for the legacy→Lua wiki cutover across all seven entity types
(items, characters, spells, skills, stances, zones, quests).

## Status

Built and validated on the local Cargo harness (the live wiki is still legacy):

- Lua presentation modules + PortableInfobox templates; repo-page deploy /
  rollback / refresh; local smoke + parity harness.
- Dual-path `{{Item}}`/`{{Character}}` templates (§5): a stablekey selects the new
  path (data module + Cargo); no stablekey selects the verbatim legacy infobox
  with no Cargo write.
- Per-type ability templates `{{Spell}}`/`{{Skill}}`/`{{Stance}}`.
- Cargo detail tables `Items`, `Characters`, `Spells`, `Skills`, `Stances` plus the
  `AbilityClasses` junction, all stored through `Module:Erenshor/Cargo`.
- Item→ability links as scalar StableKey columns on `Items` (§8); the overview
  proc/worn/click cell coalesces them at display time.
- Character→item drops and item→item container drops (the first acquisition
  relationships), built as the `Drops`/`ContainerDrops` junctions via the
  attach-trick; every StableKey column follows the `Key`-suffix convention (§2.1).
  These consolidate into the unified `ObtainedFrom` table in Phase 3 (§8).

Remaining work (sequenced in §15):

- Phase 3 — unified `ObtainedFrom`/`UsedIn` relationship model (§8), consolidating
  `Drops`/`ContainerDrops` and covering every acquisition/usage mechanism; the
  `IsAuctionable`/`IsRare` item flags; the `class_starting_items` export; the
  `CharacterAbilities`/`Spawns` junctions; and reverse-query rendering.
- Phase 4 — community contribution layer: `{{ItemSource}}` rows fold into
  `ObtainedFrom` and `{{SpawnPoint}}` into `Spawns` (shared `Origin`, free-text
  `SourceText`, stablekey validation).
- Phase 5 — dual-path templates for the remaining entity types.
- Phase 6 — thin-page article generator + automated article deploy.
- Phase 7 — production cutover: deploy → incremental thin-page conversion →
  per-type legacy retirement.
- Phase 8 — freshness / orphan reconciliation + editor and template documentation.

## 1. Purpose & scope

Define and execute the **complete, automated, zero-downtime cutover** of the
Erenshor wiki from the legacy Python/Jinja2 article-generation system to the
Lua-data-module + Cargo system, for **all seven entity types** (items,
characters, spells, skills, stances, zones, quests) — pages, templates, modules,
and Cargo — ending with the legacy generators deleted. No half-measures, no
permanently-mixed state.

The end state: each article page is a thin `{{<Type>|stablekey=…}}` reference;
all entity data lives in generated `Module:Erenshor/Data/*` modules and is
rendered + stored to Cargo by the templates; community contributions live on the
page and are never overwritten by data refreshes.

**Variant scope.** The wiki has a single production target (`erenshor.wiki.gg`) and
is generated from the current shipping build. During the playtest→main promotion that
is the `playtest` variant, which becomes `main` on promotion; all pipeline runs,
code-fact pins, and golden baselines track that build. There is no dual-variant
support — the pins are the shipping build's renderings, so they carry over unchanged
at promotion and any stale non-shipping build fail-fasts loudly.

Non-goals / out of scope:
- Raw-data TOML overrides (author-only, applied pre-generation). Separate system.
- The quest guide / entity graph (`graph_overrides`). Different system.
- Per-entity anchors / deep-linking and display "qualifiers" — dropped as
  unnecessary (lists self-disambiguate by data columns; links are page-level).

## 2. Current state (grounding — verified)

- **Wiki stack (live `Special:Version`):** LIBRARIAN 4.21.0 (wiki.gg's Cargo
  fork), Scribunto, ParserFunctions, ParserPower, Arrays, Variables, Portable
  Infobox, LabeledSectionTransclusion. **No Page Forms / Semantic MediaWiki /
  Data Transfer / External Data** — community data entry is raw wikitext only.
- **Nothing is cut over.** Every live article page is still legacy inline-param
  wikitext (`{{Ability|title=…|manacost=…|…}}`, no `stablekey`). The Lua
  templates/modules and Items/Characters Cargo exist and pass on the **local
  harness only**.
- **There is no Lua-era article-page generator.** `wiki_lua/` generates data
  modules only; `wiki_deploy/` deploys modules/templates/gadgets only (never
  main-namespace pages); the only article generator is the legacy
  `wiki/generators/` Jinja2 system. The thin `wiki-dev/fixtures/pages/*` are
  hand-written test fixtures. **This generator is the central missing piece (§6).**
- **The new-path resolve is stablekey-only.** `Module:Erenshor/*` `resolve`
  requires an explicit `stablekey` (no page-title fallback — required because a
  page hosts multiple entities); without it the module renders nothing. This is
  why legacy pages cannot simply "switch templates" — they need the thin form
  *or* the legacy fallback path (§5).
- **Entity identity is `stable_key`.** Every clean-DB entity table has
  `stable_key TEXT PRIMARY KEY`; `Page` and `Name` are both non-unique (e.g. two
  `Regrowth` spells share a page+name).
- **Freshness is driven deterministically.** `wiki_deploy/refresh.py` issues
  `action=purge&forcelinkupdate=1` on `embeddedin` dependents. `cargorecreatetables`
  is driven by the local-harness `wiki-dev/cargo_check.py`; **production Cargo-recreate
  automation does not yet exist** (the CLI only prints `Special:CargoTables` guidance)
  and is a Phase 7 deliverable, gated on confirming the deploy bot can hold the
  `recreatecargodata` right on wiki.gg.
- **Relationship source tables exist in the clean DB** (§8): `loot_drops`,
  `item_drops`, `crafting_recipes`, `crafting_rewards`, `item_classes`,
  `spell_classes`, `character_spawns`, `character_attack_spells` + siblings,
  `spell_created_items`.

### 2.1 Cargo platform constraints (wiki.gg / LIBRARIAN)

These shape every Cargo decision below:

- **A template declares ≤1 table and attaches ≤1 table** (max two without a
  workaround). To write more tables from one template, transclude zero-output
  attach-only helper templates (`<noinclude>{{#cargo_attach:_table=X}}</noinclude>`,
  the "attach trick") from the storing template's `<includeonly>`.
- **Native Lua `cargo_store`/`cargo_declare` are disabled.** Rows are written
  through the `#cargo_store` parser function via `frame:callParserFunction`,
  centralized in `Module:Erenshor/Cargo` (`buildArgs` casts a field list,
  booleans → `yes`/`no`, nil omitted; `store` hands the map to the parser
  function). One call per row; loop for multiple rows.
- **No `UNION`.** Cross-table "everything of kind X" scans run one query per table
  and merge in Lua.
- **One-to-many → a separate junction table** (one row per relationship), never a
  list field or numbered columns.
- **Column names must avoid SQL keywords.** A keyword column is rejected at declare
  time, the table is silently not created, and stores become no-ops. Known traps hit
  so far: `Range` → use `CastRange`; `Character` (`CHARACTER`) → use `CharacterKey`.
- **StableKey columns end in `Key`.** Every column whose value is an entity StableKey
  is suffixed `Key`, so the schema self-documents which columns are join keys vs.
  display values. A base table's own identity stays `StableKey`; a foreign single
  reference is `<EntityType>Key` (`ItemKey`, `CharacterKey`, `AbilityKey`,
  `FactionKey`); a relationship-specific reference is `<Relationship>Key`
  (`TeachesSpellKey`, `WeaponProcKey`, `WornEffectKey`, …). Names, pages, numbers,
  booleans, and name-lists carry no `Key` suffix.
- **Types:** Integer columns must be true integers (no decimals); Boolean columns
  accept `yes`/`no` and query back as `1`/`0`. Query the implicit page via an alias
  (`_pageName=Page`) on tables that do not store a `Page` column.
- **The local harness runs stock upstream Cargo, not wiki.gg's LIBRARIAN fork** — it
  clones `mediawiki/extensions/Cargo` (`wiki-dev/Dockerfile`). So the ≤1-declare +
  ≤1-attach budget above is **not enforced locally**: "green on harness" proves row
  shape and recreate coverage, not that LIBRARIAN accepts a multi-table template. The
  attach-trick's real correctness criterion the harness *can* check is that rows stored
  by a page whose template is not attached to a table vanish on `cargorecreatetables`;
  budget acceptance must be probed live (§15).

## 3. Core principles

1. **StableKey is the only identity.** All Cargo joins/dedup/reverse-lookups use
   `StableKey`; never key/join/dedup on `Page` or `Name`.
2. **Storage of record depends on provenance.** For *generated* data the Lua data
   module is the full record and Cargo is a queryable projection (the infobox
   renders own-entity fields from Lua; Cargo carries only filter/sort/join
   columns). For *community* data there is no Lua module — it is authored on-page
   and persists only to Cargo, so **Cargo is the system of record** for those rows.
3. **Never store rendered links or markup in Cargo.** Store names/page-titles and
   numbers; render links at the display boundary via `Module:Erenshor/Link`.
4. **One table per relationship shape; store each row once, query it from every other
   page.** Item obtainability/usage rows are stored from the *item* page (the sole
   Cargo owner until Phase 5 gives quest/zone/class templates a `cargoStore`); character
   junctions are stored from the *character* page. Every other page reads the
   relationship by querying, never by storing a second copy.
5. **Two curation layers by provenance, layered precedence.** Generated rows
   (deploy-owned) and community rows (wiki-owned, never overwritten) share tables
   via an `Origin` column (`generated`|`community`); community wins on overlap.
6. **Two non-overlapping render paths; no mixing (§5).** A page is *either* fully
   new (stablekey → data module + Cargo) *or* fully legacy (no stablekey →
   inline-param rendering, no Cargo). Cargo only ever receives clean
   stablekey-resolved data — never inline param wikitext.

## 4. Entity identity & multi-entity pages

A page = N entities, each a distinct `stablekey`. The thin page carries one
`{{<Type>|stablekey=…}}` stanza per entity; each stores its own Cargo row(s)
sharing `Page`/`Name` but distinct `StableKey`. Invariant (tested): two same-name
entities on one page store as two rows distinguished only by `StableKey`, and both
infoboxes render. The smoke checker keys rows on `(Page, StableKey)` and detects
duplicate StableKeys; this extends to every new table.

## 5. Dual-path cutover architecture

The cutover must never leave the wiki broken, even for the hour-plus a
rate-limited full deploy takes. Achieved with **backward-compatible templates**
(expand/contract): every entity template branches on `stablekey` presence into
two **completely separate, non-overlapping** paths.

```wikitext
<includeonly>{{#if:{{{stablekey|}}}|
  <!-- NEW PATH (fully migrated): PortableInfobox fields come ONLY from
       {{#invoke:Erenshor/<Type>|field|X}} (data module + module-processed
       overrides) plus {{#invoke:Erenshor/<Type>|cargoStore}}. No raw inline
       param wikitext is read; this is the current repo template body, unchanged. -->
|
  <!-- LEGACY PATH: the original live inline-param infobox, embedded verbatim.
       Renders {{{title}}}, {{{manacost}}}, … as wikitext. NO #invoke, NO cargoStore. -->
}}</includeonly>
```

Properties (all required):
- **All-or-nothing per page.** Stablekey present → entirely new path; absent →
  entirely legacy path. Never half-and-half.
- **Cargo stays pure.** `cargoStore` lives only in the new branch, so it never
  runs for a legacy page; Cargo only ever holds clean stablekey-resolved data.
- **The new path is untouched.** It is the existing repo template body (Cargo +
  module overrides, already green on the harness). The dual-path change is purely
  *additive*: a gated legacy fallback branch.
- **The legacy path preserves original behavior exactly** — the live legacy
  template body is embedded verbatim, so a not-yet-converted page renders
  identically to today (its `{{ItemLink}}`/`[[links]]` params expand as wikitext,
  which a Lua fallback could not do — Scribunto output is not re-expanded).

Incremental, zero-downtime sequence: deploy dual-path templates + modules (every
live page has no stablekey → legacy branch → renders as before, no Cargo churn) →
convert pages to thin form one at a time (each crosses to the new branch + gets
its Cargo row; unconverted pages stay on the legacy branch) → once a type is
fully converted, delete its legacy else-branch and retire that type's Jinja2
generator. The dual-path template is a temporary scaffold whose legacy half is
deleted type-by-type; the end state is pure-new templates.

## 6. Thin-page article generation

The missing cutover mechanism. A new generator (in `wiki_lua`, deployed via
`wiki_deploy`) produces the thin article wikitext for every entity and uploads it
via safe-edit:

- Groups entities by `wiki_page_name`; emits one `{{<Type>|stablekey=…}}` stanza
  per entity (multi-entity page = multiple stanzas).
- **Preserves community content** during the one-time fat→thin conversion: fetch
  the live page, run the existing override classifier (§9, `override_classifier`)
  on its inline params — *generated-duplicate* (matches the data module → drop),
  *community override* (differs → keep as an explicit thin-page param),
  *intentional blank* (`-` sentinel → keep) — and carry over any non-template
  community content (extra sections, `{{ItemSource}}`/`{{SpawnPoint}}` rows). The
  thin page = `{{<Type>|stablekey=…|<kept overrides>}}` + kept sections.
- After cutover, **data refreshes never rewrite article pages** — they regenerate
  only `Module:Erenshor/Data/*` and recreate Cargo. Pages change only on entity
  add (new thin page), removal (orphan reconciliation, §11), or rename (page move,
  which leaves a redirect and needs no delete right). So community content on a page
  is structurally safe.

The override classifier/migration currently exists for Items only and is
report-only; this phase generalizes it to all seven types and makes it write the
thin pages.

## 7. Entity / detail tables

### 7.1 Fix existing tables (remove markup, model lists correctly)

`Items`:
- **Drop `ClassLinks` (`Wikitext`).** Overview rows render class links at display
  time from `Classes` via `Module:Erenshor/Link`. Keep `Classes = List (,) of
  String` (bare names from `item_classes`).
- Item→ability links are per-relationship scalar StableKey columns (§8), each
  storing the related ability's StableKey. The overview proc/worn/click cell
  coalesces them at display time (pick the set weapon/wand/bow proc, derive the
  trigger from the item slot), so no conflated or page-resolved proc column is stored.
- `IsAuctionable` (Boolean, derived): `NOT sim_players_cant_get AND item_level
  BETWEEN 1 AND 39 AND item_value > 0` (§8 auction house). `IsRare` (Boolean): the
  authored `Item.RareItem` flag (newly exported) — independent of loot tiers, set
  in the Unity Inspector; drives the ×20 auction markup and a "prized item" qualifier.

`Characters`:
- **Replace the `Zones`/`SpawnChance` markup hack with the `Spawns` table (§8).**
  Keep an optional derived `Zones = List (,) of String` (distinct zone names) as a
  cheap filter convenience. **`FactionKey`: store the WorldFaction `stablekey`** (the
  only joinable faction; the combat `Faction` enum is name-only, not a link; the
  `Key` suffix follows §2.1).

All-6-classes → "All" is a display-only collapse in `Module:Erenshor/Link`
(store all class names; render "All" when the set is the full 6-class roster).

### 7.2 Abilities: per-type detail tables + class junction (no base table)

Spells, skills, and stances are three independent per-type tables. There is **no
shared `Abilities` base table**. A base table's only unique
benefit is a single-query cross-type "all abilities" scan (Cargo has no `UNION`),
which is rare and Lua-mergeable; ability links already resolve from the Lua data
modules, not Cargo. It would cost a redundant `Name`/`Image` row per ability, an
extra store per page, and push `{{Spell}}`/`{{Skill}}` to three tables (needing the
attach-trick) for marginal value. Each type's template declares its own detail table;
class membership is the `AbilityClasses` junction (§8). `{{Spell}}` and `{{Skill}}`
each declare their detail table and directly attach `AbilityClasses` — exactly the
wiki.gg 1-declare + 1-attach budget, so **no attach-trick is needed for abilities**
(the trick first applies in Phase 3, e.g. `{{Character}}` writing several junctions).

`Spells` (from `spells`): `StableKey`, `Page`, `Name`, `Image`, `Type`, `Line`,
`RequiredLevel`, `ManaCost`, `CastTimeSeconds`, `CooldownSeconds`,
`DurationSeconds`, `CastRange`, `DamageType`, `TargetDamage`, `TargetHealing`,
`CasterHealing`, `ShieldingAmt`, `SimUsable`, `SelfOnly`, `GroupEffect`, `Aggro`,
`CrowdControl`, `GrantInvisibility`, `CannotInterrupt`, `Jolt`, `NoResonate`, plus
single-reference relation StableKey columns `StatusEffectKey`
(`status_effect_to_apply_stable_key`), `AddProcKey` (`add_proc_stable_key`),
`PetToSummonKey` (`pet_to_summon_stable_key`).
(Times are in seconds.)

`Skills` (from `skills`): `StableKey`, `Page`, `Name`, `Image`, `Type` (`Innate`→"Passive"),
`CooldownSeconds`, `CastRange`, `SkillPower`, `PercentDmg`, `DamageType`, `Require2H`,
`RequireDualWield`, `RequireBow`, `RequireShield`, `RequireBehind`, plus relation
StableKey columns `StanceToUseKey`, `EffectToApplyKey`, `CastOnTargetKey`, `SpawnOnUseKey`.

`Stances` (from `stances`; all columns real): `StableKey`, `Page`, `Name`, `Image`,
`MaxHpMod`, `DamageMod`, `ProcRateMod`, `DamageTakenMod`, `SelfDamagePerAttack`,
`AggroGenMod`, `SpellDamageMod`, `SelfDamagePerCast`, `LifestealAmount`,
`ResonanceAmount`, `StopRegen`.

Each detail table is self-contained (`Page`/`Name`/`Image` denormalized) so per-type
list pages need no join. Detail tables carry the curated *queryable* subset; the full
per-entity field set (incl. descriptions/long text) stays in the Lua module for the
infobox. Field coverage verified against `Spell.cs`/`Skill.cs`/`Stance.cs`.

### 7.3 Zones & Quests: no detail table

Zones and quests carry **no Cargo detail table**, by decision. A detail table earns
its cost only when other pages filter/sort/join on the entity's own columns; nothing
does that for zones or quests. Their pages render own-entity fields straight from
`Module:Erenshor/Data/{Zones,Quests}` (the infobox), and every cross-page relationship
that reaches a zone or quest is already carried by an item/character junction —
`ObtainedFrom` (`mining`/`fishing`/`item_bag` → `SourceKey` = zone; `quest` →
`SourceKey` = quest), `UsedIn` (`quest_requirement` → `TargetKey` = quest), and
`Spawns` (`Zone`) — so zone/quest pages answer "what's obtained/used/spawns here" by
**reverse-querying those tables**, never by owning one. This is also why Phase 3 can
make item relationships item-owned without a `Zone.lua`/`Quest.lua` `cargoStore` (§8).

## 8. Relationship (junction) tables

Item **obtainability** and **usage** are each one unified, typed table, both
**item-owned**: every row is stored from the *item* page — the only entity with a
Cargo `cargoStore` gate until Phase 5 gives quest/zone/class templates one. This
collapses the phase-ordering trap (no source page needs a template that does not yet
exist) and matches the main consumer: the item's own "How to Obtain"/"Used For" plus
every source page's reverse query. Cargo has no `UNION`, so a single typed table beats
one-table-per-mechanism (one query, fewer attaches, uniform rendering). Foreign keys
are `<Entity>Key` StableKey columns resolved to links by type at display.
`ObtainedFrom` and the `Spawns` junction — the two tables with a Phase 4 community
counterpart — carry `Origin` (`generated`|`community`) from Phase 3 onward, so Phase 4
adds only rows and templates, never a production schema recreate; `UsedIn` and
`CharacterAbilities` have no community layer and no `Origin`.

**`ObtainedFrom`** — how an item is acquired (item ← source): `ItemKey`,
`SourceType`, `SourceKey` (StableKey; null for free-text community rows),
`SourceText` (String; free-text source for community rows, null for generated),
`Probability` (Float; null = deterministic), `IsGuaranteed` (Boolean),
`Quantity` (Integer), `SourceCondition` (String: day/night, quest-gate, chest tier —
`Condition` is a SQL keyword, §2.1), `Origin` (`generated`|`community`). `SourceKey`
resolves by `SourceType`:

| `SourceType` | from | `SourceKey` → |
|---|---|---|
| `drop` | `loot_drops` (treasure chests are characters) | CharacterLink |
| `vendor` | `character_vendor_items` (+quest unlock → `SourceCondition`) | CharacterLink |
| `dialog` | `character_dialogs.give_item_stable_key` | CharacterLink |
| `quest` | quest reward (`Quest.ItemOnComplete`) | QuestLink |
| `craft` | `crafting_rewards` (`Quantity`) | ItemLink (recipe item) |
| `item_use` | `item_drops` (fossil) + `spell_created_items` (offering bag) | ItemLink (source item) |
| `mining` | `mining_nodes`+`mining_node_items` | ZoneLink |
| `fishing` | `water_fishables` (day/night → `SourceCondition`) | ZoneLink |
| `item_bag` | `item_bags` (ground pickups) | ZoneLink |
| `starting` | `class_starting_items` (export from `CharSelectManager`) | ClassLink |
| `community` | `{{ItemSource}}` (§9) | null — free text in `SourceText` |

World-point sources (`mining`/`fishing`/`item_bag`) carry the zone as `SourceKey`
(no page of their own); dedup to one row per item×type×zone.

**`UsedIn`** — what an item is consumed for (item → consumer): `ItemKey`, `UseType`,
`TargetKey`, `Quantity`, `Slot`:

| `UseType` | from | `TargetKey` → |
|---|---|---|
| `craft_material` | `crafting_recipes` | ItemLink (recipe) |
| `quest_requirement` | `quest_required_items` | QuestLink |
| `upgrade_material` | smithing special-combine consumables via the `smithing.upgrade_ids` code fact (playtest: `31377423`/`46289586`/`2298018`/`2265228` = Mold: An Otherwordly Box, Planar Stone, Inert Diamond, Merging Vessel); never transcribed from `Smithing.cs` | ItemLink (recipe) |

`craft` (result → `ObtainedFrom`) and `craft_material`/`upgrade_material` (inputs →
`UsedIn`) make dedicated crafting tables unnecessary; the recipe item renders its
forward ingredient/result list from its Lua module, while `ObtainedFrom`/`UsedIn`
are the reverse indices.

**Auction house** is a derived per-item flag, not an `ObtainedFrom` row (no discrete
source): `Items.IsAuctionable` (§7.1). `RareItem` (`IsRare`) only soft-rejects the
SimPlayer draw (98%) and ×20-prices, so rare items stay auctionable — qualified, not
excluded. Rendered as an "Auction House" line in How to Obtain.

**Non-item junctions** keep their own per-shape tables (not obtainability/usage):

- `AbilityClasses` (from `spell_classes` + the six `*_required_level` skill columns;
  owner = ability): `AbilityKey`, `Class`, `RequiredLevel`. Spells broadcast their
  single `required_level`; skills use the per-class column. Declared by a
  declare-only `Template:AbilityClasses`; `{{Spell}}`/`{{Skill}}` attach it.
- `CharacterAbilities` (from `character_attack_spells` + siblings +
  `character_attack_skills`; owner = character): `CharacterKey`, `AbilityKey`, `Usage`.
- `Spawns` (owner = character): `CharacterKey`, `Zone`, `Scene`, `X`, `Y`, `Z`,
  `SpawnChance`, `NightSpawn`, `SpawnUponQuestComplete`, `LevelMod`, `RareNpcChance`,
  `SpawnType`, `Origin`. Source is the `wiki_character_spawns` view (`character_spawns`
  filtered to `is_wiki_generated`, with `character_chained_spawns` already expanded in
  per `docs/plans/archive/2026-05-28-dynamic-spawn-coverage-design.md`). **Treasure-chest
  possible locations fold in here**: the four `Lost Treasure (…)` chest characters get
  one `treasure_chest` row per pickable `treasure_locations` entry
  (`treasure_chest_possible_spawns` JOIN `treasure_locations` for coordinates),
  `SpawnType='treasure_chest'`, `SpawnChance` null (the game's per-location chest odds
  are not exported). Without this, a treasure-hunting item's `drop` row points at a
  chest character whose page shows no spawn locations. Replaces the flat character
  `Zones`/`SpawnChance`. Community spawns use `{{SpawnPoint}}` (§9) with `Origin=community`.

Faction relationships are deliberately not one shape: only the WorldFaction is
stable-keyed/joinable (`my_world_faction_stable_key`, `character_faction_modifiers`);
the combat `Faction` enum (`my_faction`, aggressive/allied lists) is name-only.

**Item→ability links are 1:1 scalar columns on `Items`, not junction tables**
(`Item.cs` exposes each as a single reference), each storing the ability
**StableKey** in a `Key`-suffixed column: `TeachesSpellKey`, `TeachesSkillKey`,
`WeaponProcKey` (+`WeaponProcChance`), `WandEffectKey` (+`WandProcChance`),
`BowEffectKey` (+`BowProcChance`), `WornEffectKey`, `ClickEffectKey`, `SkillUseKey`,
`AuraKey`. Reverses are queries on the column. The overview "Proc" cell is
display-time coalescing (pick whichever of weapon/wand/bow is set; derive trigger
from item slot), not a stored conflated column.

**Deferred / known gaps:** the global random world-drop pool (`GameManager` injects
Maps/Molds/etc. into every NPC at runtime — not per-source), and two 1-off hardcoded
obtainability specials (Chessboard Candlekeeper→mold, Time Stone). Documented, not modeled.

### 8.1 Forward-store / reverse-query rendering

Every relationship row is stored once from its owner page (item-owned for
`ObtainedFrom`/`UsedIn`, character-owned for `Spawns`/`CharacterAbilities`) and read
everywhere else **via Cargo query** — the item's own "How to Obtain"/"Used For", and
"dropped by"/"used by"/"taught by"/"spawns here" on character, zone, quest, and class
pages, in list pages and infoboxes. Because item-owned rows are read forward by the
item itself and reverse by the source pages, the query is the single access path in
both directions. The denormalized reverse arrays (`usedBy`, `itemsWithEffect`,
`source`) are **removed from the Lua data modules**. Single source, removal-correct
(Leaguepedia's model).

## 9. Community contribution layer (non-extractable relationships)

Non-extractable, community-curated facts (global drops not on a loot table;
spawn points the exporter misses) stay community-editable on-wiki, survive every
redeploy, and are queryable alongside generated rows. Entry is raw
multiple-instance row templates (no Page Forms). Each row template takes
`stablekey=` (Page/Name can't disambiguate multi-entity pages), `#cargo_store`s
one row with `Origin=community`, and validates `stablekey` against the data module
via `mw.loadData` (unresolved → tracking category).

- `{{ItemSource|stablekey=item:…|source=…|probability=…|condition=…}}` → an
  `ObtainedFrom` row with `Origin=community` and `SourceType=community`: the free-text
  `source` lands in `SourceText` (with `SourceKey` null), `probability` in
  `Probability`, `condition` in `SourceCondition`. It shares the item's unified "How to
  Obtain" query and render path — no separate `OtherItemSources` table. Generalizes the
  legacy free-text `othersource` field into queryable rows.
- `{{SpawnPoint|stablekey=npc:…|zone=…|x=…|y=…|z=…|spawn_chance=…|night_spawn=…|spawn_upon_quest_complete=…}}`
  → a `Spawns` row (§8) with `Origin=community`.

Editors find a variant's `stablekey` in the page source (it's on the infobox call)
— documented in the entity-editing guides (§13), not surfaced as infobox chrome.
Precedence per §3: community is additive or corrective; community wins on overlap.
Survives-redeploy invariant (tested): the generator owns modules/templates and
never overwrites community row templates; after cutover, data refreshes don't
touch article pages at all (§6).

## 10. Caching & freshness

- Cargo writes rows on **page parse**, not on declare-save. A cross-page query is
  only as fresh as the querying page's last parse (MW HTML cache; ≤24h or purge).
  Modules share templates' link-tracking, so editing `Data/*` enqueues
  `refreshLinks` (job queue, `$wgJobRunRate` caveat).
- The pipeline does not wait on the queue: keep `purge_pages(force_link_update=True)`
  on `embeddedin` dependents; drive `cargorecreatetables` on schema change
  (replacement-table form for large recreates); run the job queue as part of deploy.
- Ordering: queried-against rows must exist before the querying page parses (push
  pages → recreate Cargo → purge dependents).
- **Item-ownership freshness:** because obtainability/usage rows are stored from the
  item page, a change in any *source* table (loot/vendor/dialog/quest/craft/mining/
  fishing/item_bag/class/smithing) must reparse the **owning item pages**, not the
  source-entity page. `wiki_deploy/refresh.py` drives this; on the harness it is the
  recreate + null-edit path. Production `cargorecreatetables` automation is a Phase 7
  deliverable (§2, §15).

## 11. Removals & orphans

- Any page edit/delete is a Cargo write that drops that page's prior rows. Entity
  removed from the data module → on reparse, resolve=missing → store nothing →
  row dropped. Whole page gone → delete page → rows dropped.
- Reverse-query rendering (§8.1) makes removals correct (no ghost rows).
- **Cargo rows: drop-and-recreate** of generated tables from the authoritative set,
  gated by `cargo_check`. Recreating from the authoritative page set is what removes a
  deleted entity's rows; community rows (same tables, `Origin=community`) are reparsed
  and preserved.
- **Article pages: manual-delete queue.** The deploy bot cannot hold page-delete
  rights, so it never deletes. The cutover deploy owns the authoritative page set and
  **emits an orphan-page report** (the rollback tooling already reports created pages);
  a human admin clears the queue. Renames are page *moves* (leave a redirect, need no
  delete right). Until an orphan page is deleted, its stablekey no longer resolves, so
  its own Cargo rows are already gone and it lands in the community `stablekey`
  tracking category.
- The community `stablekey` validation category (§9) flags rows whose key no
  longer resolves after a game update.

## 12. Display layer

- Links render from stored names via `Module:Erenshor/Link`; Cargo never stores
  markup. All-6-classes → "All" is display-only. Reverse-relationship sections
  render from Cargo queries (§8.1); own-entity fields from the Lua module.

## 13. Editor & template documentation

First-class docs on the installed `TemplateData` + `/doc` subpage stack
(`{{Documentation}}` in each template's `<noinclude>`): a `<templatedata>` block
per template (param label/description/type/required/example, surfaced in
VisualEditor), purpose + usage examples, related templates. Per-entity-type
editing guides explain which facts are generated vs. community-editable, how to
add an `{{ItemSource}}`/`{{SpawnPoint}}` row (including finding the `stablekey` in
page source), and the precedence rules. Supersedes the ad-hoc doc pages.

## 14. Testing

- Multi-entity: same-name two-spell and two-character pages → two rows, distinct
  StableKey, shared Page; both infoboxes render.
- Dual-path (§5): a fat fixture page → legacy branch renders + **no** Cargo row;
  a thin fixture page → new branch renders + Cargo row.
- No markup in Cargo: assert stored values are names/numbers, not `<span>`/`[[…]]`.
- Reverse queries: item "dropped by", ability "used by", "what a class can learn".
- Community layer: `{{ItemSource}}` stores an `ObtainedFrom` row and `{{SpawnPoint}}`
  a `Spawns` row, both `Origin=community`, both surviving a simulated redeploy and
  appearing in the same unified query as generated rows; unresolved `stablekey` →
  tracking category.
- Thin-page generator: emits correct stanzas per entity; multi-entity = multiple
  stanzas; community overrides + sections preserved across a regenerate.
- Extend `wiki-dev/smoke/cargo.py` + fixtures + `cargo_check.py` recreate set to
  every new table.
- Treasure-chest spawns: a `Lost Treasure (…)` chest character stores `treasure_chest`
  `Spawns` rows for its pickable locations, and a treasure-hunting item's `drop` row
  resolves to a chest page that now shows those locations.
- **Harness limitation (explicit):** `wiki-dev` runs stock upstream Cargo, so it
  cannot test the wiki.gg ≤1-declare+≤1-attach budget or the attach-trick's live
  acceptance. What it *does* test is recreate coverage — rows stored by a page whose
  template is not attached to the table vanish on `cargorecreatetables`. Live budget
  acceptance is a §15 pre-Phase-3 probe.

## 15. Phased sequencing

Cargo for every type is completed on the local harness before any page is converted,
so the dual-path new branch is whole before cutover. Each phase is TDD-first and
atomic; `writing-plans` turns each into a step-by-step plan.

**Pre-Phase-3 gate — live attach-trick probe.** Before building Phase 3 on the
attach-trick, run a one-off non-destructive probe on the live wiki: a toy 3-table
template using the attach-trick in a user/sandbox namespace, store rows, confirm
LIBRARIAN accepts the multi-table template, `cargorecreatetables` finds the rows, and
the deploy bot can drive the recreate. Delete the probe pages after. This converts the
harness's untestable budget assumption (§14) into a fact and answers the Phase 7
bot-rights question early.

3. Phase 3 — unified **item-owned** relationship model: `ObtainedFrom` (consolidating
   the built `Drops`/`ContainerDrops`) + `UsedIn`, covering every acquisition/usage
   mechanism, with `Origin`/`SourceText` declared up front for the Phase 4 community
   layer; the `IsAuctionable` derived flag + newly-exported `IsRare`; the
   `class_starting_items` export (`starting` source); the `CharacterAbilities` and
   `Spawns` junctions (`Spawns` folds in treasure-chest possible locations); item→
   ability scalar columns. Reverse relations move to Cargo queries; denormalized
   arrays dropped.
4. Phase 4 — community contribution layer.
5. Phase 5 — dual-path templates for all seven types (verbatim legacy fallback
   branch; new branch unchanged); both-branch harness tests.
6. Phase 6 — thin-page article generator + automated article deploy + generalized
   override-preserving conversion (all seven types).
7. Phase 7 — production cutover: build production `cargorecreatetables` automation
   (confirming the bot's `recreatecargodata` right, per the §15 probe) → TemplateSandbox
   gate → deploy dual-path templates/modules → recreate Cargo → incrementally convert
   pages to thin → per-type, delete the legacy branch + retire that type's Jinja2
   generator → live smoke + rollback manifest + orphan-page report for manual deletion.
8. Phase 8 — freshness / orphan drop-and-recreate automation + documentation.

## 16. Key decisions

- Dual-path `{{#if:stablekey|new|legacy}}` cutover; all-or-nothing per page; Cargo
  written only in the new branch; legacy branch = verbatim legacy infobox, deleted
  per type after conversion.
- Thin generated `{{Type|stablekey=}}` pages are the cutover mechanism; community
  content is preserved on-page.
- Store each relationship row once from its owner page, query it from every other page; no denormalized reverse arrays.
- Item obtainability and usage are two unified typed tables — `ObtainedFrom`
  (item ← source) keyed by `SourceType`, `UsedIn` (item → consumer) keyed by `UseType`
  — **both item-owned** (the item page is the only Cargo owner until Phase 5), not one
  table per mechanism: Cargo has no `UNION`, so one typed table = one query + fewer
  attaches. World-point sources (mining/fishing/item_bag) carry the zone as `SourceKey`;
  the auction house is a derived `IsAuctionable` flag, not a row. `Condition`→
  `SourceCondition` (SQL keyword). Zones and quests own no detail table (§7.3).
- Orphan reconciliation: Cargo rows via drop-and-recreate; article pages via an
  orphan-page report + manual admin deletion (the bot cannot get page-delete rights);
  renames are page moves.
- Community rows share the generated tables via `Origin`: `{{ItemSource}}`→`ObtainedFrom`
  (free-text `SourceText`, null `SourceKey`, `SourceType=community`),
  `{{SpawnPoint}}`→`Spawns`; no separate `OtherItemSources` table. Treasure-chest
  possible locations fold into `Spawns`.
- Abilities use per-type `Spells`/`Skills`/`Stances` tables + the `AbilityClasses`
  junction; no shared base table; distinct `{{Spell}}`/`{{Skill}}` templates.
- All Cargo storage goes through `Module:Erenshor/Cargo`; all times in seconds (no ticks).

## 17. References
- Cargo — Storing data: https://www.mediawiki.org/wiki/Extension:Cargo/Storing_data
- Cargo — Querying data (HOLDS): https://www.mediawiki.org/wiki/Extension:Cargo/Querying_data
- Cargo — FAQ (query cache lag/purge): https://www.mediawiki.org/wiki/Extension:Cargo/FAQ
- River — Representing one-to-many relations: https://river.me/blog/one-to-many/
- River — Cargo list-type fields: https://river.me/blog/cargo-list-type-fields/
- River — Optimizing Cargo (no UNION): https://river.me/blog/optimizing-cargo-1/
- Leaguepedia Module:CargoQuery: https://lol.fandom.com/wiki/Module:CargoQuery
- Help:Multiple-instance templates: https://www.mediawiki.org/wiki/Help:Multiple-instance_templates
- MediaWiki Help:TemplateData: https://www.mediawiki.org/wiki/Help:TemplateData
- Expand/contract (parallel change) migration: https://martinfowler.com/bliki/ParallelChange.html
- Cargo — Other features (Lua interface): https://www.mediawiki.org/wiki/Extension:Cargo/Other_features
- wiki.gg — Cargo troubleshooting: https://support.wiki.gg/wiki/Cargo/troubleshooting
- wiki.gg — Cargo attaching tables: https://support.wiki.gg/wiki/Cargo/attaching_tables
- PoE wiki — Module:Cargo (Lua store pattern): https://www.poewiki.net/wiki/Module:Cargo
