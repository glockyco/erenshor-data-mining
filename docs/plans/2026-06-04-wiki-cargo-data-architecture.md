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
- Phase 4 — community contribution layer (`ItemSource`/`SpawnPoint`, `Origin`,
  stablekey validation).
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
  `action=purge&forcelinkupdate=1` on `embeddedin` dependents; `cargo_check.py`
  drives `cargorecreatetables`.
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
4. **One table per relationship shape; store forward once, query reverse.**
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
  add (new thin page), removal (orphan delete, §11), or rename (page move). So
  community content on a page is structurally safe.

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
  cheap filter convenience. **`Faction`: store the WorldFaction `stablekey`** (the
  only joinable faction; the combat `Faction` enum is name-only, not a link).

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

## 8. Relationship (junction) tables

Item **obtainability** and **usage** are each one unified, typed table. The reverse
query on an item page is the main consumer and Cargo has no `UNION`, so a single
typed table beats one-table-per-mechanism: one reverse query, fewer attaches,
uniform rendering. Foreign keys are `<Entity>Key` StableKey columns resolved to
links by type at display; rows are stored forward on the owner page. `Origin` is
added to every generated relationship table with the Phase 4 community layer.

**`ObtainedFrom`** — how an item is acquired (item ← source): `ItemKey`,
`SourceType`, `SourceKey`, `Probability` (Float; null = deterministic),
`IsGuaranteed` (Boolean), `Quantity` (Integer), `Condition` (String: day/night,
quest-gate, chest tier). `SourceKey` resolves by `SourceType`:

| `SourceType` | from | writer | `SourceKey` → |
|---|---|---|---|
| `drop` | `loot_drops` (treasure chests are characters) | character | CharacterLink |
| `vendor` | `character_vendor_items` (+quest unlock → `Condition`) | character | CharacterLink |
| `dialog` | `character_dialogs.give_item_stable_key` | character | CharacterLink |
| `quest` | quest reward (`Quest.ItemOnComplete`) | quest | QuestLink |
| `craft` | `crafting_rewards` (`Quantity`) | recipe item | ItemLink |
| `item_use` | `item_drops` (fossil) + `spell_created_items` (offering bag) | source item | ItemLink |
| `mining` | `mining_nodes`+`mining_node_items` | zone | ZoneLink |
| `fishing` | `water_fishables` (day/night → `Condition`) | zone | ZoneLink |
| `item_bag` | `item_bags` (ground pickups) | zone | ZoneLink |
| `starting` | `class_starting_items` (new export from `CharSelectManager`) | class | ClassLink |

World-point sources (`mining`/`fishing`/`item_bag`) have no pages of their own, so
the **zone** owns them (dedup to one row per item×type×zone).

**`UsedIn`** — what an item is consumed for (item → consumer): `ItemKey`, `UseType`,
`TargetKey`, `Quantity`, `Slot`:

| `UseType` | from | writer | `TargetKey` → |
|---|---|---|---|
| `craft_material` | `crafting_recipes` | recipe item | ItemLink (recipe) |
| `quest_requirement` | `quest_required_items` | quest | QuestLink |
| `upgrade_material` | hardcoded quality recipes (golden `31377423`/fuel `46289586`, blessing-removal `2298018`), curated from `Smithing.cs` | recipe item | ItemLink |

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
- `Spawns` (from `character_spawns` + `character_chained_spawns` per
  `docs/superpowers/specs/2026-05-28-dynamic-spawn-coverage-design.md`; owner =
  character): `CharacterKey`, `Zone`, `Scene`, `X`, `Y`, `Z`, `SpawnChance`,
  `NightSpawn`, `SpawnUponQuestComplete`, `LevelMod`, `RareNpcChance`, `SpawnType`.
  Replaces the flat character `Zones`/`SpawnChance`. Community spawns use
  `{{SpawnPoint}}` (§9) with `Origin=community`.

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

