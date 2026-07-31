---
title: Wiki Legacy Article Cutover
type: plan
status: active
created: 2026-07-11
parent: 2026-06-04-wiki-cargo-data-architecture
---

# Wiki Legacy Article Cutover

## Context

The repo-owned Lua modules and templates are deployed to the production wiki,
along with generated data modules for items, item shards, spells, skills, and
links. `Module:Erenshor/Data/Characters`, `Data/Quests`, `Data/Stances`,
`Data/Zones`, and `Module:Erenshor/Link/Search` are **not** deployed.
`Template:ItemTooltip` dispatches `kind=Weapon` or `kind=Armor` to
`Module:Erenshor/Item/ParameterizedTooltip` in the production equipment path;
`stablekey=...` dispatches to `Module:Erenshor/Item/Tooltip` for the reserved
Lua article path. 793 equipment articles use the parameterized tooltip and have
verified rendering. Playtest images and filename redirects are uploaded.

**No article page is on the Lua path and production Cargo is empty.** Live
`Template:Item` gates its Lua branch on `lua=1` in addition to `stablekey`, and no
live page sets `lua=1`. None of the ten designed Cargo tables exist on production,
because declaring does not create them and `WoWBot` lacks `recreatecargodata`. See
`docs/plans/2026-07-30-wiki-cutover-state-audit.md`.

Equipment articles currently use one parameterized `{{ItemTooltip|kind=...}}`
invocation with display-ready Normal-quality legacy arguments.
`Module:Erenshor/Item/ParameterizedTooltip` derives the eight quality variants
through `Module:Erenshor/Item/Quality` (with `PLANAR_MARCH_ENABLED=false` until
the patch ships) and composes the live legacy `Item/Weapon` and `Item/Armor`
templates through newline-joined `frame:expandTemplate` assembly. Non-equipment
kinds (general, consumable, aura, charm, spell scroll, skill book, and mold)
remain on legacy Jinja article templates; their stablekey path is reserved for the
future cutover.

Styling is deliverable. `TemplateStyles` 1.0 and `TemplateStylesExtender` 2.0.0 are
installed, unprotected `Template:*/styles.css` subpages accept the `sanitized-css`
model, and `MediaWiki:Gadget-erenshor.css` is deployable through the configured
`WoWMuch@InterfaceDeploy` interface-admin account. The remaining styling work is
integration: nothing emits a `<templatestyles>` tag and no CSS source is owned for
Lua markup. The legacy Jinja path remains the production writer until the cutover
gates are completed.

## Delivery sequence

The capability sections below are requirements, not an order of work. Delivering
them horizontally, every type at every stage, is what produced two months with no
production Cargo and no converted article. Deliver **one entity type end to end**
instead, smallest first, and retire that type's legacy generator before starting the
next.

Each slice ends with a type whose articles render from Lua, store Cargo rows, answer
at least one reverse query, and no longer have a Jinja generator.

| Order | Type | Entities | Live pages | Why here |
|---|---|---|---|---|
| 1 | Stance | 7 | 7 | Complete one-to-one coverage, 4,577-byte data module, no owned junction, one small reverse query against `Skills.StanceToUseKey`. The whole chain at seven pages. |
| 2 | Zone | 47 | 43 | Still small, no detail table by design, exercises reverse queries against `ObtainedFrom` and `Spawns` without owning either. |
| 3 | Quest | 198 | 19 | Exposes the page-coverage gap and the `QuestRewardsQuery` path. Mostly article creation rather than conversion. |
| 4 | Character | 1,254 | 500+ | Owns `Spawns` and `CharacterAbilities`. Needs the data module under the size limit first. |
| 5 | Item | 1,537 | 793 | Owns `ObtainedFrom`, `UsedIn`, and `ItemEffects`. Largest blast radius, most valuable, converted last. |
| 6 | Spell, Skill | 400 | 0 | Not a conversion. No articles exist, so this is content creation on the already-migrated path. |

Slice 1 is the real gate. If stances cannot go end to end, nothing larger can.

Capabilities by slice: slice 1 needs sections 2 through 6 for one type only. Slice 4
additionally needs the character data module under 4,194,304 bytes. Slice 5
additionally needs the schema revision in
`2026-07-30-wiki-cargo-schema-revision`. **Section 1, the community-row layer, is not
a prerequisite for any slice** and moves to the end, after at least one type is
converted and the row shapes are proven in production.

