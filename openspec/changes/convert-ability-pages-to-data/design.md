# Design

## Context

See proposal.md for motivation and `adopt-data-backed-wiki/design.md` D1-D3 for ownership and conversion order. This slice follows item and stance conversion and reuses their neutral conversion mechanics.

Read-only production inventory on 2026-10-17 found 385 main-namespace Ability users, with 402 top-level roots. Of these, 399 roots on 382 pages have stable identities and exactly match the generated corpus field for field: 348 spells and 51 skills. All have their corresponding tooltip companions. The 331 nonblank captions are generated player status messages. The preservation map currently has `Ability: {}`, so no Ability parameter is preserved as an editorial field today. This does not justify discarding future edits.

The other three roots are unkeyed: Fishing, Pocket Rift and Stance: Reckless. Fishing is explicitly excluded in mapping.json. Stance: Reckless has a removed-content disposition without a stable skill identity. Pocket Rift has no matching shipped spell or skill row. The database has Dimensional Rift under another exact identity and page, which is not proof that the old Pocket Rift article is the same entity. Keep all three legacy pages and their exact content. They remain compatibility users, not failed current-generation conversions and not evidence that all legacy Ability users have disappeared.

The clean database has 348 spells, 52 skills and six active stances plus historical Reckless. Fishing accounts for the excluded skill. Repository methods return the complete clean spell/skill rows. A null mapped wiki page excludes a new article, while Lua data builders can still retain a display-name record. Reuse existing visibility and lifecycle inputs rather than treating data-table presence as article eligibility.

Thirteen spell pages contain two identities, including Regrowth caster/effect pairs, Death's Embrace caster variants, Protection worn effects and Frozen Breath cast/stun variants. `EntityPageGenerator._entity_sort_key` puts class-bearing spells first, then uses stable-key order. These identities must not collapse to a page title. The exact spell/skill key is already carried by `.erenshor-ability-tooltip[data-erenshor-key]`, and the hover gadget selects exactly one match on the target page.

`ability.jinja2` writes 70 named parameters and one SpellTooltip or SkillTooltip companion. The legacy Ability PortableInfobox ignores line, required_level, range, max_level_target, resist_modifier, special_descriptor, percent_mana_restoration, duration_in_ticks and the generated boolean flags. It labels every type as Spell Type and emits only Abilities. Some omitted information already appears in the data-backed inline tooltip, but that does not make the infobox complete. Skill effects combine exact effect_to_apply, activated_stance and cast_on_target links. Spell effects remains blank in the old generator. The skill article generator leaves itemswitheffect blank even though Skills data already contains itemsWithEffect.

`build_spells_data` and `build_skills_data` already publish the native fields and typed acquisition relations needed here. Spell classes union SimPlayer class data with teaching-item restrictions. Spell cooldown is native seconds, skill cooldown and spell charge time divide ticks by 60, and spell duration ticks multiply by three. Preserve these different units. Existing Python data tests, Spell/Skill Scribunto testcases, Ability Tooltip Fixture and Semantic Tooltip Smoke already cover part of this contract.

Live API availability controls confirmed Template:AbilityData missing while Ability and all three data pages existed. Live Spells revision 67266 was 864,723 bytes, Skills revision 58929 was 70,288 bytes. These are not Lua runtime cost measurements. Planning performed no parser, browser or deployment acceptance.

The read-only API also confirmed Module:Erenshor/Ability, Data/StanceRelations and Data/EntityLifecycle missing. Category:Spells and Category:Skills do not exist, while Category:Stances exists. This makes publishing the new spell/skill category pages an actual prerequisite, not a hypothetical cleanup.

## Goals / Non-Goals

Goals:

- One compact call for each current game-backed spell or skill root, with exact caster/effect identity preserved.
- Correct spell and skill categories and complete useful data without copying facts into articles.
- An explicit caption home and intact prose, historical notices, inline tooltips and hover behavior.

Non-goals:

- Guessing identities for historical/manual pages or converting excluded Fishing by title.
- New source selection, a second class selector, a new tooltip UI or a type-specific writer.
- Adding developer-only flags to a public infobox merely because they occur in data.

## Decisions

### D1. One new wrapper dispatches by key kind

Add `Template:AbilityData` and a maintained `Module:Erenshor/Ability` article renderer. The only identity parameter is stablekey. Dispatch exact spell keys to existing Spells data/resolution and exact skill keys to Skills. Stance keys must use StanceData. Never fall back to name, page title, kind labels or the first record. Invalid identity is visible and adds `Category:Pages with invalid Erenshor ability identity` in article namespace.

Keep Ability, SpellTooltip and SkillTooltip compatible. New article rendering can call existing tooltip renderers internally, but emits exactly one keyed inline card per root. The card's kind and stable key must identify the root even when effects or variants share a page. Existing hover code continues to retrieve that card. Preserve normal click and focus behavior, centered tooltip content and the pure black spell border. No context-menu or right-click details action is added, including when the tooltip is used below an item.