Reverse/cross-page relationships — the item's "How to Obtain" (`ObtainedFrom`) and
"Used For" (`UsedIn`), plus "dropped by"/"used by"/"taught by" on other pages — are
**rendered via Cargo query** against the unified tables, the non-item junctions, and
the item→ability columns, in list pages and infoboxes. The denormalized reverse
arrays (`usedBy`, `itemsWithEffect`, `source`) are **removed from the Lua data
modules**. Single source, removal-correct (Leaguepedia's model).

## 9. Community contribution layer (non-extractable relationships)

Non-extractable, community-curated facts (global drops not on a loot table;
spawn points the exporter misses) stay community-editable on-wiki, survive every
redeploy, and are queryable alongside generated rows. Entry is raw
multiple-instance row templates (no Page Forms). Each row template takes
`stablekey=` (Page/Name can't disambiguate multi-entity pages), `#cargo_store`s
one row with `Origin=community`, and validates `stablekey` against the data module
via `mw.loadData` (unresolved → tracking category).

- `{{ItemSource|stablekey=item:…|source=…|drop_probability=…|zone=…|notes=…}}` →
  `OtherItemSources(StableKey, Source, DropProbability, Zone, Notes, Origin)`.
  Generalizes the free-text `othersource` field into queryable rows.
- `{{SpawnPoint|stablekey=npc:…|zone=…|x=…|y=…|z=…|spawn_chance=…|night_spawn=…|spawn_upon_quest_complete=…|notes=…}}`
  → the `Spawns` table (§8), `Origin=community`.

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

## 11. Removals & orphans

- Any page edit/delete is a Cargo write that drops that page's prior rows. Entity
  removed from the data module → on reparse, resolve=missing → store nothing →
  row dropped. Whole page gone → delete page → rows dropped.
- Reverse-query rendering (§8.1) makes removals correct (no ghost rows).
- **Drop-and-recreate** of generated tables from the authoritative set,
  gated by `cargo_check`. The deploy bot cannot get page-delete rights, so orphan
  removal relies on this deterministic rebuild + the orphan-page reconciliation
  the cutover deploy performs (it owns the authoritative page set). Community rows
  (separate `Origin`/templates) are unaffected.
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
- Community layer: `{{ItemSource}}`/`{{SpawnPoint}}` store `Origin=community`,
  survive a simulated redeploy; unresolved `stablekey` → tracking category.
- Thin-page generator: emits correct stanzas per entity; multi-entity = multiple
  stanzas; community overrides + sections preserved across a regenerate.
- Extend `wiki-dev/smoke/cargo.py` + fixtures + `cargo_check.py` recreate set to
  every new table.

## 15. Phased sequencing

Cargo for every type is completed on the local harness before any page is converted,
so the dual-path new branch is whole before cutover. Each phase is TDD-first and
atomic; `writing-plans` turns each into a step-by-step plan.

3. Phase 3 — unified item-relationship model: `ObtainedFrom` (consolidating the
   built `Drops`/`ContainerDrops`) + `UsedIn`, covering every acquisition/usage
   mechanism; the `IsAuctionable` derived flag + newly-exported `IsRare`; the
   `class_starting_items` export (`starting` source); the `CharacterAbilities` and
   `Spawns` junctions; item→ability scalar columns. Reverse relations move to Cargo
   queries; denormalized arrays dropped.
4. Phase 4 — community contribution layer.
5. Phase 5 — dual-path templates for all seven types (verbatim legacy fallback
   branch; new branch unchanged); both-branch harness tests.
6. Phase 6 — thin-page article generator + automated article deploy + generalized
   override-preserving conversion (all seven types).
7. Phase 7 — production cutover: TemplateSandbox gate → deploy dual-path
   templates/modules → recreate Cargo → incrementally convert pages to thin →
   per-type, delete the legacy branch + retire that type's Jinja2 generator → live
   smoke + rollback manifest.
8. Phase 8 — freshness / orphan drop-and-recreate automation + documentation.

## 16. Key decisions

- Dual-path `{{#if:stablekey|new|legacy}}` cutover; all-or-nothing per page; Cargo
  written only in the new branch; legacy branch = verbatim legacy infobox, deleted
  per type after conversion.
- Thin generated `{{Type|stablekey=}}` pages are the cutover mechanism; community
  content is preserved on-page.
- Store forward / query reverse; no denormalized reverse arrays.
- Item obtainability and usage are two unified typed tables — `ObtainedFrom`
  (item ← source) keyed by `SourceType`, `UsedIn` (item → consumer) keyed by
  `UseType` — not one table per mechanism: the item's reverse "how to obtain" /
  "used for" is the main consumer and Cargo has no `UNION`, so one typed table = one
  query + fewer attaches. World-point sources (mining/fishing/item_bag) are owned by
  the zone; the auction house is a derived `IsAuctionable` flag, not a row.
- Orphan reconciliation = drop-and-recreate (the bot cannot get page-delete rights).
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
