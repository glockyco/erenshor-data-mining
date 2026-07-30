---
title: Wiki Cutover State Audit (2026-07-30)
type: audit
status: active
created: 2026-07-30
parent: 2026-07-09-erenshor-planning-overview
---

# Wiki Cutover State Audit (2026-07-30)

What is actually true on `erenshor.wiki.gg` as of 2026-07-30, measured against the
repo and against the claims in `2026-06-04-wiki-cargo-data-architecture`,
`2026-07-11-wiki-article-cutover`, and `2026-07-10-wiki-deferred-mechanics`.
Method: anonymous read-only MediaWiki API and `Special:CargoTables` against live,
plus repo and clean-database inspection. No writes, no deploys.

## Verdict

The Lua and Cargo cutover is **less advanced on production than the plans state in
its load-bearing respects, and further advanced in its cosmetic ones**. Two
documented blockers are stale and one silent blocker was never recorded.

1. **Cargo is entirely inert on production.** None of the ten designed tables
   exist. Coverage is 0 of 1,537 items.
2. **No article page is on the Lua rendering path.** Zero live pages pass `lua=1`,
   which the live `Template:Item` requires. The Lua path is deliberately dormant.
3. **The styling gate is open, not blocked.** `TemplateStyles` is installed and
   already in live use, and a working interface-admin deploy path is configured.
4. **The Phase 7 Cargo-recreate gate is resolved and negative.** `WoWBot` cannot
   create Cargo tables. This is the root cause of finding 1.
5. **A human admin has reverted the bot's template deploys twice.** Live
   `Quest`, `Zone`, and `Stance` are legacy-only against the repo's dual-path source.
6. **The equipment tooltip path is far broader than documented**, covering 793
   articles rather than the twelve the spec claims.

## 1. Live platform

MediaWiki 1.43.6 with LIBRARIAN 4.21.0, Scribunto, Portable Infobox 0.7,
ParserFunctions, ParserPower 1.10.0, Arrays 2.2.1, Variables 2.6.0-beta,
VariablesLua 1.6.0, LabeledSectionTransclusion, TemplateData 0.1.2,
TemplateSandbox 1.1.0, **TemplateStyles 1.0**, and **TemplateStylesExtender 2.0.0**.
No Page Forms, Semantic MediaWiki, Data Transfer, or External Data.

## 2. Cargo is inert

`Special:CargoTables` lists exactly two tables, both with zero rows:

| Table | Rows | Columns | Declaring template |
|---|---|---|---|
| `Consumable` | 0 | 5 | `Template:Consumable/CargoDeclare` (rev 23731, Roan, 2025-07-03) |
| `Item` | 0 | 5 | none, reported orphaned |

Both carry an unrelated legacy schema of `title`/`name`, `image`/`file`, `effects`,
`buy`, `sell`. Every designed table is absent: `Items`, `Characters`, `Spells`,
`Skills`, `Stances`, `ObtainedFrom`, `UsedIn`, `AbilityClasses`,
`CharacterAbilities`, `Spawns`. There are no `__NEXT` replacement tables and no
leftover probe or sandbox tables. `Drops` and `ContainerDrops` are absent, which is
consistent with their intended deletion.

Two independent causes, both of which must be fixed:

- **The tables were never created.** All six Cargo-declaring templates are
  deployed and each carries `#cargo_declare` (`Template:Item` rev 44604 by WoWBot
  2026-07-19, the five store templates rev 42937 to 42943 by WoWBot 2026-07-14).
  Declaring creates nothing on save. Creation requires `cargorecreatetables`,
  which requires the `recreatecargodata` right.
- **No page would store a row even if the tables existed.** `cargoStore` sits
  inside the Lua branch, and no live page enters that branch (§3).

## 3. No article is on the Lua path

Live `Template:Item` gates its Lua branch on `{{#if:{{#ifeq:{{{lua|}}}|1|{{{stablekey|}}}|}}`
and documents the intent inline: `lua=1` opts a page into the Lua and Cargo
stablekey path *reserved for the future article cutover*, and generated articles
deliberately omit it so they render the legacy inline-parameter infobox while still
using the stablekey to build the interactive-map link.

Measured live, main namespace:

| Query | Pages |
|---|---|
| `insource:"lua=1"` | **0** |
| `insource:/kind=/` | 793 |
| `insource:"kind=Armor"` | 578 |
| `insource:"kind=Weapon"` | 215 |
| `insource:"ItemTooltip"` and `insource:"stablekey="` | 792 |

So 793 equipment articles carry one parameterized `{{ItemTooltip|kind=…}}`
invocation and 792 also carry a stablekey, while **zero** articles render the Lua
infobox or store Cargo rows. Render spot checks are clean, with no Lua or script
errors on the parameterized pages `Arcanist Cap` and `Razor Waveblade` or the
legacy pages `Muck Ball` and `Ripper Insignia Badge`.

## 4. Dual-path status, live against repo

Spec §5 requires all seven entity templates to branch directly on `stablekey`.
Neither live nor the repo satisfies that.

| Template | Live | Repo |
|---|---|---|
| `Item` | branch gated on `lua=1` plus `stablekey` | same |
| `Character` | branch on `stablekey` | same |
| `Quest` | legacy only | dual-path |
| `Zone` | legacy only | dual-path |
| `Stance` | legacy only | dual-path |
| `Skill` | unconditional Lua | unconditional Lua |
| `Spell` | unconditional Lua | unconditional Lua |

`Skill` and `Spell` have no legacy fallback at all, so they violate the
all-or-nothing property rather than implementing it.

## 5. The deploy bot is fighting an admin

`WoWBot` deployed Lua-only bodies with no legacy fallback, and `WoWMuch` reverted
them within about a minute, twice.

| When | Bot revision | Revert |
|---|---|---|
| 2026-07-14 12:51 to 12:58 | `Quest`, `Zone`, `Stance` | reverted, `Quest` back to a revision by community editor Roan |
| 2026-07-22 10:51 | `Quest` 44836, `Zone` 44837, `Stance` 44834 | reverted at 10:52 as 44839, 44840, 44841 |

The reverts were correct. The deployed bodies were Lua-only, so every legacy
parameter-only article of those three types would have lost its infobox. The repo's
dual-path bodies for `Quest` and `Zone` landed afterwards in `be27c9eb3`
(2026-07-22) and for `Stance` in `5fb526b08` (2026-07-23), so the fix exists locally
and has never been deployed. Until it is, `deploy-repo-pages --include-templates`
is safe for those three, and re-running the older manifest would break live again.

## 6. Account rights, which closes the Phase 7 gate

| Account | Groups | Cargo rights | Interface rights |
|---|---|---|---|
| `WoWBot` | autopatrol, bot, user, autoconfirmed, emailconfirmed | `runcargoqueries`, `runcargoapiqueries` | none |
| `WoWMuch` | interface-admin, sysop | `recreatecargodata`, `deletecargodata`, plus query rights | `editinterface`, `editsitecss`, `editsitejson`, `editcontentmodel` |

On this wiki `recreatecargodata` is granted only to `sysop`, `staff`, `staff-bot`,
`global-sysop`, `titan`, and `librarian-admin`. **The deploy bot therefore cannot
create or recreate Cargo tables and never will as a plain bot account.** Table
creation and every future schema change must run as `WoWMuch` or an equivalently
privileged account. Whether the configured `WoWMuch@InterfaceDeploy` bot password
carries the grant needed for `cargorecreatetables` is untested and is the one
remaining unknown on this gate.

## 7. The styling gate is open

- `TemplateStyles` 1.0 and `TemplateStylesExtender` 2.0.0 are installed.
- The pattern is already in live use. `Template:ClassPill/styles.css` exists at
  rev 44826 by community editor GreenFlag, 2026-07-21.
- A missing-title probe of `Template:Anything/styles.css` reports content model
  `sanitized-css`, empty page protection, and only `create` as a restriction type.
  The Template namespace allows subpages and carries no namespace protection.
- The gadget route is also deliverable. The MediaWiki namespace is protected by
  `editinterface`, but `MediaWiki:Gadget-erenshor.css` (rev 42951) and
  `MediaWiki:Gadgets-definition` (rev 42882) were both deployed by `WoWMuch` on
  2026-07-14, and `interface_username = WoWMuch@InterfaceDeploy` is configured with
  `wiki deploy-interface` wired to authenticate with it and to check `editinterface`
  during dry runs.

