# Wiki Lua Migration & Cargo Data Architecture

Status: IN PROGRESS — approved umbrella spec for the full legacy→Lua wiki cutover.
Date: 2026-06-04 (rewritten 2026-06-06 to cover the full migration, not just Cargo).
Supersedes the cutover/retirement model of `2026-05-29-wiki-lua-migration-next-steps.md`
(its M1–M11 built the Lua rendering + repo-page deploy foundation; its M12–M14
cutover model is replaced by the dual-path / incremental model in §5–§6 here).

## Progress

Each increment lands via TDD + local smoke + the full commit gate.

Built foundation (2026-05-29 M1–M11): Lua presentation modules, PortableInfobox
templates, repo-page deploy/rollback/refresh, local smoke/parity harness, and
Items+Characters Cargo (validated locally only). Live wiki is still 100% legacy.

- [x] Phase 0 — export wiki-relevant Spell flags. Commits `79f3d71f`, `f66c287d`.
- [x] Phase 1a — drop `Items.ClassLinks` markup; render class links from `Classes`. `9bb6495a`.
- [x] Phase 1b — Characters `Faction`→WorldFaction stablekey, `Zones`→names, drop `SpawnChance`. `f063bcd4`.
- [x] Phase 1c — multi-entity Cargo regression fixture (`Dire Wolf`). `5ef8c16e`.
- [x] Phase 2 prereq A — spell/skill times to seconds at generation; zero ticks. `0f522eb1`.
- [~] Phase 5 de-risk — dual-path `{{Item}}`/`{{Character}}` proof landed ahead of
  schedule to validate the §5 cutover linchpin. **Plan A holds** (inline
  `<infobox>` inside `{{#if:{{{stablekey|}}}|new|legacy}}` expands as a real
  extension tag, not escaped); Plan B (sub-template transclusion) is unneeded.
  Harness now proves all three branches: thin page → new branch + Cargo row; fat
  inline-param page (no stablekey) → verbatim legacy infobox + zero Cargo rows;
  thin page with a dead stablekey → loud missing-data span + tracking category +
  zero rows. Cargo absent-row assertions generalized to the Characters table.
- [ ] Phase 2 prereq B — split `{{Ability}}`→`{{Spell}}`/`{{Skill}}`, retire `Module:Erenshor/Ability`.
- [ ] Phase 2 — abilities base + `Spells`/`Skills`/`Stances` detail + `AbilityClasses`.
- [ ] Phase 3 — junction tables + `Spawns` + item→ability scalar columns + reverse-query rendering.
- [ ] Phase 4 — community layer (`ItemSource`/`SpawnPoint`, `Origin`, validation).
- [ ] Phase 5 — dual-path templates (`{{#if:stablekey|new|legacy}}`) for every entity type (§5).
- [ ] Phase 6 — thin-page article generator + automated article deploy (§6).
- [ ] Phase 7 — production cutover: deploy → incremental thin-page conversion → per-type legacy retirement (§5, §15).
- [ ] Phase 8 — freshness/orphans + editor/template documentation.

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
  String` (bare names from `item_classes`). *(done — Phase 1a)*
- **Replace the `Overview*` ability columns** (which stored a resolved page title
  and collapsed weapon/wand/bow procs into one slot) with per-relationship scalar
  StableKey columns — see §8.

`Characters`:
- **Replace the `Zones`/`SpawnChance` markup hack with the `Spawns` table (§8).**
  Keep an optional derived `Zones = List (,) of String` (distinct zone names) as a
  cheap filter convenience. **`Faction`: store the WorldFaction `stablekey`** (the
  only joinable faction; the combat `Faction` enum is name-only, not a link).
  *(done — Phase 1b)*

All-6-classes → "All" is a display-only collapse in `Module:Erenshor/Link`
(store all class names; render "All" when the set is the full 6-class roster).

### 7.2 Abilities: thin base + per-type detail (class-table-inheritance)

A single wide `Abilities` table is rejected (sparse single-table inheritance).
Instead a thin base + three per-type detail tables, joined on `StableKey`, written
from the split `{{Spell}}`/`{{Skill}}`/`{{Stance}}` templates (`Spell` declares
the base + `AbilityClasses`; `Skill`/`Stance` `#cargo_attach`).