## Approach

### Cutover gates before any type conversion

No article type may move to the Lua stablekey path until all of these
prerequisites are satisfied:

- The designed Cargo tables exist on production, created with `cargorecreatetables`
  run as `WoWMuch` or another sysop-equivalent account. `WoWBot` cannot do this.
- Styling for Lua-owned markup is wired end to end: a CSS source is owned in the
  repo, a `<templatestyles>` tag is emitted deterministically, and the stylesheet
  deploys through `wiki deploy-interface` or a `Template:*/styles.css` subpage.
- Lua presentation parity with the restored legacy display contract is proven
  against live pages, including wikilinked names, icon suffixes, unit
  conversions, zero-as-blank optional fields, the XPBonus percent rule,
  centered layout, and resolved drop rows.
- Scribunto testcase pages exercise renderers through real frames using
  `mw.getCurrentFrame():newChild`; frame mocks are prohibited. `Module:*/testcases`
  pages are excluded from production deploy manifests.
- The four undeployed data modules are live, so the character, quest, zone, and
  stance Lua paths can resolve.

The legacy Jinja generator is re-hardened and remains the production article
writer until Phase 7 completes. It must continue to write the non-equipment kinds
while the gates above are unresolved.

**Template deploys are a known live regression risk.** `WoWBot` twice deployed
Lua-only `Quest`, `Zone`, and `Stance` bodies with no legacy fallback, and an admin
reverted both rounds within a minute, on 2026-07-14 and 2026-07-22. The repo's
dual-path bodies for those three landed after the second revert and have never been
deployed. Any template deploy must first prove the legacy branch still renders
parameter-only articles.

### 1. Add the community-row layer, after the first type is converted

This is the last capability to build, not the first. It has no consumer until at
least one type renders reverse-query sections in production, and building it first
adds schema surface to a table that has never been created.

Implement the Phase 4 contribution layer before writing the thin-page converter.
It reuses the `ObtainedFrom`, `UsedIn`, and `Spawns` Cargo schemas defined by the
repo's store templates and the stable-key resolution conventions already used by
`Module:Erenshor/Link.lua`. Those schemas are declared in the repo but do not yet
exist on production, so table creation precedes this step.

- Add `{{ItemSource}}` storage for `ObtainedFrom` rows with
  `Origin=community`, `SourceType=community`, null `SourceKey`, and preserved
  `SourceText`.
- Add `{{SpawnPoint}}` storage for `Spawns` rows with `Origin=community` and
  stable-key validation. Unresolved keys must render a tracking category and
  must not create a generated-looking row.
- Add TemplateData/documentation and parser-safe validation for both templates.
- Ensure community rows survive a generated data refresh and appear beside
  generated rows in reverse Cargo queries.
- Add fixtures, Cargo expectations, smoke assertions, and harness tests for
  successful rows, unresolved keys, and redeploy preservation.

Use the existing Cargo declaration/store modules and the established
`SourceText`/`Origin` columns; do not create parallel community tables.

### 2. Make all seven article templates dual-path

Extend the stablekey conditional architecture from `wiki/templates/Item.wiki`
and `wiki/templates/Character.wiki` to `Spell.wiki`, `Skill.wiki`,
`Stance.wiki`, `Quest.wiki`, and `Zone.wiki`. Current repo state: `Character`,
`Quest`, `Zone`, and `Stance` branch on `stablekey`, `Item` branches on `lua=1`
plus `stablekey`, and `Spell` and `Skill` are unconditional Lua with no legacy
fallback. Live state is further behind, because `Quest`, `Zone`, and `Stance` are
legacy-only there. Resolve `Spell` and `Skill` explicitly: either give them a
legacy branch or record the decision that they stay Lua-only.

For each template, preserve the current generated stablekey branch unchanged
except where a test proves a defect. Add a no-stablekey legacy branch containing
the exact existing live inline-param infobox behavior for that entity type. The
legacy branch must not invoke presentation Lua modules or `cargoStore`; the new
branch must not read legacy inline parameters. Invalid nonempty stablekeys must
enter the new branch and produce the existing missing-data diagnostic rather
than silently falling back to legacy rendering.