### D2. Explicit field ownership and visitor display

Data owns title, icon, description, native type, classes and levels, timings, resources, targeting, damage, healing, shielding, crowd control, stats, skill requirements, summons, applied effects, procs, teaching items, items with effects, characters using a spell and lifecycle. The renderer consumes the existing typed references and exact effect/caster identities. It never derives acquisition or class eligibility from prose or builds a second source selector.

The editor-owned content field is imagecaption. Conversion retains its exact raw bytes, including the 331 current generated captions, instead of treating resemblance to a game message as permission to erase it. For a new page with no explicit caption parameter, a spell may display its existing data statusEffectMessageOnPlayer caption. An explicit caption, including blank, controls presentation only. Other prose remains outside the compact root. `notice=external` is the same presentation-only control introduced by stance conversion for an already validated standalone lifecycle notice.

Unknown parameters cannot replace data and add `Category:Pages with unsupported Erenshor ability parameters`. A conversion inventory compares all legacy parameter values with the revision-bound generated baseline. Nonempty unexpected or edited factual parameters block conversion until moved to prose, corrected in the source pipeline, or explicitly resolved. Do not convert historical/manual unkeyed roots by name. No hardcoded title exception list is used in automation.

Keep every currently visible factual row, with native formatting corrected where required by review. Use Spell Type for spells and Skill Type for skills. Class restrictions show canonical display names and per-class levels. Show Range and target restrictions, resist modifier, equipment/position requirements and mana restoration when applicable. Spell Line identifies stacking lines. Crowd control and targeting labels show true player-relevant root/stun/charm/fear, self/group/caster targeting, break behavior and target-level restrictions without a wall of false flags. Ticks are not displayed as a second duration unit when seconds already show the same fact. SimPlayer implementation flags and internal animation identifiers are not public rows.

Use shared existing spell/skill tooltip formatting for mechanics where it already covers the native fact, and add missing infobox rows rather than parsing tooltip HTML or manufacturing a combined effects string. Skill effectStableKey, stanceStableKey and castOnTargetStableKey remain distinct links with appropriate labels, even when destinations share a title. Only show a damage type where relevant. Label the native skillPower value Base Skill Power rather than treating it as guaranteed target damage. Keep effect/weapon scaling distinct and do not invent a derived final damage formula. The production diff must expose any old misleading row changed by this rule.

Emit Abilities and Spells for spell roots, Abilities and Skills for skill roots, article namespace only. A shared spell/skill page receives the union, not a winner based on page name. Stance categories remain the stance slice's responsibility. Publish any missing category pages before writes that use them.

### D3. Reuse complete immutable data

Do not restructure or duplicate Data/Spells or Data/Skills. Their existing maps carry the native facts and source, itemsWithEffect, usedBy, classLinks/classLevels and stable effect references. Reuse Python `_usable_classes`, existing link_refs and canonical item relation inputs rather than reproducing their selection. The previously blank skill article itemswitheffect now renders from the existing data relation and is an explicit reviewed output change.

Reuse `Data/EntityLifecycle` introduced by the stance slice. Populate exact spell/skill lifecycle records with `ContentLifecycle` and `load_content_lifecycle` from the canonical owner's neutral `erenshor.infrastructure.content_lifecycle`. Never import the CLI's `_load_retired_lifecycle`, derive dispositions from missing acquisition or duplicate ItemsV2 item dispositions. Active current-generation roots such as Mana Burst and Mana Call still render their recorded removed notices. Preserve existing standalone notice bytes where present and avoid a duplicate renderer notice through the validated placement control.

No entity data schema expansion is required by this inventory. If implementation demonstrates a genuinely missing fact, fix Python/export inputs and add a narrow supplement or new versioned module, with exact downstream reader migration. A generic AbilityData copy of both entire schemas is rejected.

### D4. Conversion interface and write ownership

Supply the parent's neutral conversion mechanism with Ability as the legacy root name, AbilityData as the new root name, allowed identity kinds spell/skill, imagecaption as preserved content, and SpellTooltip/SkillTooltip as key-specific companions. Reuse native guarded edits, `GuardedPageEdit`, manifests and rollback plus shared full-corpus comparisons and limit reports. Do not copy item_migration.py or turn item quality and item companion policies into generic ability rules.

Every candidate page has all roots accounted for. Duplicate keys/parameters, mismatched kinds, missing identities on a current-generation root, mixed converted/legacy game-backed roots, and unknown companion ownership block the page and full approval. Unkeyed legacy-only pages receive a recorded preserve disposition with their revision and rationale. A retained legacy-only root on a shared eligible page must remain byte-identical, and the receipt must not claim that root converted.

