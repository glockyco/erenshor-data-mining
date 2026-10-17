# Design

## Context

See proposal.md for motivation and `adopt-data-backed-wiki/design.md` D1-D3 for the publishing boundary.

Read-only inventory on 2026-10-17 found seven live main-namespace users of Stance and seven keyed roots. Six active roots exactly matched the fetched/generated corpus, including all parameter values. None had a nonblank imagecaption. The seventh root is Reckless, with key `stance:reckless`, a standalone historical notice and a StanceTooltip companion. The clean database contains seven stances, but Reckless has `is_wiki_generated=0` and no wiki page name. Its native data record remains present because `build_stances_data` falls back to the display name. Preserve the reviewed historical identity without making it active again.

`StanceSectionGenerator`, `stance.jinja2` and `EntityPageGenerator._assemble_stance` copy description, switch message, ten modifiers, stop_regen and activated_by into articles. `FieldPreservationHandler` preserves only Stance imagecaption. `ROOT_COMPANIONS` associates StanceTooltip with a stance root, but proximity alone does not prove bot ownership.

`build_stances_data` already emits name, page, icon, description, switchMessage, the ten `_STANCE_FIELD_MAP` values and stopRegen. It lacks activatedBy and lifecycle metadata. `SkillRepository.get_skills_using_stance` already produces the exact activation relation. `Module:Erenshor/Stance.skillsForStance` instead scans every Skills record and sorts matching stable keys in Lua to pick a tooltip presentation. That is a second relationship selector to remove, not a model to extend.

The live API reported Template:StanceData missing while Template:Stance and Data/Stances existed. Data/Stances revision 58931 was 4,599 bytes. Generated local bytes were 4,600. The Skills dependency was 70,288 live bytes. These are page sizes, not Lua memory or CPU measurements. No render or browser acceptance was performed during planning.

## Goals / Non-Goals

Goals:

- Render native stance mechanics, all activating skills and recorded lifecycle without copied factual article fields.
- Keep the stance key on its tooltip even when a skill supplies the presentation.
- Convert the seven identified roots without losing captions, prose or historical context.

Non-goals:

- Reclassifying Reckless, changing its mapping exclusion or inventing a replacement skill.
- Replacing the live Stances schema just to add a relation.
- Adding a generic Lua query layer, a new HTTP writer or item-specific migration rules.

## Decisions

### D1. New public renderer and exact identity

Add `Template:StanceData` and a maintained infobox entry point in `Module:Erenshor/Stance`. The wrapper renders the infobox and exactly one inline tooltip. Require `stablekey` with a stance key present in the stance data. Missing, duplicate, wrong-kind or unknown identity yields a visible diagnostic and `Category:Pages with invalid Erenshor stance identity`. Never resolve by page title, display name or the first root. Legacy Stance and StanceTooltip remain compatible.

Use data for title, icon, description, switch message, all ten native modifiers, stopRegen and activating skills. The editor-owned content parameter is imagecaption. The notice placement control described below cannot change a fact. Unknown parameters never override data and add `Category:Pages with unsupported Erenshor stance parameters` in article namespace. Preserve their raw values in a blocked conversion report until explicitly resolved. Do not silently drop an unexpected nonempty legacy field.

Render multipliers relative to 1 with native precision handled at presentation time, selfDamagePerAttack as percent max HP, selfDamagePerCast as the native amount, and stopRegen as an actual boolean. Preserve baseline and absent-versus-zero semantics. Retain the Stances category in article namespace only. The inline tooltip keeps stance identity and shows native stance facts whenever no unique activating skill is proven.

### D2. Narrow relation and lifecycle publication

Keep `Data/Stances` and `Data/Skills` structurally unchanged. Add `Module:Erenshor/Data/StanceRelations` with shape `{stances = {[stanceKey] = {activatedBy = {typedSkillRef, ...}, tooltipSkillStableKey = skillKey?}}}`. A typed reference uses the existing link-ref contract, `kind="ability"` and `stablekey=skillKey`. Python uses `SkillRepository.get_skills_using_stance` and filters visible links through existing link helpers. Export an explicit empty activatedBy list for a stance without an activating skill. Set tooltipSkillStableKey only when exactly one activating skill is proven. Never select the first of several skills by name, iteration order or lexical key.

Update the stance tooltip resolver to use the generated exact tooltipSkillStableKey when present. It may load that one Skills record for presentation, but never scan Skills to derive relations. With zero or several activators, render stance-native facts directly while retaining every activator in acquisition. Do not synthesize a skill identity or label an arbitrary skill as the stance. Missing stance data remains an error.

Publish a narrow `Module:Erenshor/Data/EntityLifecycle` supplement with shape `{entities = {[stableKey] = {state, thing, update?, date?, url?}}}` using `ContentLifecycle` and `load_content_lifecycle` from the canonical owner's neutral `erenshor.infrastructure.content_lifecycle` module. Serialize keyed `ContentLifecycle.pages` records for stance, spell and skill prefixes only, map patch_notes_url to url and reject contradictory records for one key. Never guess a null key from its title or import the CLI's `_load_retired_lifecycle`. This slice introduces the supplement for non-item stances. The following ability conversion reuses its shape and extends its keyed population, not its structure. ItemsV2 keeps its own canonical dispositions, and its item-only derive_item_dispositions helper is not reused here. Missing activation never implies removal. Facts without a stable identity remain under the existing retired-page workflow.

