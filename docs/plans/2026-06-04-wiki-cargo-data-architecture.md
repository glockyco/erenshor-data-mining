---
title: Wiki Lua Migration & Cargo Data Architecture
type: spec
status: active
created: 2026-06-04
parent: 2026-07-09-erenshor-planning-overview
---

# Wiki Lua Migration & Cargo Data Architecture

Umbrella spec for the legacy→Lua wiki cutover across all seven entity types
(items, characters, spells, skills, stances, zones, quests).

## Status

Production baseline: repo-owned Lua modules and templates are deployed to the
production wiki, and generated data modules are deployed for items, item shards,
spells, skills, and links. All playtest images and filename redirects are uploaded.
See `docs/plans/2026-07-30-wiki-cutover-state-audit.md` for the measured live state.

Four generated data modules are **not** deployed — `Module:Erenshor/Data/Characters`,
`Data/Quests`, `Data/Stances`, and `Data/Zones` — so the Lua path for those types
cannot resolve on live even where its template branch exists. `Module:Erenshor/Link/Search`
is also undeployed.

- `Template:ItemTooltip` dispatches `kind=Weapon/Armor` to
  `Module:Erenshor/Item/ParameterizedTooltip` and `stablekey=…` to
  `Module:Erenshor/Item/Tooltip`. 793 equipment articles use the parameterized
  tooltip (578 armor, 792 of which also carry a stablekey) and render correctly.
- The production equipment path has one parameterized `{{ItemTooltip|kind=…}}`
  invocation per weapon/armor article, with display-ready Normal-quality legacy
  arguments. `Module:Erenshor/Item/ParameterizedTooltip` derives all eight quality
  variants through `Module:Erenshor/Item/Quality` (gated by
  `PLANAR_MARCH_ENABLED=false` until the patch ships) and composes the live legacy
  `Item/Weapon` and `Item/Armor` templates through `frame:expandTemplate` with
  newline-joined assembly.
- **No article page renders the Lua infobox or stores Cargo rows.** Live
  `Template:Item` gates its Lua branch on `lua=1` in addition to `stablekey`, and
  zero live pages pass `lua=1`. The stablekey on the 792 equipment articles feeds
  the parameterized tooltip and the interactive-map link only.
- **Production Cargo is inert.** None of the ten designed tables exist on live —
  `Special:CargoTables` holds only a legacy `Consumable` table and an orphaned
  `Item` table, both empty and both on unrelated schemas. The Cargo-declaring
  templates are deployed and declare correctly, but declaring creates nothing on
  save and the deploy bot cannot run the creation step (§2).
- Phase 3 — item-owned `ObtainedFrom`/`UsedIn` consolidation, `CharacterAbilities`
  and `Spawns`, scalar item→ability columns, reverse queries, and the related
  exports — is complete **in the repo and on the local harness**; its plan is
  archived. It is unexercised on production because no Cargo table exists there.
  `Drops` and `ContainerDrops` are folded into the unified model and deleted.
- Non-equipment kinds (`general`, `consumable`, `aura`, `charm`, `spell scroll`,
  `skill book`, `mold`) remain on the legacy Jinja templates.

Remaining work follows one dependency chain:

1. Approve the field-level render-parity contract in
   `2026-08-01-wiki-render-parity-gate` and implement its local comparison
   instrument.
2. Correct the Cargo schema and generated payload under
   `2026-07-30-wiki-cargo-schema-revision`.
3. Implement the reusable protection, drift, guarded-write, rollback, and
   privileged-operation controls in `2026-07-30-wiki-deploy-sync-discipline`.
4. Deploy the missing data modules and exact `lua=1` dual paths for all seven
   entity types while every production article remains on its legacy path.
5. Create the production Cargo tables through the privileged replacement-table
   procedure, then run local and TemplateSandbox canaries.
6. Convert articles per type under `2026-07-11-wiki-article-cutover` only after
   `2026-08-01-wiki-cargo-cutover-foundation` records a passing foundation report
   with zero converted production articles.

The foundation plan owns the executable order through table creation and sandbox
readiness. The article-cutover plan owns per-type conversion and legacy retirement.
The Cargo ownership, replacement-table, refresh, identity, and community-row design
below remains authoritative.

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