Delete companions only when exact key binding and checkpointed bot publication text/revision prove ownership. A tooltip manually placed inside prose or a table is not owned because it follows a root. If a retained manual companion would create duplicate keyed cards after conversion, stop for explicit editorial resolution rather than break hover identity. Preserve all text outside proven replacement spans byte for byte, including unrelated type roots and separators.

Bot owns generated Data pages. The repository owns new wrappers, renderer, styles, diagnostic category pages and test fixtures. People own captions, prose and legacy manual articles. Use native dependency ordering and repository drift checks for repository pages, and fetched-revision guards for every article write. No permanent copies of people-owned pages enter wiki/.

### D5. Acceptance and removal gates

Behavior tests cover both key kinds, all existing visible rows, newly displayed targeting/requirements, exact effect links, unit precision, editorial caption bytes and blank overrides, namespace categories, invalid identities and unsupported facts. Existing Scribunto tests remain green. Extend wiki-dev imports and smoke fixtures for a spell, a skill, caster/effect multi-root page, multi-class levels, historical spell and manual unkeyed root preservation. Test nested manual companion refusal and shared unrelated roots through the neutral converter's behavior tests, not permanent wording/source-copy assertions.

Import generated production-scale Spells, Skills, Links, lifecycle and dependent Items data into the real local host. Inspect spell/skill layouts, narrow-width infoboxes, centered inline tooltips, captions, long source/used-by lists, historical notice placement and reordered multi-root pages in a browser. Save local screenshots. Exercise hover/focus selection of each key on the shared target page, navigation, an item with an existing inline spell tooltip and no added right-click details behavior.

Text-parse old and candidate text for every eligible production page under its real title, not only representative fixtures. Include the preserved legacy-only inventory in the coverage report. Record visible text, categories, links, images, keyed tooltip DOM and all intentional changes, especially categories, the Skill Type label and newly visible mechanics. Require fresh dependency availability, complete root coverage and explicit review of every difference. Incomplete TemplateSandbox dependency results are provisional, not acceptance.

Measure full generated module bytes and actual enforcing Lua memory/time, expansion and parser limits on the host using the largest usedBy/source page, both kinds, effect-heavy pages and every multi-root page. Require at least 25 percent headroom below each observed enforcing limit. A metric the host does not expose remains an explicit approval blocker until an equivalent enforcing limit is established. Do not remove facts or variants to fit a fixture-scale result.

## Risks / Trade-offs

- New rows change visible output instead of preserving legacy omissions. Full-corpus differences and local browser approval separate intended improvements from regressions.
- Shared pages can return the wrong hover card if a root or companion is guessed. Exact identity and one keyed inline card per converted root are acceptance invariants.
- Frozen caption text can differ from later native status messages. That is deliberate presentation ownership, while game descriptions and effects still update from data.
- Three manual legacy roots remain. Complete eligible cutover is not a claim that legacy templates are unused, and their compatibility renderer stays available.
- Data/Links and item dependencies may dominate limits. Measure their transitive generated load and shard only through immutable reader migration if necessary.

## Migration Plan

1. After stance conversion has established shared lifecycle publication and neutral conversion primitives, land ability rendering, behavior tests, fixture/smoke rows and the editor/data-contract documentation in a coherent unit. Recheck free public template/module titles before deployment.
2. Publish exact required data and category dependencies through reviewed native dry runs and approvals, then readers. Verify local screenshots before live reader approval. Legacy Ability remains untouched.
3. Build the revision-bound full inventory and comparison/limits report. Resolve unexpected fields, unknown identities and companion proof gaps. Preserve and name legacy-only dispositions without guessing identities. Production comparisons remain read-only.
4. With separate approval, convert canaries covering ordinary spell, skill, multi-root caster/effect, class restrictions, item relationships and historical notice. Inspect fresh production parse/browser output. Exercise manifest rollback to original text and refusal after a later edit. Reapply only with approval.
5. Refresh the full dry run after canaries. Broad writes require their own approval tied to report, source/data hashes, complete comparisons, measured limits and canary/rollback evidence. Revision or data drift invalidates the plan.
6. After all current-generation eligible roots pass, switch spell/skill generation to compact new stubs and exact membership-only reconciliation. Unchanged membership returns unchanged article bytes. Keep removed identities for the lifecycle workflow and never erase editorial content. Preserve other types on shared pages.
7. Remove SpellSectionGenerator, SkillSectionGenerator, ability.jinja2 and obsolete type-only assembly/merge rules only after verified full eligible coverage and the accepted rollback retention window. Keep public legacy Ability, existing tooltip entry points and native guarded deploy/rollback for manual pages and external consumers. The final type conversion owns removal of the common merge/Jinja/full-article machinery.