What genuinely remains is integration, not platform capability. The repo's Lua
modules build markup through `mw.html` but nothing emits a `<templatestyles>` tag,
no CSS source is owned for Lua markup, and rendered parity is unproven. Whether
`TitleBlacklist` restricts `styles.css` subpage creation was not separately
checked. [INFERENCE] Emission from Lua via `frame:extensionTag` is the likely
mechanism but was not exercised live.

## 8. Modules and data staleness

Live has 32 `Module:Erenshor/` pages, 19 non-data and 14 data. Five repo-owned
titles are absent from live: `Module:Erenshor/Link/Search`, `Data/Characters`,
`Data/Quests`, `Data/Stances`, and `Data/Zones`. The four missing data modules mean
the Lua path for characters, quests, zones, and stances cannot resolve on live even
where a template branch exists. None of the four has any log entry, so each was
never created rather than deleted.

### 8.1 `Data/Characters` cannot be deployed as one page

Live `maxarticlesize` is **4,194,304 bytes**. The generated module is **5,099,976
bytes**, which is 906 KB and 21.6 percent over the limit, so the deploy must fail.
The fix is precedented in the repo: `Data/Items` is already sharded into nine
kind-shards, the largest of which is `Items/Armor` at 3,608,766 bytes and therefore
fits. Generated module sizes:

| Module | Bytes | Fits 4 MiB |
|---|---|---|
| `Data/Characters` | 5,099,976 | **no** |
| `Data/Items/Armor` | 3,608,766 | yes |
| `Data/Links` | 1,625,494 | yes |
| `Data/Items/Weapons` | 1,312,337 | yes |
| `Data/Items/General` | 947,468 | yes |
| `Data/Spells` | 861,936 | yes |
| `Data/Quests` | 41,121 | yes |
| `Data/Zones` | 14,284 | yes |
| `Data/Stances` | 4,577 | yes |

Size explains only `Data/Characters`. `Data/Quests`, `Data/Stances`, and
`Data/Zones` are tiny and were still never pushed, and they are exactly the three
types whose templates were reverted to legacy. [INFERENCE] Those three were left
undeployed because their templates no longer used them, not because the deploy
failed. Generated-data deploys are opt-in and require an explicit `--pages-file`,
so omission is easy.

Live also carries a `Data/AbilityLinks` page with no local counterpart, which is a
leftover from an earlier naming.

### 8.2 Staleness
Data modules are stale and unevenly sourced. `Data/Items` and its nine item shards
were last written by `WoWMuch` on 2026-07-12, while `Data/Spells` and `Data/Links`
were written by `WoWBot` on 2026-07-24. The clean database is main build 24362350
with 1,537 items, 1,254 characters, 348 spells, 52 skills, 7 stances, 47 zones, and
198 quests. `Args`, `Cargo`, and `Format` are human-last edits but are byte-identical
to their repo sources after trailing-whitespace normalization. No `/testcases` page
leaked into production, which matches the exclusion at `manifest.py:331-360`.

## 9. Local phase implementation

| Phase or section | State | Evidence |
|---|---|---|
| Phase 4 community layer | absent | no `ItemSource` or `SpawnPoint` template in repo or live, `ItemObtainedFromStore.wiki:14-16` marks community as future |
| Phase 5 dual-path | partial | four direct branches, `Item` gated on `lua=1`, `Spell` and `Skill` new-path only |
| Phase 6 thin-page generator | absent | `override_migration.py:66-208` is a report-only single-stanza classifier that skips multi-key pages as ambiguous |
| Article identity registry | not as designed | `article_identity.py:16-30` is a generic title to stable-key grouping helper, used by `fetch_service.py:21,40` and `wiki.py:41,409` |
| Phase 7 orchestration | absent | no staged conversion command, no TemplateSandbox gate, no recreate automation, no article deploy manifest or rollback, no orphan report |
| Phase 8 freshness and docs | mostly absent | `refresh.py:1-167` does embedded purge and item-owner null edits only, only `Character` has `{{Documentation}}`, no `<templatedata>` in any of the seven, no per-type editor guides |