Use this fixed entity registry for all later stages:

| Entity type | Article template | Presentation module |
|---|---|---|
| Item | `Item` | `Erenshor/Item` |
| Character | `Character` | `Erenshor/Character` |
| Spell | `Spell` | `Erenshor/Spell` |
| Skill | `Skill` | `Erenshor/Skill` |
| Stance | `Stance` | `Erenshor/Stance` |
| Quest | `Quest` | `Erenshor/Quest` |
| Zone | `Zone` | `Erenshor/Zone` |

The registry must reject unknown types and Faction articles with an explicit
error. Do not add a Faction fallback or infer a Faction article model.

Add paired harness coverage for each type:

- valid stablekey page: generated fields render and exactly one stable Cargo row
  exists;
- absent stablekey page: legacy fields render and no generated Cargo row is
  written;
- invalid stablekey page: missing-data diagnostic renders and no stale Cargo row
  is accepted;
- multi-entity page: each stablekey stanza renders and each Cargo row is keyed
  distinctly by stable key.

Update `wiki-dev/smoke.tsv`, `cargo_*.tsv`, `cargo_absent.tsv`, fixture pages,
`tests/unit/test_wiki_dev_harness.py`, and parity tests as needed. Run the local
harness before proceeding to article conversion.

### 3. Define the authoritative article identity registry

Add a single entity-type registry under `src/erenshor/application/wiki_deploy`
that maps each of the seven supported types to:

- its repository/entity collection;
- its root article template name;
- its presentation module name;
- its stable-key and wiki-page-name accessors;
- fields eligible for generated-duplicate removal and fields guarded from
  conversion until the new module emits them.

Build identities using `build_article_identity_map()` from
`article_identity.py`, grouping by `wiki_page_name` and retaining every
`stable_key`. Null page names are excluded. Duplicate stable keys are a hard
error. A page with multiple stable keys is valid and must not be treated as an
ambiguous single-entity page; it becomes multiple ordered template stanzas.

Generalize the current Item-only CLI/review path so every registry type can be
preflighted. The default operation must cover all seven types; `--type` may
restrict a run to one registry entry. Any page whose authoritative type,
template, or stable-key set conflicts with the registry fails the preflight.

### 4. Implement thin-page conversion with content preservation

Add a dedicated thin-page generator/converter under
`src/erenshor/application/wiki_deploy` rather than modifying the legacy Jinja2
article generator in place. It must consume the authoritative identity registry
and current live page text/revision metadata.

For each authoritative article page, emit deterministic stanzas in this exact
shape:

```wikitext
{{Type|stablekey=entity:stable-key}}
```

For multiple entities on one page, emit one stanza per entity, ordered by
registry type then stable key, with one blank line between stanzas. Preserve
non-template page sections byte-for-byte except for the minimum whitespace
normalization already used by `override_migration.py`.

Reuse `classify_article_overrides()` and `migrate_article_overrides()` instead
of reimplementing comparison rules:

- generated-duplicate parameters are removed;
- divergent community overrides are retained on the matching thin stanza;
- the intentional `-` blank sentinel is retained;
- unknown parameters and non-template sections are preserved;
- missing generated values, Scribunto errors, identity injection/conflicts, and
  unsafe fields fail closed and leave the page unchanged;
- all legacy template stanzas must be accounted for; an unrecognized or
  unmatched stanza is a preflight error, never silently discarded.

Extend migration parsing to process every stanza on a multi-entity page and
associate each stanza with its authoritative stable key. Do not use the current
single-identity ambiguity skip for conversion. Require the resulting page to
contain exactly the authoritative stable-key set for that title.

Generate a conversion report containing title, type, stable keys, removed
parameters, preserved overrides/sections, unresolved fields, and validation
errors. Dry-run output must be deterministic and machine-readable enough for
review before apply.

### 5. Add revision-safe article deployment and rollback

Add an article conversion deployment service that re-fetches each page before
writing and uses the namespace-agnostic guarded APIs in
`src/erenshor/application/wiki_deploy/pages.py`:
- existing page: `safe_edit_page()` with the fetched base revision;
- missing authoritative page: `safe_create_page()` only when the conversion
  report explicitly marks it as a new page;