`Abilities` (base; one row per spell/skill/stance): `StableKey`, `Page`, `Name`,
`AbilityType` (`Spell`|`Skill`|`Stance`), `Image`, `Description`.

`Spells` (from `spells`): `StableKey`, `Page`, `Name`, `Type`, `Line`,
`RequiredLevel`, `ManaCost`, `CastTimeSeconds`, `CooldownSeconds`,
`DurationSeconds`, `Range`, `DamageType`, `TargetDamage`, `TargetHealing`,
`CasterHealing`, `ShieldingAmt`, `SimUsable`, `SelfOnly`, `GroupEffect`, `Aggro`,
`CrowdControl`, `GrantInvisibility`, `CannotInterrupt`, `Jolt`, `NoResonate`, plus
single-reference relation StableKeys `StatusEffect` (`status_effect_to_apply_stable_key`),
`AddProc` (`add_proc_stable_key`), `PetToSummon` (`pet_to_summon_stable_key`).
(Times are seconds — Phase 2 prereq A.)

`Skills` (from `skills`): `StableKey`, `Page`, `Name`, `Type` (`Innate`→"Passive"),
`CooldownSeconds`, `Range`, `SkillPower`, `PercentDmg`, `DamageType`, `Require2H`,
`RequireDualWield`, `RequireBow`, `RequireShield`, `RequireBehind`, plus relation
StableKeys `StanceToUse`, `EffectToApply`, `CastOnTarget`, `SpawnOnUse`.

`Stances` (from `stances`; all columns real): `StableKey`, `Page`, `Name`,
`MaxHpMod`, `DamageMod`, `ProcRateMod`, `DamageTakenMod`, `SelfDamagePerAttack`,
`AggroGenMod`, `SpellDamageMod`, `SelfDamagePerCast`, `LifestealAmount`,
`ResonanceAmount`, `StopRegen`.

`Page`/`Name` are denormalized onto detail tables so per-type list pages need no
base join. Detail tables carry the curated *queryable* subset; the full per-entity
field set stays in the Lua module for the infobox. Field coverage verified against
`Spell.cs`/`Skill.cs`/`Stance.cs`.

## 8. Relationship (junction) tables

One table per relationship shape, FK by `StableKey`, attributes as columns,
`Origin` provenance. Stored forward on the owner page; reverse is a query.

- `Drops` (from `loot_drops`; owner = character): `Character`, `Item`,
  `DropProbability`, `ExpectedPerKill`, `IsGuaranteed`, `Zone`, `Rarity`, `Origin`.
- `ContainerDrops` (from `item_drops`; owner = source item): `SourceItem`,
  `DroppedItem`, `DropProbability`, `IsGuaranteed`, `Origin`.
- `CraftingMaterials` (from `crafting_recipes`; owner = recipe): `Recipe`,
  `Material`, `Quantity`, `Slot`, `Origin`.
- `CraftingRewards` (from `crafting_rewards`; owner = recipe): `Recipe`, `Reward`,
  `Quantity`, `Slot`, `Origin`.
- `AbilityClasses` (from `spell_classes` + the six `*_required_level` skill
  columns; owner = ability): `StableKey`, `Class`, `RequiredLevel`, `Origin`.
  `RequiredLevel` resolved per (ability, class): spells broadcast their single
  `required_level`; skills use the per-class column. `Class` = canonical class name.
- `CharacterAbilities` (from `character_attack_spells` + siblings + `character_attack_skills`;
  owner = character): `Character`, `Ability`, `Usage`, `Origin`.