Every test path named in the cutover plan's verification section exists, but the
plan's `wiki articles preflight` and `wiki articles convert` commands do not.
Existing tests cover generic identity grouping, override classification, guarded
repo-page deploys, rollback, and refresh. Nothing covers community rows, the
seven-template matrix, thin conversion, staged orchestration, or orphan reporting.

## 10. Deferred mechanics

`0 of 15` is an honest implementation count. Data prerequisites are partly present.

| Task | Fact state | Data state |
|---|---|---|
| 1 Smithing merge and forge box | `smithing.upgrade_ids` exists with `31377423`, `2298018`, `2265228` | Merging Vessel `2265228` and Inert Diamond `2298018` present, no forge relationship |
| 2 Planar Shard blessing removal | `smithing.planar_shard_output` missing | runtime path exists, no Planar Shard item row |
| 3 Chessboard candlekeeper mold | `ReplaceStatue` fact missing | no Candlekeeper or game-piece item rows |
| 4 Time Stone use | `spellvessel.time_stone_id` missing | Time Stone `2936548` present, chest loot rows present |
| 5 Braxonian Flame Well ritual | fact missing | Offering Stone `340104` and Sivakrux `23431650` present |
| 6 Global world-drop pool | all 11 `loot.world_drop.*` facts exist | entirely unconsumed, `Essence of Amarion` `49119950` is a confirmed dead end |

Only `smithing.upgrade_ids` has a consumer, in
`infrastructure/database/repositories/items.py`. All eleven world-drop facts are
extracted and unused, so task 6 is closer to deliverable than its checkbox implies.
`Essence of Amarion`'s only clean-database edge is the Banker quest requirement, with
no acquisition path, confirming the dead end the plan predicts.

The asserted game-code shapes still hold in build 24362350, with two documentation
defects. The architecture spec cites `Smithing.cs:159-240` for the merge branch,
which now begins near line 144. The deferred plan describes the Brax ritual as a
"quality 2 to 1" upgrade, but `TradeWindow.CheckOfferingStones` assigns quality **2**
on success and **3** on the enhanced roll, and does not read the offered item's
quality at all. Separately, that method's failure path passes the item's original
*quantity* into the `_qual` parameter of `Inventory.AddItemToInv(Item, int)`, which
looks like a game bug and is not a wiki concern.

## 11. The parity gate does not check parity

The design spec treats presentation parity as a conversion gate. No instrument
currently measures it.

- `wiki-dev/parity_check.py` renders seven fixed fixture pages on the local Docker
  harness and compares them against a live-captured baseline of **computed CSS
  properties and DOM target presence only** (infobox shell, title, data row, plus
  group, header, and divider for characters). It never compares field values,
  wikitext, or rendered content, and the baseline is gitignored.
- `wiki-dev/clean_parity.py` compares warm against freshly bootstrapped local
  MediaWiki acceptance snapshots. It proves stack reproducibility, not
  legacy-against-Lua equivalence.
- Neither runs in CI. `.github/workflows/ci.yml` has no parity job, and
  `tests/unit/test_wiki_dev_parity.py` only exercises the comparison helpers.

So "parity is unproven" understates it: a conversion could regress every field and
the gate would still pass.

### 11.1 Known field asymmetries

| Type | Difference |
|---|---|
| Item | Lua root dispatch omits `vendorsource`, `source`, `questsource`, `relatedquest`, `componentfor`, `guaranteeddrops`, `droprates`. This is by design per section 8.1 of the design spec, which moves them to Cargo queries, so converting an item page while Cargo is empty silently drops its entire obtainability content. |
| Character | Lua adds `map`, `experience`, and `spawnwithstatus`, which legacy has no equivalent for. Drop rows differ in order: legacy sorts by probability then name, Lua preserves input order. Drop-rate and guaranteed-drop display is explicitly in progress. |
| Skill | Lua dispatch is a strict subset. It omits `line`, `required_level`, `manacost`, and more, where legacy emits them as blank parameters. |
| Zone | Lua populates `image`, `imagecaption`, and `level`, which legacy leaves blank, and Lua emits no Zone Navbox. |
| Quest | Lua routes `items` through `QuestRewardsQuery`, a Cargo query, where legacy supplies it inline. |
| Spell | Field coverage matches. Cast time relies on the exported seconds value rather than legacy tick division, so agreement depends on the export being correct. The `XPBonus` percentage rule is a divergence risk because legacy multiplies by 100 and the Lua accessor may already receive a percentage. |
| Stance | Field coverage matches plus a Lua-only `imagecaption`. Formatting is conceptually equivalent but was not compared as rendered output. |