- **Wiki stack (live `Special:Version`, re-verified 2026-07-30):** MediaWiki 1.43.6,
  LIBRARIAN 4.21.0 (wiki.gg's Cargo fork), Scribunto, ParserFunctions, ParserPower,
  Arrays, Variables, VariablesLua, Portable Infobox, LabeledSectionTransclusion,
  TemplateData, TemplateSandbox, **TemplateStyles 1.0**, and
  **TemplateStylesExtender 2.0.0**. **No Page Forms / Semantic MediaWiki /
  Data Transfer / External Data** — community data entry is raw wikitext only.
- **Production cutover is presentation-only.** Repo-owned Lua modules and templates
  are live, along with generated data modules for items, item shards, spells, skills,
  and links. `Template:ItemTooltip` dispatches weapon/armor calls to the
  parameterized tooltip module and `stablekey=…` calls to the stablekey tooltip
  module, and 793 equipment articles use it. **No article renders the Lua infobox and
  no Cargo table exists on production**, so the data half of the cutover is entirely
  unexercised there.
- **Thin-page conversion remains incomplete.** No article uses the thin form; Phase 6
  still delivers the override-preserving thin-page converter and automated article
  deploy for all seven entity types.
- **Path selection and entity identity are separate.** Exact `lua=1` is the only
  selector for the generated Lua/Cargo branch across all seven entity templates.
  `stablekey` is identity data only. After `lua=1` selects that branch,
  `Module:Erenshor/*` `resolve` requires an explicit valid `stablekey` because a
  page can host multiple entities. A missing or invalid key emits the missing-data
  diagnostic and stores no Cargo row. Without exact `lua=1`, the template renders
  the verbatim legacy branch and performs no Cargo write even when a `stablekey` is
  present (§5).
- **Entity identity is `stable_key`.** Every clean-DB entity table has
  `stable_key TEXT PRIMARY KEY`; `Page` and `Name` are both non-unique (e.g. two
  `Regrowth` spells share a page+name).
- **Freshness is driven deterministically.** `wiki_deploy/refresh.py` issues
  `action=purge&forcelinkupdate=1` on `embeddedin` dependents.
  `cargorecreatetables` is driven by the local-harness `wiki-dev/cargo_check.py`;
  production Cargo-recreate automation remains a Phase 7 deliverable and must run
  as a privileged account.
- **Deploy identities:** article deploys and uploads run as
  `WoWBot@erenshor-wiki` (bot-password; bot/edit/upload rights, rate-limited on
  rapid undo). Repo-page deploys support `--assertion user` for
  `WoWMuch@CargoProbe`, which lacks the bot right. Interface deploys run as
  `WoWMuch@InterfaceDeploy`.
- **`WoWBot` cannot create or recreate Cargo tables.** Verified 2026-07-30: its
  groups are `autopatrol`, `bot`, `user`, `autoconfirmed`, `emailconfirmed`, and its
  only Cargo rights are `runcargoqueries` and `runcargoapiqueries`. On this wiki
  `recreatecargodata` is granted only to `sysop`, `staff`, `staff-bot`,
  `global-sysop`, `titan`, and `librarian-admin`. `WoWMuch` is `sysop` plus
  `interface-admin` and holds `recreatecargodata` and `deletecargodata`. Table
  creation and every schema change therefore run as `WoWMuch` or an equivalently
  privileged account, never as the deploy bot. Whether the configured
  `WoWMuch@InterfaceDeploy` bot password carries the grant required for
  `cargorecreatetables` is the one untested part of this gate.
- **Relationship source tables exist in the clean DB** (§8): `loot_drops`,
  `item_drops`, `crafting_recipes`, `crafting_rewards`, `item_classes`,
  `spell_classes`, `character_spawns`, `character_attack_spells` + siblings,
  `spell_created_items`.

### 2.1 Cargo platform constraints (wiki.gg / LIBRARIAN)

These shape every Cargo decision below:

- **One declaring owner per Cargo table.** Cargo guidance is one `#cargo_declare`
  (the schema owner) per table; any other storing template `#cargo_attach`es it. Live
  wiki.gg probes confirmed nested hidden storage templates store the item's three
  tables from one page, so the helper attach-trick is not required. Each table has
  exactly one **declaring** owner — the target of `cargorecreatetables`:
  `Items`←`Item`, `ObtainedFrom`←`ItemObtainedFromStore`, `UsedIn`←`ItemUsedInStore`,
  and the `Spawns`/`CharacterAbilities` junctions ← their character-side store
  templates. Community row templates (`{{ItemSource}}`/`{{SpawnPoint}}`, §9) are
  additional **storing** contributors that attach — never redeclare —
  `ObtainedFrom`/`Spawns` to add `Origin=community` rows.

- **Lua-owned presentation has two deployable stylesheet paths.** Verified
  2026-07-30: `TemplateStyles` 1.0 and `TemplateStylesExtender` 2.0.0 are installed,
  the `sanitized-css` content model is available on unprotected `Template:*/styles.css`
  subpages, and the community already ships `Template:ClassPill/styles.css`. The
  gadget route is also deliverable — the MediaWiki namespace is `editinterface`-protected,
  but `MediaWiki:Gadget-erenshor.css` and `MediaWiki:Gadgets-definition` are deployed
  through the configured `WoWMuch@InterfaceDeploy` interface-admin account by
  `wiki deploy-interface`. What remains is integration, not platform capability: the
  Lua modules build markup through `mw.html` but nothing emits a `<templatestyles>`
  tag, no CSS source is owned for Lua markup, and rendered parity is unproven.
- **Recreate only for schema changes; routine refresh reparses.** `#cargo_declare`
  changes nothing on save — a table is (re)created in a separate step. Once a table
  exists, reparsing a page rewrites that page's rows in place, so a data-only refresh
  (same schema) needs no recreate: regenerate the modules, push, and reparse the
  affected pages. `cargorecreatetables` (a template's tables) and `cargorecreatedata`
  (one table, repopulating from every contributing page) are for first creation and
  schema changes only, and run one job per page, so completion is polled. A
  large-table recreate should use a replacement table (§10) to avoid the empty-table
  window.
- **Native Lua `cargo_store`/`cargo_declare` are disabled.** Rows are written through
  the `#cargo_store` parser function via `frame:callParserFunction`, centralized in
  `Module:Erenshor/Cargo` (`buildArgs` casts a field list, booleans → `yes`/`no`, nil
  omitted; `store` hands the map to the parser function). One call per row; loop for
  multiple rows.
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
- **The local harness runs stock upstream Cargo, not wiki.gg's LIBRARIAN fork** —
  it clones `mediawiki/extensions/Cargo` (`wiki-dev/Dockerfile`). Green harness
  results prove row shape and local recreate coverage; live storage-shape and
  recreate-data behavior are covered by the live probe/runbook, not by the
  harness.

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
6. **Two non-overlapping render paths with separate selection and identity (§5).**
   Exact `lua=1` selects the generated Lua/Cargo path. `stablekey` identifies the
   entity only after that selection. Every invocation without exact `lua=1` uses
   the verbatim legacy path and performs no Cargo write, even if it carries a
   `stablekey`.

## 4. Entity identity & multi-entity pages

A page = N entities, each a distinct `stablekey`. The thin page carries one
`{{<Type>|stablekey=…}}` stanza per entity; each stores its own Cargo row(s)
sharing `Page`/`Name` but distinct `StableKey`. Invariant (tested): two same-name
entities on one page store as two rows distinguished only by `StableKey`, and both
infoboxes render. The smoke checker keys rows on `(Page, StableKey)` and detects
duplicate StableKeys; this extends to every new table.

## 5. Dual-path cutover architecture

The cutover must never leave the wiki broken, even for the hour-plus a
rate-limited full deploy takes. Every Item, Character, Spell, Skill, Stance, Quest,
and Zone template therefore has two completely separate render paths selected only
by an exact flag check:

```wikitext
<includeonly>{{#ifeq:{{{lua|}}}|1|
  {{#if:{{{stablekey|}}}|
    <!-- GENERATED PATH: resolve stablekey, render from the data module,
         and invoke cargoStore. -->
  |
    <!-- Existing missing-data diagnostic. No cargoStore. -->
  }}
|
  <!-- LEGACY PATH: the original live inline-parameter body, embedded verbatim.
       No generated-data #invoke and no cargoStore. -->
}}</includeonly>
```

Permanent selector and identity invariant:

- **Exact `lua=1` is the only generated-path selector.** No other `lua` value and
  no identity field selects that path.
- **`stablekey` is identity data only.** Its presence never selects a rendering
  path.
- **No exact flag means verbatim legacy behavior.** Without exact `lua=1`, the
  invocation renders the legacy branch and performs no `cargoStore` call, even if
  `stablekey` is present.
- **The generated path fails closed on identity.** With exact `lua=1`, a valid
  `stablekey` is required. A missing or invalid key emits the existing missing-data
  diagnostic, stores no Cargo row, and never falls back to legacy rendering.
- **The paths never mix.** Generated-path rendering reads only resolved module data
  plus declared overrides. Legacy rendering reads inline parameter wikitext only.
- **The contract applies uniformly to all seven entity types.** Spell and Skill use
  the same dual path as Item, Character, Stance, Quest, and Zone. They are not
  unconditional Lua templates.

This produces the required four-case matrix:

| Invocation | Render path | Cargo behavior |
|---|---|---|
| no `lua=1`, no key | legacy | no store |
| exact `lua=1`, valid key | generated Lua | store resolved rows |
| exact `lua=1`, missing or invalid key | missing-data diagnostic | no store |
| key without exact `lua=1` | legacy | no store |

**Production presentation rules:** wikitable markup must begin at line start, so
parameterized equipment rendering composes expanded legacy templates with
`frame:expandTemplate` and newline-joined assembly. Do not wrap expanded wikitext
in `mw.html`, `frame:preprocess`, or `#tag:div`. Those wrappers prevent the
wikitable markup from parsing in production.

**Current production boundary.** Equipment articles may carry a `stablekey` for
parameterized tooltips and interactive-map links while remaining on the legacy
infobox path. Zero articles currently pass exact `lua=1`. Quest, Zone, and Stance
are legacy-only on live, Character has a key-selected split that must be corrected,
and Spell and Skill are unconditional Lua in the repo and must gain the uniform
flag-selected dual path before any canary.

Incremental cutover sequence: deploy the uniform dual-path templates and modules
while every article stays legacy, create and verify Cargo, exercise both branches,
then add exact `lua=1` to one guarded article at a time. Once every page of one type
has converted and passed its retirement gate, delete that type's legacy branch and
retire its Jinja2 generator. The dual-path template is a temporary scaffold whose
legacy half is deleted type by type.

## 6. Thin-page article generation

The remaining cutover mechanism for full conversion is a thin-page generator (in
`wiki_lua`, deployed via `wiki_deploy`) that produces the thin article wikitext
for every entity and uploads it via safe-edit:

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
| `mining` | `mining_nodes`+`mining_node_items` | Mining-node StableKey, displayed through its connected ZoneLink |
| `fishing` | `water_fishables` (day/night → `SourceCondition`) | Water StableKey, displayed through its connected ZoneLink |
| `item_bag` | `item_bags` (ground pickups) | Item-bag StableKey, displayed through its connected ZoneLink |
| `starting` | `class_starting_items` (export from `CharSelectManager`) | ClassLink |
| `community` | `{{ItemSource}}` (§9) | null — free text in `SourceText` |

World-point sources carry their smallest stable identity. Mining nodes, waters,
and item bags are joined to their connected zone through
`mining_nodes.scene = zones.scene_name`, `waters.scene = zones.scene_name`, or
`item_bags.scene = zones.scene_name`; the zone is a display-resolution target,
not a replacement for the source identity. Deduplicate mining to one row per
item×mining-node, item bags to one row per item×item-bag, and fishing to one row
per item×water×condition.

**`UsedIn`** — what an item is consumed for (item → consumer): `ItemKey`, `UseType`,
`TargetKey`, `Quantity`, `Slot`:

| `UseType` | from | `TargetKey` → |
|---|---|---|
| `craft_material` | `crafting_recipes` | ItemLink (recipe) |
| `quest_requirement` | `quest_required_items` | QuestLink |
| `upgrade_material` | smithing quality upgrade consumables from the heterogeneous `smithing.upgrade_ids` code fact: `31377423` (Mold: An Otherwordly Box) + `46289586` (Planar Stone fuel) | ItemLink (recipe) |
| `blessing_removal_material` | smithing blessing-removal consumable from `smithing.upgrade_ids`: `2298018` (Inert Diamond) | ItemLink (recipe) |

`craft` (result → `ObtainedFrom`) and `craft_material`/`upgrade_material`/
`blessing_removal_material` (inputs → `UsedIn`) make dedicated crafting tables
unnecessary; the recipe item renders its forward ingredient/result list from its Lua
module, while `ObtainedFrom`/`UsedIn` are the reverse indices.

`smithing.upgrade_ids` is a `string_constants` fact over `Smithing.Combine`, so it
intentionally bundles heterogeneous string literals. Consumers must classify the set
by game semantics, not map every ID to `upgrade_material`: `2265228` (Merging Vessel)
is the distinct item-merge/forge mechanic (the merge branch of `Smithing.Combine`,
build 24362350) and remains deferred until the forging mechanic is
documented/modelled.

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
  `character_attack_skills`; owner = character): `CharacterKey`, `AbilityKey`, `AbilityUsage` (`Usage` is reserved by the local Cargo SQL fork). Death-event `ShoutOnDeath` text is not an ability and is deferred to a dedicated ordered table.
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

**Empty query results are a rendering state, not a failure.** A reverse-query section
whose Cargo query returns nothing renders as absent or as an explicit "none recorded"
line, never as an error, a broken table, or a Lua stack trace. This keeps a page
readable when its table does not exist yet, when a recreate is mid-flight, or when a
replacement table has not been switched in. It is the property that makes Cargo an
additive layer rather than a hard dependency of every article.

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
`stablekey=` (Page/Name can't disambiguate multi-entity pages), `#cargo_attach`es
the relationship table its declaring owner already created (§2.1) — it never
redeclares the schema — `#cargo_store`s one row with `Origin=community`, and
validates `stablekey` against the data module via `mw.loadData` (unresolved →
tracking category).

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
touch article pages at all (§6). Community rows survive refreshes because they live on
their own pages: a routine (same-schema) refresh just reparses those pages like any
other, and a schema-change recreate's `cargorecreatedata` cycles every page that
contributes to the table — generated and community alike — so both come back (§10).
Community-row repopulation is exercised with the Phase 4 community layer; the
storage-validation probe covered generated-owner recreation only.

## 10. Caching & freshness

- Cargo writes rows on **page parse**, not on declare-save. A cross-page query is
  only as fresh as the querying page's last parse (MW HTML cache; ≤24h or purge).
  Modules share templates' link-tracking, so editing `Data/*` enqueues
  `refreshLinks` (job queue, `$wgJobRunRate` caveat).
- Routine (same-schema) refresh does not recreate: push the `Data/*` modules and
  reparse dependents with `purge_pages(force_link_update=True)` (run the job queue as
  part of deploy); each page's `#cargo_store` rewrites its rows in place. Recreate only
  when the schema changes — `cargorecreatetables` (structure) + per-table
  `cargorecreatedata` (repopulate), polling row counts. For a large-table recreate the
  documented no-downtime path is a replacement table (`createReplacement=1`): the old
  table keeps serving queries while `__NEXT` fills, then an admin switches it in at
  `Special:CargoTables` (the switch-in has no API).
- Ordering: a queried row must exist before the querying page parses — push the storing
  pages (and, on a schema change, recreate) before purging the dependents that read them.
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

Links render from stored names via `Module:Erenshor/Link`; Cargo never stores
markup. All-6-classes → "All" is display-only. Reverse-relationship sections
render from Cargo queries (§8.1); own-entity fields from the Lua module.

**Presentation parity is a conversion gate.** Lua renderers must preserve the
restored legacy display contract before a type converts: wikilinked spell names,
`.png` icon suffixes, tick-to-second cast times, zero-as-blank optional fields,
the `XPBonus` percentage rule, and resolved item/character drop rows with
guaranteed-drop and drop-rate display. The item infobox consumes resolved
`SourceInfo.item_drops` tuples (`ItemLink`, probability, `is_guaranteed`); the
obsolete `ItemDropInfo` value object is deleted. Character-side
drop-rate/guaranteed-drop rendering remains in progress. Prove parity against
live pages; keyed `LootDropInfo` remains the Lua data shape while resolved
display rows feed the legacy Jinja path.

## 13. Editor & template documentation

First-class docs on the installed `TemplateData` + `/doc` subpage stack
(`{{Documentation}}` in each template's `<noinclude>`): a `<templatedata>` block
per template (param label/description/type/required/example, surfaced in
VisualEditor), purpose + usage examples, related templates. This is the target, not
the current state: `/doc` subpages exist only for the link templates, only
`Character` invokes `{{Documentation}}`, and no entity template carries a
`<templatedata>` block. Per-entity-type
editing guides explain which facts are generated vs. community-editable, how to
add an `{{ItemSource}}`/`{{SpawnPoint}}` row (including finding the `stablekey` in
page source), and the precedence rules. Supersedes the ad-hoc doc pages.

## 14. Testing

- Multi-entity: same-name two-spell and two-character pages → two rows, distinct
  StableKey, shared Page; both infoboxes render.
- Selector matrix (§5): no flag stays legacy and stores nothing, exact `lua=1`
  plus a valid key renders generated data and stores rows, exact `lua=1` plus a
  missing or invalid key emits the diagnostic and stores nothing, and a key without
  the flag stays legacy and stores nothing. Exercise all four cases for Item,
  Character, Spell, Skill, Stance, Quest, and Zone.
- No markup in Cargo: assert stored values are names/numbers, not `<span>`/`[[…]]`.
- Reverse queries: item "dropped by", ability "used by", "what a class can learn".
- Community layer: `{{ItemSource}}` stores an `ObtainedFrom` row and `{{SpawnPoint}}`
  a `Spawns` row, both `Origin=community`, both surviving a simulated redeploy and
  appearing in the same unified query as generated rows; unresolved `stablekey` →
  tracking category.
- **Renderer testcases:** Scribunto renderers use real frames created through
  `mw.getCurrentFrame():newChild`; frame mocks are prohibited.
  `Module:*/testcases` pages are excluded from production deploy manifests.
- Thin-page generator: emits correct stanzas per entity; multi-entity = multiple
  stanzas; community overrides + sections preserved across a regenerate.
- Extend `wiki-dev/smoke/cargo.py` + fixtures + `cargo_check.py` recreate set to
  every new table.
- Treasure-chest spawns: a `Lost Treasure (…)` chest character stores `treasure_chest`
  `Spawns` rows for its pickable locations, and a treasure-hunting item's `drop` row
  resolves to a chest page that now shows those locations.
- **Harness limitation (explicit):** `wiki-dev` runs stock upstream Cargo, so it
  cannot exercise wiki.gg's LIBRARIAN fork directly. What it *does* test is recreate
  coverage — rows stored by a page whose template is not attached to the table vanish
  on `cargorecreatetables`. Live storage-shape, stale-row lifecycle, multi-entity
  identity, and `cargorecreatedata` job-queue behavior were validated by the live
  probe (`2026-07-09-wiki-cargo-storage-validation`); nested hidden storage is the
  selected contract and no attach-trick is required.

## 15. Dependency sequence

The executable sequence is owned by
`2026-08-01-wiki-cargo-cutover-foundation`. The technical contracts remain in this
architecture spec and its sibling parity, schema, and deploy/sync specs.

1. Approve `2026-08-01-wiki-render-parity-gate`,
   `2026-07-30-wiki-cargo-schema-revision`, and
   `2026-07-30-wiki-deploy-sync-discipline`.
2. Implement the local parity instrument and its field-loss regression.
3. Apply the exact `lua=1` selector matrix to all seven templates.
4. Correct schema declarations and generated payloads, including the Character
   module size gate and the `ItemEffects` junction.
5. Implement reusable size, protection, rights, drift, sandbox, guarded-write,
   rollback, and queue controls.
6. Deploy the missing data modules and adopt live `Template:Ability` byte for byte
   while all production articles remain on legacy paths.
7. Create production Cargo tables through the privileged replacement-table
   procedure, then verify schemas and row counts.
8. Run local and TemplateSandbox parity canaries for all seven types and all
   required selector and multi-entity cases.
9. Publish a foundation-completion report proving zero failed cases, zero required
   `not_exercised` cases, and zero converted production articles.

Only that report unlocks `2026-07-11-wiki-article-cutover`. Article conversion then
runs per type in the order Stance, Zone, Spell and Skill, Character, and Item. Quest
article conversion remains governed by `2026-07-31-wiki-quest-article-strategy`.
Community-row implementation remains part of this architecture but is not a
prerequisite for first production Cargo creation or article conversion.

## 16. Key decisions

- Exact `lua=1` is the only generated Lua/Cargo selector for all seven entity
  templates. `stablekey` is identity only. Without exact `lua=1`, the verbatim
  legacy branch renders and stores nothing even when a key is present. With exact
  `lua=1`, a missing or invalid key diagnoses and stores nothing without falling
  back to legacy.
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