- changed remote revision: refuse the edit and report a conflict;
- unchanged normalized text: skip the edit;
- assertion and assert-user guards are required for apply;
- no page deletion is attempted by the bot.

Production account handling is explicit: article edits and uploads run as
`WoWBot@erenshor-wiki` with its bot password. `WoWMuch@CargoProbe` lacks the
bot right; repo-page deploys may use the `--assertion user` fallback with that
account. `WoWBot` does **not** hold `recreatecargodata`, verified 2026-07-30, so
every Cargo table creation and schema change runs as `WoWMuch` or another
sysop-equivalent account.

Store a dedicated article conversion manifest containing title, entity type,
old/new revision IDs and timestamps, old/new content hashes, stable-key set,
rollback text path, and conversion outcome. Keep it separate from the
repo-owned Lua/template manifest because article pages have different ownership
and conflict semantics. Reuse rollback conflict handling from `rollback.py`;
created pages and orphan pages remain in a manual-admin report because the bot
has no delete right.

Add CLI commands under the existing `wiki` group following Typer conventions:

- `wiki articles preflight`: fetch and validate all seven types without edits;
- `wiki articles convert --dry-run`: produce the deterministic conversion report;
- `wiki articles convert --apply --assert-user <name>`: re-fetch, guarded-edit,
  record the article manifest, and stop on conflicts or validation failures;
- `wiki articles rollback <manifest>`: restore converted pages only when the
  current revision matches the recorded deployed revision, unless explicit
  force mode is used.

The apply command must require the playtest/shipping variant precondition,
logged-in MediaWiki client, explicit bot assertion, and a successful preflight.
It must never call the legacy unguarded article deploy path.

### 6. Add staged production cutover orchestration

Implement the Phase 7 sequence as a fail-fast operational command/runbook:

1. Run the TemplateSandbox gate against all seven dual-path templates and
   verify parser output has no unresolved Lua/template errors.
2. Deploy repo-owned Lua modules, generated data, Cargo declarations, and
   dual-path templates using the existing staged `deploy-repo-pages` flow.
3. Create/recreate Cargo tables through the explicit Cargo APIs. Poll each
   `cargorecreatedata` job to completion. For a large-table replacement, stop at
   the documented manual `Special:CargoTables` switch-in gate and require its
   confirmation before article conversion.
4. Run article preflight and review the conversion report.
5. Convert pages incrementally by entity type using the guarded article command.
   After each page, null-edit/reparse as needed, purge with forced link updates,
   and verify its Lua rendering and Cargo rows.
6. After a type has complete identity coverage and passes live smoke checks,
   remove that type's legacy template branch and retire its Jinja2 generator in
   a separate clean-cut commit.
7. Produce live smoke, Cargo identity, rollback, and orphan reports. Human
   admins handle orphan deletion; page renames use moves and retain redirects.

The orchestration must not proceed to legacy-branch deletion if any page is
missing, ambiguous, stale, unresolved, or unverified. It must support pausing
between types and resuming from the manifest.

### 7. Retire legacy article generation and establish steady state

Keep the existing `wiki fetch` → `wiki generate` → `wiki deploy` Jinja2 flow
available only until every type is converted; do not run it against a partially
converted production set. After all seven types are converted and verified,
remove its article-generation callsites and registrations: the legacy
`WikiGenerateService` path under `src/erenshor/application/wiki/services/`, the
`EntityPageGenerator` and `ZonePageGenerator` entries in
`src/erenshor/application/wiki/generators/registry.py`, the legacy article
branch in `src/erenshor/cli/commands/wiki.py`, and any article-only storage or
deploy helpers that are no longer referenced. Keep the existing repo-owned
Lua/template/data `deploy-repo-pages` path separate from the new guarded article
conversion command. The only remaining article writer must be the thin-page
converter; Lua/Cargo data refreshes must never rewrite article pages.

After all seven types are converted and verified, remove the temporary legacy
template branches in per-type clean-cut commits and establish the steady-state
thin-page/orphan reconciliation path.

Add steady-state checks for:

- authoritative stable-key coverage versus live article stanzas;
- unresolved stable keys and orphan pages;
- stale generated Cargo rows after page changes;
- community rows surviving generated refresh;
- type-specific legacy branch absence after retirement.