### 11.2 The one live Lua surface is not a like-for-like

`Item/ParameterizedTooltip` does expand the legacy `Item/Weapon` and `Item/Armor`
cards, so its structure is shared. It also adds all eight quality variants through
`Item/Quality` with `PLANAR_MARCH_ENABLED = true`, plus labels, a flex wrapper, and
sparkle treatment, and its quality formulas are new. No test compares its rendered
output against the legacy card. The one surface that shipped therefore changed the
mechanism and the presentation at the same time, which is the pattern to avoid for
the remaining types.

## 12. Article corpus coverage

Live has 3,171 content pages and 7,167 total pages. Main-namespace transclusion
counts show the corpus is items and characters, and that three entity templates are
barely used while two are unused entirely.

| Template | Main-namespace transclusions |
|---|---|
| `Item` | 500+ |
| `Character` | 500+ |
| `ItemTooltip` | 500+ |
| `Zone` | 43 |
| `Quest` | 19 |
| `Stance` | 7 |
| `Spell` | **0** |
| `Skill` | **0** |
| `SpellTooltip` | 1 |
| `SkillTooltip` | 0 |

`Category:Spells` and `Category:Skills` are both empty and `Flame Bolt` does not
exist, so spells and skills have effectively no article corpus. The consequence is
that live `Template:Spell` and `Template:Skill` being unconditional Lua with no
legacy fallback is currently harmless, because nothing transcludes them. It also
means 348 spells and 52 skills in the clean database have no articles at all, which
is a larger content gap than the parity question.

## Corrections applied to the plans

Applied in the same commit as this audit.

- `2026-06-04-wiki-cargo-data-architecture` — the no-TemplateStyles and
  undeliverable-gadget claims, the "twelve item article pages" and Phase 3
  production-complete claims, the unverified `recreatecargodata` gate, the
  installed TemplateData and `/doc` stack claim, and the stale `Smithing.cs` line
  range.
- `2026-07-11-wiki-article-cutover` — the repeated styling claims, the "existing
  `ObtainedFrom`/`UsedIn`/`Spawns` Cargo schemas" claim, and the all-seven
  dual-path claim.
- `2026-07-09-erenshor-planning-overview` — the standing styling gate.
- `2026-07-10-wiki-deferred-mechanics` — the Brax ritual quality wording.

## What this changes about sequencing

1. **Build a real parity instrument first.** Nothing today measures field-level
   equivalence, so "get Cargo and Lua working properly" is currently unfalsifiable.
   Render each entity through both paths and diff extracted field values and
   rendered HTML. This is the true gate and it blocks everything below.
2. **Make the path selector an explicit flag on all seven templates.** `lua=1`
   already does this for `Item` (`wiki/templates/Item.wiki:1` and `:129-132`), and
   `PLANAR_MARCH_ENABLED` in `Module:Erenshor/Item/Quality.lua:12` is the
   module-level precedent with a per-call override for regression tests. Promote the
   flag to the canonical selector for every type and update section 5 of the design
   spec, because `stablekey`
   is now carried by 792 articles for the map link and tooltip and can no longer
   select a path. A template holding both branches behind an opt-in flag is inert on
   deploy, which structurally removes the revert failure mode.
3. **Shard `Data/Characters` below 4 MiB** following the `Data/Items` pattern, then
   deploy the four missing data modules.
4. **Create the Cargo tables as a privileged account.** Until this happens any
   converted page loses its relationship sections, because the Lua path delegates
   them to Cargo queries.
5. **Prove parity per type on a sandbox page, then convert one page, then a batch.**
6. **Freeze content and visualization changes** until the steps above are green.
   Change the mechanism or the presentation, never both at once.
7. **Decide `Spell` and `Skill` explicitly.** They have no legacy fallback, but also
   no transclusions, so the cheap correct move is to give them the same flag as
   every other type before any article starts using them.
