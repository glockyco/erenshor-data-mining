# Wiki Cargo Data Architecture

Status: IN PROGRESS — approved spec; implementing per §13 sequencing. See Progress.
Date: 2026-06-04
Scope: the repo-owned MediaWiki (LIBRARIAN/Cargo) data layer — entity tables,
relationship tables, the community-contribution layer, freshness, and removals.

## Progress

Each increment lands via TDD + local smoke + the full commit gate.

- [x] Phase 0 — export wiki-relevant Spell flags (`GrantInvisibility`,
  `CannotInterrupt`, `JoltSpell`, `NoResonate`). Commits `79f3d71f`, `f66c287d`.
- [x] Phase 1a — drop `Items.ClassLinks` rendered markup; render class links at
  display from `Classes`. Commit `9bb6495a`.
- [x] Phase 1b — Characters §5.1: `Faction`→WorldFaction stablekey (enriched
  faction ref), `Zones`→bare names, drop `SpawnChance` from Cargo.
- [x] Phase 1c — multi-entity regression fixture (same-name two-`character`
  page `Dire Wolf`: two Cargo rows, shared Page, distinct StableKey).
- [x] Phase 2 prereq A — convert spell/skill times to seconds at generation
  (cast `/60`, duration `*3`, skill cooldown `/60`, per the game C#); remove all
  tick storage/display from the wiki. See `2026-06-06-wiki-cargo-phase2-abilities.md`.
- [ ] Phase 2 prereq B — split `{{Ability}}`→`{{Spell}}`/`{{Skill}}`, retire
  `Template:Ability` + `Module:Erenshor/Ability` dispatcher.
- [ ] Phase 2 — abilities base + `Spells`/`Skills`/`Stances` detail + `AbilityClasses`
  (symmetric three-template Cargo via `#cargo_attach`).
- [ ] Phase 3 — relationship junction tables + `Spawns` (§6) + item→ability scalar
  columns + reverse-query rendering.
- [ ] Phase 4 — community layer (`ItemSource`/`SpawnPoint`, `Origin`, validation).
- [ ] Phase 5 — freshness/orphans (recreate + refresh sets, drop-and-recreate).
- [ ] Phase 6 — editor/template documentation (TemplateData + `/doc`).

## 1. Purpose

Define how generated game data and community contributions coexist in Cargo so
that wiki list/overview/cross-reference pages are correct, queryable, and robust
across game-version redeploys. This consolidates every decision reached in the
2026-06-04 design discussion: semantic identity, multi-entity pages, the
spell/skill/stance ("abilities") schema, relationship modeling, caching,
removals, and community-entered non-extractable relationships.

The current model is preserved and extended, not replaced: **generated/raw data
lives in `Module:Erenshor/Data/*` Lua modules; on-page infoboxes render from
those modules and `#cargo_store` on parse.** This spec adds relationship tables,
a community authoring layer, and the freshness/removal discipline around them.

Non-goals / out of scope:
- Raw-data TOML overrides (author-only, applied pre-generation to correct the
  source-of-record). A separate mechanism; untouched here.
- The quest guide / entity graph (`graph_overrides`) — a different system.
- Per-entity anchors / deep-linking and display "qualifiers" — explicitly
  dropped during design as unnecessary (lists self-disambiguate by data columns;
  links are page-level).

## 2. Grounding (verified facts this design depends on)

- **Wiki stack (live `Special:Version`):** LIBRARIAN 4.21.0 (wiki.gg's Cargo
  fork), Scribunto, ParserFunctions, ParserPower, Arrays, Variables, Portable
  Infobox, LabeledSectionTransclusion. **No Page Forms, no Semantic MediaWiki,
  no Data Transfer, no External Data.** Community data entry is therefore raw
  wikitext templates only — no form UI is available.
- **Entity identity is `stable_key`.** Every entity table in
  `variants/main/erenshor-main.sqlite` has `stable_key TEXT PRIMARY KEY`. A wiki
  page hosts one *or more* entities (e.g. `Regrowth` = two spells with identical
  name; same-name character variants). `Page` and `Name` are both non-unique.
- **The resolve/store path already keys on stablekey.** `Module:Erenshor/*`
  `resolve` requires an explicit `stablekey` arg (no page-title fallback);
  `cargoStore` runs once per infobox transclusion, storing `Page` (shared) +
  `StableKey` (unique). The smoke checker (`wiki-dev/smoke/cargo.py`) already
  keys rows on `(Page, StableKey)` and detects duplicate StableKeys.
- **Page generation is multi-entity aware.** `wiki_lua` page generation groups
  entities by `wiki_page_name` and emits one infobox per entity.
- **Freshness is already driven deterministically.** `wiki_deploy/refresh.py` /
  `client.purge_pages(force_link_update=True)` issues `action=purge&forcelinkupdate=1`
  on dependents discovered via `embeddedin` (synchronous LinksUpdate; chosen
  over no-op edits, which perform no LinksUpdate). `wiki-dev/cargo_check.py`
  drives `cargorecreatetables`.
- **Relationship source tables exist in the clean DB** (see §6 for exact
  columns): `loot_drops`, `item_drops`, `crafting_recipes`, `crafting_rewards`,
  `item_classes`, `spell_classes`, `character_spawns`, `character_attack_spells`
  and siblings, `spell_created_items`.

## 3. Core principles

1. **StableKey is the only identity.** All Cargo joins, dedup, and reverse
   lookups use `StableKey`. Never key, join, or dedup on `Page` or `Name`.
2. **Storage of record depends on provenance.** For *generated* data the Lua
   data module is the full record and Cargo is a queryable projection of it (the
   infobox renders own-entity fields straight from Lua; Cargo carries only what
   list/overview/reverse queries filter, sort, or join on). For *community* data
   there is no Lua module — it is authored on-page and persists only to Cargo, so
   **Cargo is the system of record** for those rows. "Queryable subset" describes
   the generated projection, not a cap on what community data may store.
3. **Never store rendered links or markup in Cargo.** Store names/page-titles
   and numbers; render links at the display boundary via `Module:Erenshor/Link`.
   (Fixes today's `ClassLinks=Wikitext`, `Zones=Text`, `Faction=String`
   markup-bearing fields.)
4. **One table per relationship shape; store forward once, query reverse.** The
   "many" side is its own table keyed by the owner's StableKey, with the pair's
   attributes as columns. Reverse direction is always a query, never a second
   stored copy.
5. **Two curation layers, distinguished by provenance, with layered precedence.**
   Generated rows (deploy-owned, regenerated every deploy) and community rows
   (wiki-owned, never overwritten by the generator) share tables via an `Origin`
   column (`generated` | `community`). Community contributions are both
   *additive* (facts the exporter cannot produce — global drops, missed spawn
   points) and *corrective* (overrides of a generated value). Precedence is the
   golden-record rule: where they overlap, community wins; where they add, they
   stand alone. The existing scalar article-param override path
   (`applyRootOverrides`, e.g. `othersource`) already implements this for infobox
   fields and is the model for relationship-level overrides.

## 4. Entity identity & multi-entity pages

A page = N entities, each a distinct `stablekey`. The per-entity infobox
(`{{Item|stablekey=…}}`, `{{Ability|stablekey=…}}`, `{{Character|stablekey=…}}`,
`{{Stance|stablekey=…}}`) both renders from the Lua module and `#cargo_store`s
its row(s). Multiple entities on a page produce multiple Cargo rows sharing
`Page`/`Name` but distinct `StableKey`.

Invariant (tested): two same-name entities on one page store as two rows
distinguished only by `StableKey`, and both infoboxes render. The smoke checker
already enforces `(Page, StableKey)` keying and duplicate-StableKey detection;
this is extended to every new table.

## 5. Entity / detail tables

### 5.1 Fix existing tables (remove markup, model lists correctly)

`Items`:
- **Drop `ClassLinks` (`Wikitext`).** It stores rendered
  `<span…>[[Paladin]]</span>` markup. Overview rows render class links at display
  time from `Classes` via `Module:Erenshor/Link`.
- Keep `Classes = List (,) of String` (bare class names, from `item_classes`).
- **Replace the `Overview*` ability columns.** Today `OverviewProcAbility`,
  `OverviewWornAbility`, `OverviewClickAbility` store the resolved *page title*
  (via `abilityPage()`), and `OverviewProcAbility` further *collapses* three
  distinct game relationships (`WeaponProcOnHit`, `WandEffect`, `BowEffect`) into
  one slot disambiguated by a derived `OverviewProcTrigger` string. Both are
  wrong: a Page reference is ambiguous on multi-entity ability pages, and the
  collapse conflates distinct relationships while omitting others. Model each
  item→ability link (all 1:1 from the item side per `Item.cs`) as its own
  domain-named scalar column storing the ability **StableKey** — see §6.

`Characters`:
- **Replace the `Zones`/`SpawnChance` hack with a `Spawns` table (§6).** Today
  `Zones` is an unqueryable `<br>`-joined link blob and `SpawnChance` a
  `<br>`-joined display string. Character spawning is multi-source and far richer
  than a flat zone list, so it is modeled properly in the `Spawns` table (§6) and
  the infobox renders spawns from it. The Characters table keeps an optional
  derived `Zones = List (,) of String` (distinct zone names) only as a cheap
  filter convenience.
- **`Faction`: store the WorldFaction `stablekey`** (`my_world_faction_stable_key`,
  joinable to the `factions` table), not a page, bare name, or `<span>` markup.
  Factions are stable-keyed; this is the only joinable faction. The combat
  `Faction` enum (`my_faction`, aggressive/allied lists) is name-only and not a
  faction link (§6).

All-6-classes → "All" is a display-only collapse in `Module:Erenshor/Link`
rendering (store all class names; render "All" when the set is the full roster of
6: Arcanist, Druid, Duelist, Paladin, Reaver, Stormcaller).

### 5.2 Abilities: thin base + per-type detail (class-table-inheritance)

A single wide `Abilities` table is rejected (sparse single-table inheritance:
~30 spell/skill columns null on every stance, ~11 stance columns null on every
spell/skill). Instead:

`Abilities` (base; every spell/skill/stance stores exactly one row):
`StableKey`, `Page`, `Name`, `AbilityType` (`Spell`|`Skill`|`Stance`), `Image`,
`Description`. This is the cross-type "all abilities" / search surface.

Per-type detail tables, joined to the base on `StableKey`, written from the same
page via the **attach trick** (one template declares/attaches; the store module
writes base + detail):

- `Spells` (from `spells`): `StableKey`, `Page`, `Name`, `Type`, `Line`,
  `RequiredLevel`, `ManaCost`, `CastTimeSeconds` (`spell_charge_time`),
  `CooldownSeconds` (`cooldown`), `DurationTicks` (`spell_duration_in_ticks`),
  `Range` (`spell_range`), `DamageType`, `TargetDamage`, `TargetHealing`,
  `CasterHealing`, `ShieldingAmt`, `SimUsable`, `SelfOnly`, `GroupEffect`,
  `Aggro`, `CrowdControl` (`crowd_control_spell`), `GrantInvisibility`,
  `CannotInterrupt`, `Jolt` (`jolt_spell`), `NoResonate`, plus single-reference
  relation columns storing ability StableKeys — `StatusEffect`
  (`status_effect_to_apply_stable_key`), `AddProc` (`add_proc_stable_key`),
  `PetToSummon` (`pet_to_summon_stable_key`).
- `Skills` (from `skills`): `StableKey`, `Page`, `Name`, `Type` (`type_of_skill`,
  with `Innate`→public "Passive"), `CooldownSeconds` (`cooldown`), `Range`
  (`skill_range`), `SkillPower`, `PercentDmg`, `DamageType`, `Require2H`,
  `RequireDualWield` (`require_dw`), `RequireBow`, `RequireShield`,
  `RequireBehind`, plus single-reference relation columns storing StableKeys —
  `StanceToUse` (`stance_to_use_stable_key`), `EffectToApply`
  (`effect_to_apply_stable_key`), `CastOnTarget` (`cast_on_target_stable_key`),
  `SpawnOnUse` (`spawn_on_use_stable_key`).
- `Stances` (from `stances`; small, all columns real): `StableKey`, `Page`,
  `Name`, `MaxHpMod`, `DamageMod`, `ProcRateMod`, `DamageTakenMod`,
  `SelfDamagePerAttack`, `AggroGenMod`, `SpellDamageMod`, `SelfDamagePerCast`,
  `LifestealAmount`, `ResonanceAmount`, `StopRegen`.

`Page`/`Name` are intentionally denormalized onto detail tables so per-type list
pages need no base join; the base remains the source of truth for cross-type
queries. `Spells`/`Skills` are kept separate (distinct DB tables, distinct
tooltips, skills lack the caster stat block and carry weapon-requirement flags +
per-class levels).

Field coverage was verified against `Spell.cs`/`Skill.cs`/`Stance.cs`: skills and
stances are fully exported; spells have four wiki-relevant booleans missing from
the DB — `GrantInvisibility` (target invisibility), `CannotInterrupt`
(uninterruptible cast), `JoltSpell` (interrupt/knock), `NoResonate` (suppresses
the resonate proc chain). These are **exported first** (Phase 0, §13) so the DB,
the Lua module, and the `Spells` table above all include them in one pass — there
is no benefit to deferring a DB change we need regardless. `ForHardEncounters` and
`HardcodedUseCase` stay unexported (NPC-AI/engine internals with no display
value). The detail tables otherwise carry the curated *queryable* subset (the
full per-entity field set lives in the Lua module for the infobox); the
single-reference relation columns follow the item→ability 1:1-scalar-StableKey
rule and are reverse-queryable (e.g. "skills that grant stance X").

## 6. Relationship (junction) tables

One table per relationship shape, FK by `StableKey`, attributes as columns,
`Origin` provenance column. Stored forward on the owner page; reverse is a query.
Source columns are the real DB columns.

- `Drops` (from `loot_drops`; owner = character): `Character`, `Item`,
  `DropProbability`, `ExpectedPerKill`, `IsGuaranteed`, `Zone`, `Rarity`
  (derived from `is_common/uncommon/rare/legendary/ultra_rare/unique`), `Origin`.
  Reverse "what drops Item X" = `where Item=X`.
- `ContainerDrops` (from `item_drops`; owner = source item): `SourceItem`,
  `DroppedItem`, `DropProbability`, `IsGuaranteed`, `Origin`.
- `CraftingMaterials` (from `crafting_recipes`; owner = recipe item): `Recipe`,
  `Material`, `Quantity` (`material_quantity`), `Slot` (`material_slot`),
  `Origin`. Reverse "used to craft" = `where Material=X`.
- `CraftingRewards` (from `crafting_rewards`; owner = recipe item): `Recipe`,
  `Reward`, `Quantity` (`reward_quantity`), `Slot` (`reward_slot`), `Origin`.
- `AbilityClasses` (from `spell_classes` + the six `*_required_level` skill
  columns; owner = ability): `StableKey`, `Class`, `RequiredLevel`, `Origin`.
  `RequiredLevel` is **resolved per (ability, class)**: for spells, broadcast the
  spell's single `required_level` to each class in `spell_classes`; for skills,
  the per-class `<class>_required_level`. Reverse "what can a Druid learn by
  level N" = `where Class='Druid' AND RequiredLevel<=N`.
- `CharacterAbilities` (from `character_attack_spells`, `character_buff_spells`,
  `character_cc_spells`, `character_heal_spells`, `character_group_heal_spells`,
  `character_taunt_spells`, `character_attack_skills`; owner = character):
  `Character`, `Ability`, `Usage` (`attack`|`buff`|`cc`|`heal`|`group_heal`|
  `taunt`|`attack_skill`), `Origin`. Reverse "ability used by characters" =
  `where Ability=X`.
- `Spawns` (from `character_spawns`, plus `character_chained_spawns` expanded per
  `docs/superpowers/specs/2026-05-28-dynamic-spawn-coverage-design.md`; owner =
  character): `Character`, `Zone`, `Scene`, `X`, `Y`, `Z`, `SpawnChance`,
  `NightSpawn`, `SpawnUponQuestComplete` (quest stablekey), `LevelMod`,
  `RareNpcChance`, `SpawnType`, `Origin`. `SpawnType` is the multi-source
  discriminator from the spawn-coverage work: `spawn_point` | `direct` |
  `trigger` | `event_script` | `chained` (carried by
  `character_spawns.source_script`; NULL = spawn point). This replaces the flat
  character `Zones`/`SpawnChance`. Upgrade path: conditional/event spawns (e.g.
  Astra, only after interactions) already arrive as `event_script` rows via the
  dynamic-spawn catalog; the deferred Category-C zone-wide random spawners get a
  future `zone_random_spawns` table + a "may appear in {zone}" renderer.
  Community-added spawns the exporter still misses use `{{SpawnPoint}}` (§7) into
  this same table with `Origin=community`.

Faction relationships are deliberately **not** one shape (`Character.cs` + DB).
Only the **WorldFaction** is stable-keyed/joinable: `my_world_faction_stable_key`
(the displayed `Faction`, §5.1) and `character_faction_modifiers.faction_stable_key`
(a `FactionModifiers(Character, Faction, Modifier)` junction, if modeled). The
combat `Faction` enum — `my_faction`, `character_aggressive_factions.faction_name`,
`character_allied_factions.faction_name` — is stored by **name only, not joinable**;
render it as plain text, never a faction-page link.

**Item→ability links are 1:1 scalar columns on `Items`, not junction tables.**
`Item.cs` exposes each as a single reference, so each is its own domain-named
column storing the referenced ability's **StableKey** (String), never a Page and
never a collapsed slot:

| Column | `Item.cs` field | Companion |
|---|---|---|
| `TeachesSpell` | `TeachSpell` | — |
| `TeachesSkill` | `TeachSkill` | — |
| `WeaponProc` | `WeaponProcOnHit` | `WeaponProcChance` |
| `WandEffect` | `WandEffect` | `WandProcChance` |
| `BowEffect` | `BowEffect` | `BowProcChance` |
| `WornEffect` | `WornEffect` | — |
| `ClickEffect` | `ItemEffectOnClick` | — |
| `SkillUse` | `ItemSkillUse` | — |
| `Aura` | `Aura` | — |

Reverses ("taught by", "items with this worn effect/proc/aura") are queries on
the relevant column, keyed by the ability StableKey. The overview "Proc" cell is
display-time coalescing in the row template (pick whichever of weapon/wand/bow is
set; derive the trigger — shield→"on bash", wand→"on cast", else "on attack" —
from item type), not a stored conflated column or trigger string.

### 6.1 Forward-store / reverse-query rendering

Reverse and cross-page relationships (drops on an item page, "used by" on an
ability page, "taught by", etc.) are **rendered via Cargo query** against the
junction tables (§6) or, for item→ability links, the scalar reference columns on
`Items` — in list pages and in the infobox — and the denormalized reverse arrays
(`usedBy`, `itemsWithEffect`, `source`) are **removed from the Lua data modules**.
This makes Cargo the single source, eliminates
duplication, and makes removals correct (no ghost rows). Own-entity scalar
fields continue to render from the Lua module. Deploy ordering already supports
this: push pages → recreate Cargo → purge/reparse dependents.

**Confirmed:** store forward, query reverse — drop the denormalized arrays
(Leaguepedia's model; single-source correctness over infobox-query micro-cost).

## 7. Community contribution layer (non-extractable relationships)

Some facts are not auto-extractable and are community-curated on the wiki today:
"global" item drops not on any enemy loot table, and spawn points/conditions the
export pipeline misses. These MUST remain community-editable on-wiki, survive
every redeploy, and be queryable alongside generated rows.

Because there is no Page Forms, entry is **raw multiple-instance row templates**.
Each row template:
- Takes `stablekey=` (matching the existing infobox param name) to identify the
  entity — Page/Name cannot, on multi-entity pages.
- `#cargo_store`s one row with `Origin=community` into the relevant table.
- Validates `stablekey` against the Lua data module via `mw.loadData`; if it does
  not resolve to an entity on the page, drops the row into a tracking category
  (e.g. `Pages with unresolved community <X>`), mirroring existing "missing data"
  categories. This is the safety net Page Forms validation would otherwise give.

Row templates (fields grounded in DB columns, no invented names):
- `{{ItemSource|stablekey=item:…|source=…|drop_probability=…|zone=…|notes=…}}` —
  global/other obtain methods. Generalizes the existing free-text `othersource`
  field into queryable rows. Stored in `OtherItemSources`
  (`StableKey`, `Source`, `DropProbability`, `Zone`, `Notes`, `Origin=community`).
- `{{SpawnPoint|stablekey=npc:…|zone=…|x=…|y=…|z=…|spawn_chance=…|night_spawn=…|spawn_upon_quest_complete=…|notes=…}}`
  — fields mirror `character_spawns` (`zone_stable_key`, `x/y/z`, `spawn_chance`,
  `night_spawn`, `spawn_upon_quest_complete_stable_key`). Stored in the `Spawns`
  alongside generated `character_spawns`-derived rows, distinguished by `Origin`.

Editors must learn each entity's `stablekey` to target the right variant. That is
an **editor-documentation** concern, not infobox content — see §11. No
copy-paste stub is rendered into the article infobox; that is not appropriate
reader-facing content.

Provenance / survivorship (per §3.5): community rows are additive or corrective.
Where a community row overlaps a generated fact (same key), community wins; where
it adds a new fact, it stands alone. If a correction later becomes extractable,
the regenerated value subsumes it. Queries union generated + community by
`StableKey`; display may flag `Origin=community` as unverified.

Survives-redeploy invariant (tested): the generator owns the Lua modules,
templates, and repo-manifest pages and never emits or overwrites the community
row templates; entity article pages stay community-owned, so a community
`{{ItemSource}}`/`{{SpawnPoint}}` row persists across a redeploy and still
answers its reverse query.

## 8. Caching & freshness

- Cargo writes rows on **page parse**, not when a declaring template is saved.
- A cross-page query is only as fresh as the *querying* page's last parse; stale
  results clear on reparse (MW HTML cache, ≤24h, or purge). Lua modules share
  templates' link-tracking, so editing `Data/*` enqueues `refreshLinks` for
  consumers — via the job queue, with the `$wgJobRunRate` caveat.
- The pipeline does not wait on the queue: keep the existing
  `purge_pages(force_link_update=True)` refresh of `embeddedin` dependents, and
  drive `cargorecreatetables` on schema change (use the replacement-table form
  for large recreates to avoid an empty-table window). Ensure the job queue runs
  as part of deploy.
- Ordering: queried-against rows must exist before the querying page is parsed;
  the existing deploy phases (push pages → recreate Cargo → purge dependents)
  satisfy this.

## 9. Removals & orphans

- Cargo treats any page edit/delete as a write that drops that page's prior rows
  and inserts current ones. Entity removed from the data module → on reparse,
  resolve=missing → store nothing → row dropped. Whole page gone → delete page →
  rows dropped.
- Reverse-query rendering (§6.1) makes removals correct: dropping the owner page
  (or reparsing it after the fact is gone) removes the junction rows and the
  reverse query updates on the consumer's next parse — no ghosts.
- Gap to close: the deploy bot cannot delete pages today (it only reports
  orphaned `created_titles` for manual deletion). Recommended backstop:
  periodic **drop-and-recreate of the generated tables from the authoritative
  regenerated set**, gated by `cargo_check` — fully deterministic for a generated
  pipeline, no new permissions. Community rows are unaffected (different
  `Origin`, different templates).
- The community `stablekey` validation category (§7) flags rows whose key no
  longer resolves after a game update (renamed/removed entity).

**Confirmed: drop-and-recreate** of the generated tables from the authoritative
set, gated by `cargo_check`. The deploy bot cannot be granted page-delete rights
(no permission to do so), so orphan removal relies on this deterministic rebuild.
Community rows are unaffected (separate `Origin`/templates).

## 10. Display layer

- Links render from stored names via `Module:Erenshor/Link` (semantic
  `<span class="erenshor-link…">[[Page]]</span>`); Cargo never stores the markup.
- All-6-classes → "All" collapse is display-only.
- Reverse-relationship sections render from Cargo queries (§6.1); own-entity
  fields from the Lua module.

## 11. Editor & template documentation

Every template and every entity type gets first-class documentation, built on the
installed `TemplateData` + `/doc` subpage stack (the established MediaWiki system)
rather than the ad-hoc doc pages that exist today. This is how editors learn what
to enter and how to find the values they need — and it replaces the rejected
infobox stub.

Per-template `/doc` subpages (`Template:<X>/doc`, transcluded via
`{{Documentation}}` inside the template's `<noinclude>`), each carrying:
- A `<templatedata>` block: every parameter with label, plain-text description,
  type (`string`/`number`/`boolean`/`wiki-page-name`), required/suggested status,
  and an example value. `TemplateData` surfaces this in VisualEditor/WikiEditor's
  template dialog, giving editors inline parameter guidance.
- Purpose, when to use, and live usage examples (transclude the template with
  sample params and show the result), per MediaWiki documentation guidance.
- Related templates (e.g. `{{SpawnPoint}}` ↔ `{{Character}}`).

Entity-editing guides (one per entity type: item, character, spell/skill/stance,
zone, quest) explain the contribution workflow: which facts are generated vs.
community-editable, how to add an `{{ItemSource}}`/`{{SpawnPoint}}` row, and the
precedence rules.

Finding the `stablekey`: editors don't need a special tool — every infobox carries
it verbatim in the wikitext (`{{Ability|stablekey=…}}`), so each variant's key is
already visible in the page source. The entity-editing guides document this (read
the source, copy the variant's `stablekey`). A Cargo-backed lookup/help page over
`Abilities`/`Characters`/`Items` (`StableKey` + `Page` + `Name`) is an optional
convenience, not a requirement. The identifier never appears in reader-facing
infobox output.

These doc pages and TemplateData blocks are repo-owned and deployed like other
repo pages; the entity-editing guides supersede the current ad-hoc template docs.

## 12. Testing

- Multi-entity: `Regrowth`-style two-spell page and a same-name two-character
  page — two rows, distinct StableKey, shared Page; both infoboxes render.
- No markup in Cargo: assert `Classes`/`Zones`/`Faction` (and all new tables)
  store names/numbers, not `<span>`/`[[…]]`; assert rendered output carries the
  semantic links.
- Reverse queries: item "dropped by", ability "used by", "what a class can
  learn" return correct rows from the junction tables.
- Community layer: `{{ItemSource}}`/`{{SpawnPoint}}` store `Origin=community`
  rows; survive a simulated redeploy; unresolved `stablekey` lands in the
  tracking category.
- Extend `wiki-dev/smoke/cargo.py` + fixtures to the new tables; extend
  `cargo_check.py` recreate set.

## 13. Sequencing (for the implementation plan)

0. **Export the missing wiki-relevant Spell flags first** (so the DB, Lua module,
   and `Spells` Cargo table include them in one pass — no later rework): add
   `GrantInvisibility`, `CannotInterrupt`, `JoltSpell`, `NoResonate` through the
   export chain — `Database/SpellRecord.cs` → `AssetScanner/Listener/SpellListener.cs`
   → `processor/writer.py` (raw `spells` schema) → `repositories/spells.py` SELECT
   → `domain/entities/spell.py` → `wiki_lua/spells.py` field map. Skip
   `ForHardEncounters`/`HardcodedUseCase`. (unity-export-system skill.)
1. Items/Characters fix: drop `ClassLinks`; `Classes`/`Zones` to names; `Faction`
   to WorldFaction `stablekey`; replace the `Zones`/`SpawnChance` hack with the
   `Spawns` table (§6); render links at display; + multi-entity fixtures.
2. Abilities schema: `Abilities` base + `Spells`/`Skills`/`Stances` detail
   (attach trick) + `AbilityClasses`.
3. Relationship tables: `Drops`, `ContainerDrops`, `CraftingMaterials`,
   `CraftingRewards`, `CharacterAbilities`; replace the `Items` `Overview*`
   columns with the per-relationship StableKey columns (§6). Move reverse
   relations to Cargo queries; remove denormalized arrays.
4. Community layer: `ItemSource`/`SpawnPoint` row templates, `OtherItemSources`
   table, community rows into the shared `Spawns` table, `Origin` columns,
   validation category, survives-redeploy test.
5. Freshness/orphans: extend recreate + refresh sets; drop-and-recreate backstop.
6. Documentation: per-template `/doc` + `TemplateData`, entity-editing guides,
   and the `stablekey` lookup help page (§11).

Each step is TDD (failing test first) and atomic. writing-plans turns this into
the step-by-step plan.

## 14. Resolved decisions
- §6.1 store-forward / query-reverse — **confirmed** (drop denormalized arrays).
- §9 orphan reconciliation — **confirmed**: drop-and-recreate (bot cannot get
  page-delete rights).
- §5.2 base `Abilities` table + per-type detail — **confirmed**.

## 15. References
- Cargo — Storing data: https://www.mediawiki.org/wiki/Extension:Cargo/Storing_data
- Cargo — Querying data (HOLDS): https://www.mediawiki.org/wiki/Extension:Cargo/Querying_data
- Cargo — FAQ (query cache lag/purge): https://www.mediawiki.org/wiki/Extension:Cargo/FAQ
- River — Representing one-to-many relations: https://river.me/blog/one-to-many/
- River — Cargo list-type fields: https://river.me/blog/cargo-list-type-fields/
- River — Optimizing Cargo (no UNION): https://river.me/blog/optimizing-cargo-1/
- Leaguepedia Module:CargoQuery: https://lol.fandom.com/wiki/Module:CargoQuery
- Help:Multiple-instance templates: https://www.mediawiki.org/wiki/Help:Multiple-instance_templates
- Page Forms — values/mappings (for context; not installed): https://www.mediawiki.org/wiki/Extension:Page_Forms/Values,_mappings_and_autocompletion