- `Spawns` (from `character_spawns` + `character_chained_spawns` expanded per
  `docs/superpowers/specs/2026-05-28-dynamic-spawn-coverage-design.md`; owner =
  character): `Character`, `Zone`, `Scene`, `X`, `Y`, `Z`, `SpawnChance`,
  `NightSpawn`, `SpawnUponQuestComplete`, `LevelMod`, `RareNpcChance`, `SpawnType`
  (`spawn_point`|`direct`|`trigger`|`event_script`|`chained`), `Origin`. Replaces
  the flat character `Zones`/`SpawnChance`. Upgrade path: Category-C zone-random
  spawners → future `zone_random_spawns` table. Community spawns use `{{SpawnPoint}}`
  (§9) into this same table with `Origin=community`.

Faction relationships are deliberately not one shape: only the WorldFaction is
stable-keyed/joinable (`my_world_faction_stable_key`, `character_faction_modifiers`);
the combat `Faction` enum (`my_faction`, aggressive/allied lists) is name-only.

**Item→ability links are 1:1 scalar columns on `Items`, not junction tables**
(`Item.cs` exposes each as a single reference), each storing the ability
**StableKey**: `TeachesSpell`, `TeachesSkill`, `WeaponProc` (+`WeaponProcChance`),
`WandEffect` (+`WandProcChance`), `BowEffect` (+`BowProcChance`), `WornEffect`,
`ClickEffect`, `SkillUse`, `Aura`. Reverses are queries on the column. The overview
"Proc" cell is display-time coalescing (pick whichever of weapon/wand/bow is set;
derive trigger from item type), not a stored conflated column.

### 8.1 Forward-store / reverse-query rendering

Reverse/cross-page relationships ("dropped by", "used by", "taught by") are
**rendered via Cargo query** against the junction tables / item→ability columns —
in list pages and in the infobox — and the denormalized reverse arrays (`usedBy`,
`itemsWithEffect`, `source`) are **removed from the Lua data modules**. Single
source, removal-correct. **Confirmed** (Leaguepedia's model).

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
- **Confirmed: drop-and-recreate** of generated tables from the authoritative set,
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

## 15. Phased sequencing (for the implementation plans)

Cargo new-path completion (local harness) comes first so the dual-path new branch
is whole before any page is converted; then dual-path + generator + cutover.

0. *(done)* Spell-flag export.
1. *(done)* Items/Characters Cargo fixes + multi-entity fixture.
2. *(done)* Times→seconds at generation.
3. Phase 2 prereq B + Phase 2: split `{{Ability}}`→`{{Spell}}`/`{{Skill}}` (retire
   `Module:Erenshor/Ability`); abilities base + detail + `AbilityClasses` Cargo.
4. Phase 3: junction tables + item→ability scalar columns; move reverse relations
   to Cargo queries; drop denormalized arrays.
5. Phase 4: community layer.
6. Phase 5: dual-path templates for all seven types (embed verbatim legacy
   fallback branches; new branch unchanged); both-branch harness tests.
7. Phase 6: thin-page article generator + automated article deploy + generalized
   override-preserving conversion (all seven types).
8. Phase 7: production cutover — TemplateSandbox gate → deploy dual-path
   templates/modules → recreate Cargo → incrementally convert pages to thin →
   per-type, delete the legacy branch + retire that type's Jinja2 generator →
   live smoke + rollback manifest.
9. Phase 8: freshness/orphan drop-and-recreate automation + documentation.

Each step is TDD (failing test first) and atomic; writing-plans turns each phase
into a step-by-step plan.

## 16. Resolved decisions
- Dual-path `{{#if:stablekey|new|legacy}}` cutover; all-or-nothing per page; Cargo
  pure (new branch only); legacy branch = verbatim legacy infobox, deleted per
  type after conversion. **Confirmed.**
- Thin generated `{{Type|stablekey=}}` pages (community content preserved) as the
  cutover mechanism, replacing the M13 null-edit model. **Confirmed.**
- Store forward / query reverse; drop denormalized arrays. **Confirmed.**
- Orphan reconciliation = drop-and-recreate (bot cannot get page-delete rights).
  **Confirmed.**
- Base `Abilities` table + per-type detail; distinct `{{Spell}}`/`{{Skill}}`
  templates. **Confirmed.**
- All times in seconds; no tick storage/display anywhere. **Confirmed.**

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