Add TemplateData and `/doc` documentation for the final templates, generated
versus community-owned fields, stable-key lookup, `ItemSource`, and
`SpawnPoint` editing.

## Critical files & anchors

- `docs/plans/2026-06-04-wiki-cargo-data-architecture.md` §§5–7, 9–15 — design authority for dual paths, thin conversion, Cargo creation, rollback, and orphan handling.
- `src/erenshor/application/wiki_deploy/override_migration.py` — existing override classifier/migrator and fail-closed safety behavior to extend for multi-stanza conversion.
- `src/erenshor/application/wiki_deploy/pages.py` — revision-safe create/edit primitives to reuse for main-namespace articles.
- `src/erenshor/application/wiki_deploy/article_identity.py` — authoritative stable-key/page grouping utility to generalize across seven types.
- `src/erenshor/cli/commands/wiki.py` — existing repo-page deploy, review, refresh, and rollback command conventions.

## Verification

Run from `/Users/joaichberger/Projects/Erenshor`.

### Template and local Cargo gates

```bash
uv run pytest tests/unit/test_wiki_dev_harness.py tests/unit/test_wiki_dev_parity.py
uv run python wiki-dev/import_pages.py --dry-run
uv run python wiki-dev/import_pages.py
uv run python wiki-dev/smoke_test.py
uv run python wiki-dev/parity_check.py
uv run python wiki-dev/cargo_check.py
```

The local fixtures must prove all four branch cases per type, multi-entity
identity, no generated Cargo rows on legacy/invalid pages, no markup in Cargo,
reverse-query rendering, and community-row survival after a simulated refresh.

### Generator and migration gates

```bash
uv run pytest tests/unit/application/wiki_deploy/test_article_identity.py \
  tests/unit/application/wiki_deploy/test_override_classifier.py \
  tests/unit/application/wiki_deploy/test_override_migration.py \
  tests/unit/application/wiki_deploy/test_pages.py \
  tests/unit/application/wiki_deploy/test_manifest.py \
  tests/unit/application/wiki_deploy/test_rollback.py
uv run erenshor -V playtest wiki articles preflight
uv run erenshor -V playtest wiki articles convert --dry-run
```

Required behavioral cases include a valid single-entity conversion, a
multi-entity same-page conversion, duplicate generated parameters removed,
manual override and `-` sentinel preserved, non-template community sections
preserved, remote revision conflict refused, and missing/unknown identity
refused without an edit.

### Production cutover gates

Run the TemplateSandbox and Cargo API gates against the live target with the
shipping/playtest data only. Use the local harness sequence after every staged
module/template change, then run the guarded article conversion in one type at
a time. For every converted page verify:

- exactly the authoritative stable-key stanza set is present;
- generated infobox fields render through Lua;
- expected generated Cargo rows exist and legacy-path Cargo rows do not;
- reverse Cargo queries include the page;
- preserved community content remains unchanged;
- forced link/Cargo refresh completes.

Before legacy retirement, require all seven type coverage reports to be empty,
all live smoke/Cargo checks to pass, rollback manifest creation to succeed, and
orphan pages to be explicitly reported for manual deletion.

## Assumptions & contingencies

- The seven supported article types are exactly Item, Character, Spell, Skill,
  Stance, Quest, and Zone. Faction remains unsupported and is a hard preflight
  error until a dedicated article module/template is designed.
- Stable keys are mandatory because one wiki title may contain multiple entity
  instances. Never infer identity from page title or display name.
- The current `Item` and `Character` new branches are the reference pattern;
  remaining templates receive verbatim legacy fallback branches while their
  types are being converted.
- The production target is single-variant and must use the playtest/shipping
  data pin. If the target build is not the shipping build, preflight fails.
- If the deploy bot lacks `recreatecargodata`, pause after schema declaration
  and require the main account/manual Cargo recreation gate; do not bypass it
  or mutate tables through an unguarded fallback.
- If a remote article changes after preflight, skip that page, record a conflict,
  and require a fresh preflight; never overwrite it with force by default.
- If an article contains an unrecognized template stanza, unsupported type, or
  unresolved multi-entity identity, fail the batch before any apply edits.
- If an orphan page cannot be deleted by the bot, emit the title and reason in
  the manual-admin report and continue only with verified authoritative pages.