For Reckless, the recorded stable key and shipped stance row are sufficient. Keep its exclusion from new active stubs. Preserve the existing standalone notice bytes and let the data renderer avoid a second notice through a single owned presentation flag, `notice=external`, set only when an existing validated standalone notice is retained. The flag changes placement, never lifecycle state. A new historical stub without an external notice renders the recorded notice from the supplement. Compare every such placement in the full corpus report.

### D3. Ownership and shared conversion boundary

Bot-owned Data pages come only from Python and the clean database plus validated lifecycle facts. Repository-owned wrappers, modules, styles, category descriptions and fixtures deploy through native dependency and drift guards. Article captions and prose belong to people. No maintained article copies go in wiki/.

The parent conversion owner supplies shared neutral identity parsing, companion proof, comparison/limit reports and guarded conversion orchestration extracted from the item work. Reuse native `GuardedPageEdit`, guarded edits, deploy manifests and rollback. Supply a stance descriptor with template names, stance identity kind, imagecaption ownership and StanceTooltip companion kind. Do not fork item_migration.py or pre-generalize its quality logic.

Bind removable companions to exact root stable keys and checkpointed bot publication bytes/revisions. A coincidentally identical tooltip or one merely following the root is not deletion proof. Missing or conflicting proof blocks that page. Keep all surrounding whitespace and prose byte-identical. If an unexpected owned parameter differs from current data, report it for source correction or an explicit editorial migration before conversion. The observed six active roots have no such differences, but that observation never becomes an allowlist.

### D4. Acceptance gates

Extend the existing stance Python data tests and Scribunto testcases with native modifier formatting, all/zero activation relations, exact tooltip identity, invalid keys, unsupported factual parameters and imagecaption preservation. Extend local fixture imports and smoke checks with converted active and historical pages plus multi-root/reordered and nested-editor-companion cases.

Import generated production-scale Stances, Skills, Links, StanceRelations and lifecycle data into the local MediaWiki host, not just the small fixtures. Inspect Normal, Aggressive, Hateful, Taunting and Reckless mechanics, captions, historical notices, acquisition links and centered inline tooltip layout in a real browser at desktop and narrow widths. Save local screenshots for approval. Exercise keyed hover, keyboard focus and ordinary navigation. No context-menu details action is introduced.

Before broad conversion, text-parse both current legacy and candidate text for every inventory page on production under the same title. Record visible text, categories, images, links, keyed tooltip DOM and parser limit reports. Categorize every difference, including canonical corrections on Reckless, rather than approving only unchanged pages. Recount live roots with continuation immediately before planning writes. Measure generated page bytes and actual Lua memory/time, expansion and parser limits using the full data and heaviest multi-root page. Require at least 25 percent headroom below each observed enforcing limit. Missing metrics or unresolved dependency states block broad approval and remain explicitly provisional.

## Risks / Trade-offs

- A module lookup can make all stance pages fail together. Publish and verify dependencies before readers, and retain legacy rollback targets.
- A historical native record differs from stale article parameters. Review the exact production parse diff without relabeling the historical stance as current.
- A manual tooltip can resemble a generated companion. Require checkpoint proof rather than textual resemblance.
- A new template title can be occupied after planning. Recheck live availability before publication and stop on drift rather than overwrite it.

## Migration Plan

1. Land data supplements and their tests/documented contracts. Keep old readers working and deploy exact data titles first only after a reviewed dry run and explicit approval.
2. Land wrapper, renderer, styles and category pages. Complete local real-data parsing, smoke and browser screenshots before requesting live reader approval. Deploy readers with guarded native repository-page tooling.
3. Build the complete conversion report from fresh revisions, including Reckless and any newly discovered legacy roots. Require complete production comparisons, measured limits, ownership proof and resolved findings. An excluded root is a recorded disposition, never silently omitted from coverage.
4. After separate approval, convert canaries covering ordinary multipliers, special effects and historical fallback. Inspect fresh production parses and browser output. Roll back the canary manifest, verify original article bytes and conflict refusal, then reapply only with approval.
5. Rebuild and review the complete broad dry run. Broad conversion requires a distinct approval bound to report/data hashes and complete successful canary/rollback evidence. Revision, source or dependency drift invalidates approval.
6. After all eligible roots pass, switch stance generation to compact new stubs and membership-only reconciliation. An unchanged identity set returns original article bytes. Removed keys require the lifecycle workflow and never discard caption or prose. Shared pages preserve every other entity kind.
7. Remove StanceSectionGenerator, stance.jinja2, stance-only assembly and obsolete merge rules only after full coverage, real rollback acceptance and the rollback retention window. Keep legacy Stance, existing public tooltip entry points and native guarded deploy/rollback. The last entity conversion, not this one, removes the common merge engine.
