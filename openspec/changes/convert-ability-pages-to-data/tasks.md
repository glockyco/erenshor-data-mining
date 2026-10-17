# Tasks

## 1. feat(wiki) render exact spell and skill article identities

- [ ] 1.1 Add AbilityData and the maintained Ability article renderer using exact spell/skill resolvers, leaving Ability parameter-only. Verify wrong/missing/duplicate keys, same-name caster/effect variants and kind-specific dispatch through Scribunto behavior tests.
- [ ] 1.2 Render current visible fields plus applicable targeting/range, resist modifiers, skill requirements, mana restoration, class levels and stacking lines from existing immutable data. Verify native cooldown/duration precision, Base Skill Power labeling, distinct effect links and existing skill itemsWithEffect relations without a second source/class selector.
- [ ] 1.3 Preserve exact imagecaption bytes and explicit blank presentation, support the stance slice's validated external-notice control, and populate the same EntityLifecycle supplement for keyed spell/skill records using the neutral loader. Verify Mana Burst/Mana Call notice behavior, null-key exclusion, unsupported-fact diagnostics and no item lifecycle duplication.
- [ ] 1.4 Add missing Spells/Skills category pages, diagnostic categories and renderer styles. Verify namespace-only Abilities plus type-specific categories, shared-page category union and one exact keyed inline tooltip per root while old tooltip entry points remain usable.
- [ ] 1.5 Extend existing editor/data-contract documentation in place and add local fixture/smoke cases for ordinary spell, skill, multi-class, caster/effect, historical and unkeyed legacy pages. Verify local MediaWiki action=parse output and existing Spell/Skill Scribunto testcases rather than source-text or wording snapshots.

## 2. feat(wiki) bind ability roots to shared guarded conversion

- [ ] 2.1 Add only the ability-specific descriptor/adapter to the parent's neutral converter, with spell/skill key kinds, exact caption ownership and key-bound SpellTooltip/SkillTooltip companions. Verify reordered multi-roots, unrelated shared roots, prose/caption byte preservation and duplicate-parameter/identity refusal in behavior tests.
- [ ] 2.2 Bind companion removal to checkpointed bot text and revision proof. Verify nested manual companions are not removed by proximity and an unowned duplicate keyed tooltip blocks conversion rather than breaking hover selection.
- [ ] 2.3 Add complete inventory dispositions for current-generation roots versus legacy-only excluded, historical or manual roots. Verify no name fallback for Fishing, Pocket Rift or Stance: Reckless, no hardcoded title allowlist, and a receipt cannot claim preserved legacy roots were converted.
- [ ] 2.4 Reuse native guarded edits, manifests, comparisons and limits with no type-specific writer or duplicate migration engine. Update existing publishing documentation for the descriptor and verify dry-run purity, fetched-revision conflicts, stale source/data approval refusal and exact rollback through orchestration tests.

## 3. test(wiki) accept full-data ability rendering and comparisons

- [ ] 3.1 Import full generated Spells, Skills, Links, lifecycle and transitive item dependencies into the local wiki. Exercise both layouts, narrow widths, captions, long source/used-by lists, historical notices and reordered caster/effect pages in a browser, save local screenshots and restore normal fixtures afterward.
- [ ] 3.2 Exercise keyed hover/focus selection for every root on a shared target, ordinary navigation and an item with a visible inline spell tooltip. Verify no wrong-variant card, duplicate keyed card or new right-click details action.
- [ ] 3.3 Generate the complete fresh production legacy/candidate text-parse comparison for every eligible page, plus revision-bound preserve dispositions for legacy-only users. Verify all text/category/link/image/tooltip differences, including new Spells/Skills categories and newly visible mechanics, are reviewed with no provisional dependencies or unresolved ownership findings.
- [ ] 3.4 Measure generated page sizes and actual enforcing Lua/parser metrics with the largest source/used-by pages, effect-heavy roots and all multi-root pages. Verify at least 25 percent headroom below observed enforcing limits and block approval when required metrics or complete dependencies are missing.

## 4. chore(wiki) publish reversible ability conversion

- [ ] 4.1 Recheck free AbilityData/renderer titles, review the complete repository-page dry run and local screenshots, and obtain explicit approval for exact data/category/reader publication. Verify dependency order and fresh production text parses before writing articles.
- [ ] 4.2 Review the complete conversion dry run and obtain separate approval for ordinary spell, skill, multi-root, class/item-relation and historical canaries. Verify fresh production parse/browser behavior, restore exact original bytes with the manifest and demonstrate rollback refuses intervening edits.
- [ ] 4.3 Refresh full comparisons, limits and live inventories after canaries. Obtain distinct broad approval bound to report/source/data hashes and successful rollback evidence. Verify every eligible current-generation root converted, all legacy-only dispositions retained and revision drift refused.

## 5. refactor(wiki) retire spell and skill full-article generation

- [ ] 5.1 Switch spell/skill generation to compact new stubs and exact membership-only reconciliation after the accepted receipt. Verify unchanged membership preserves original bytes, additions retain editorial/unrelated roots and removals require lifecycle handling.
- [ ] 5.2 After the accepted rollback retention window, remove SpellSectionGenerator, SkillSectionGenerator, ability.jinja2 and obsolete spell/skill-only assembly/merge code. Update existing workflow documentation and concise player-facing changelog in the same unit. Verify legacy Ability and public tooltips remain usable for manual pages and shared unconverted-type generation is intact.
- [ ] 5.3 Run narrow changed-path Python checks, local Scribunto/smoke/browser integration and the repository CI command once the coherent implementation is complete. Record exercised results and complete eligible versus retained-legacy coverage in this change before archive.
