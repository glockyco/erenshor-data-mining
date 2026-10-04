## Context

See `proposal.md` for the reason and `specs/wiki-tooltip-parity/spec.md` for the contract. The clean main database currently has 1,537 items, 348 spells, 52 skills, and 7 stances. Of these, 1,516 items, 348 spells, 51 skills, and 6 stances have `is_wiki_generated=1`. A collection must still account for the others and name why they have no page.

The game writes item facts into separate `ItemInfoWindow` TextMeshPro fields. `DisplayItem(item, slotLoc, quantity)` reads player stats for Base DPS and known spell or skill lists for book text. `LoadSpellDetails(spell, worn)` also scales Mana Regen by player level. `SpellbookSlot.ToggleSelect(true)` and `SkillbookSlot.ToggleSelect(true)` write their own name and description fields. The stance tooltip on the wiki reuses the skill that activates that stance. The wiki's standalone spell tooltip combines rows from the spellbook and item spell-details window.

Equipment uses `ItemTooltip` and eight cards from `Module:Erenshor/Item/Quality`. Other items use maintained `Item/*` templates. Spells, skills, and stances use generated Lua modules and their tooltip modules. `wiki-dev/import_pages.py` imports small fixture data modules, not the full generated modules. `erenshor test wiki --warm` imports those fixtures, null-edits them, runs smoke checks, and runs browser tests. It cannot prove whole-build parity as it stands.

## Goals / Non-Goals

**Goals:**

- Keep raw game evidence separate from wiki generation so a shared formatter cannot agree with itself by mistake.
- Compare complete source and target populations by stable key, including eight equipment qualities.
- Make a current-build, source-bound report an enforceable article-deploy precondition.

**Non-Goals:**

- Run the game in CI, write to the live wiki, or infer the current viewer's stats.
- Compare pixels, font metrics, image assets, keyboard hints, or arbitrary community prose.
- Change the approved hover placement or convert article templates to data-backed rendering.

## Decisions

### 1. Collect through the existing HotRepl CLI

Add `wiki capture-tooltips` to `src/erenshor/cli/commands/wiki.py`. The Python orchestration uses the existing HotRepl client in `src/erenshor/application/eval/client.py` and versioned C# source under `src/erenshor/application/wiki_tooltips/`. The script runs in bounded batches after a character and the UI databases have loaded. It reads fields after calls to the game's own methods. A large all-in-one eval reply risks timeout or truncation. A new BepInEx endpoint would duplicate the existing evaluator and add a mod lifecycle to a post-update evidence job.

Use `ItemDatabase.ItemDB` for items and quantities 1, 11 to 15, 2, and 3 for equipment. Read the relevant active and visible `ItemInfoWindow` fields, including name, lore, stats, restrictions, price, effect, book panel, and optional spell details. Close the window between items and restore the window and current selection on every batch outcome. Set each spell and skill on an existing non-hotkey slot, call `ToggleSelect(true)`, and read its `Name` and `Desc`. Capture `LoadSpellDetails` for the spell in each item effect, with the actual worn flag, and for each standalone spell in a non-worn context. Preserve spellbook and details as distinct observations, not one invented window. For stances, resolve each activating skill through `Skill.StanceToUse` and save that skillbook observation against both identities. An unreachable stance such as Reckless is listed as outside publication.
For each field, save `text`, `color`, `faceColor`, and active state. Some item tones come from TextMeshPro properties rather than inline tags, and inactive fields must not become visible facts.

The collection format is sorted JSON with build ID, source method, game `Id` or resource name, stable key, quality, named TextMeshPro fields, raw text, count, and failures. `items.id`, `spells.id`, `skills.id`, and their DB indices join runtime identities to clean-database stable keys. Stances join by the activating skill's reference, not by a guessed name. Fail duplicate IDs or an unmatched published identity. Record the installed Steam build ID and compare it with `code_facts_meta` before accepting a collection. Write a temporary file first and publish the evidence only after all expected runtime and published identities reconcile. The collector must not keep the game running. It closes the launched game through the regular shutdown path, with recorded-process recovery only after a failure.

### 2. Keep character-dependent text out of the parity boundary

No synthetic character is used. Field-level projections exclude the game's `Base DPS` numeric line, the `YOU ALREADY KNOW THIS SPELL` and `YOU ALREADY KNOW THIS SKILL` lines, and the alternate required-level lines suppressed by those known-state messages. `LoadSpellDetails` excludes only its viewer-level-scaled Mana Regen row when `LevelScaledManaRestoration` is nonzero. Control-dependent hold-mouse, Control, and gamepad instruction lines are excluded as UI hints. Class eligibility in `Usable.text` stays in comparison: `DisplayItem` builds that list from `item.Classes`, not the viewer's class. All exclusions use an enumerated field or anchored line rule and appear with counts and examples in the report. An unexpected player-dependent source goes to the report as a failure, not a silent wildcard.

Alternative: set a synthetic character to satisfy every requirement as in the Afallon compendium. Erenshor's loaded player affects weapon DPS, learned-book messages, and some spell details, so that state would add save-dependent assumptions to collection. Omitting only those fields keeps the rest of each window testable.

### 3. Parse TextMeshPro markup into typed lines

Store exact raw strings in the evidence. A Python parser in `src/erenshor/application/wiki_tooltips/` maps supported `<color=...>`, `</color>`, `<i>`, `</i>`, and explicit line breaks to ordered lines and spans with `text`, `tone`, and `italic`. Include named and hex colors observed in real evidence, not arbitrary CSS. TextMeshPro can leave a color active to the end of a field, as `DisplayItem` does for charms. The grammar permits that implicit end, but rejects mismatched closing tags, unknown tags and unknown colors. Never pass native markup to MediaWiki as HTML. A failed parse names the stable key, field, and offending token.
The parser starts with each field's recorded color and face color. Inline tags override that base tone only for their spans. A saved numeric color becomes a semantic tone through the same reviewed mapping as markup colors.

Alternative: strip tags or compare only plain text. That would miss a lost positive, negative, damage, or muted tone. The typed-span approach follows Afallon's decisions 1 and 2 without importing its TypeScript schema.

### 4. Render the complete wiki output in an isolated local stack

Add `wiki check-tooltips`. Use the current `wiki-dev` MediaWiki/Scribunto stack in its own compose project. Extend `wiki-dev/import_pages.py` with a full-data input mode for the generated files under `variants/<variant>/wiki/lua/Erenshor/Data/` and generated article text under `variants/<variant>/wiki/generated/`. Do not replace the warm fixture modules or take ownership of live pages. Reuse its existing importer and `action=parse` pattern. Compare the parsed HTML of each generated article with its stable-key template calls. Select the tooltip subtree for each key, and for equipment each `data-erenshor-quality` card. Parse its text nodes and semantic color classes into the same typed lines. Keep markup for links and icons out of the fact projection, but keep link labels and factual words. Do not derive wiki text from Lua data records in Python: a data-only comparison would miss template, Scribunto, or MediaWiki rendering defects.

Inventory targets from the clean database's `is_wiki_generated` fields and the generated pages. Check that each published identity has exactly one tooltip subtree and that each source identity is either published or listed with a concrete exclusion. Compare every card in sorted key and quality order. A missing item template, rendered script error, duplicate key, missing card, or parser failure is a named failure. A local parse is read-only with respect to the live wiki.

Alternative: use `erenshor test wiki --warm` alone. Its fixture modules are deliberately small and omit most entities. Alternative: call production `action=parse` for every title. That would require live writes before checking new data and would make the gate dependent on the live wiki.

### 5. Compare game facts with explicit context and narrow exceptions

Each wiki line has a source contract: item-window field, spellbook row, spell-details row, or activating skillbook row. Spell tooltips merge the spellbook's Mana Cost and Cooldown with Spell Level, Spell Line, and extra modifiers from spell details. Compare each row against its designated source, rather than merging two game windows and counting their repeated facts twice. Embedded item spell details compare with the corresponding `LoadSpellDetails` observation. Match ordered text and tone within each block. Fix any other discrepancies found across the whole build instead of extending the exception set by accident.

The exception table has only design D14's choices. For equipment, ignore the wiki's quality-card wrapper and compare all eight card bodies to their matching runtime quantities. For damage over time, map only the exact suffix ` / tick` to ` / 3 sec` on the damage row, without changing its number or tone. For Base DPS, check the wiki value against its own declared weapon-damage/delay formula, and exclude only the game's character-dependent value. Record every application by key and line. Navigation links, artwork, and layout are outside text parity. Wiki-only prose in a fact block or an unmatched source fact is a failure.

Use a machine-readable report under `variants/<variant>/wiki/tooltip-parity/` with hashes of the game evidence, clean database, generated article tree, generated data modules, maintained tooltip modules and templates, and comparison policy. Also write a concise human report with counts, exclusions, expected differences, and each actual line difference. The source hashes prevent a cached pass from hiding a new template or data edit.

### 6. Gate article writes, not unrelated publication

Run capture after each game update when the installed build and clean database agree. Run the whole-build check after `wiki generate-lua` and `wiki generate`, before `wiki deploy`. The deploy preflight in `src/erenshor/cli/commands/wiki.py` accepts only a complete passing report whose build ID and source hashes still match. It checks before its first write and also in a dry run with planned writes. No-write deploys do not need a report. Keep the existing online link audit, production per-page parse, revision guard, and rollback manifest. Repository-page and gadget deploys keep their existing review and approval paths. A tooltip source edit invalidates the parity report, so a later article deploy must run parity again.

A failed collection or comparison keeps the previous accepted evidence and report for diagnosis but cannot satisfy the new build's gate. A failed article deploy writes no article because the gate runs before deployment. The local stack is torn down on success or failure. Roll back repository code and generated input changes as one unit. Live article rollback still uses the existing manifest. No production wiki write is part of collection or comparison.

## Risks / Trade-offs

- [UI methods have scene or selection side effects] → Use loaded UI objects, short batches, `finally` cleanup, and a post-batch check of the character and window state.
- [A new TextMeshPro tag or color appears] → Reject it with the raw field in the report, then add a supported tone after review.
- [Rendering every generated page takes time] → Parse in bounded serial batches and save progress, but publish a passing report only after full completion.
- [Current wiki tooltips already disagree with game text] → List every discrepancy and fix the source or renderer before enabling the article gate. Do not add generic allowances.
- [Wiki rendering changes without an article change] → Hash maintained tooltip sources and rerun parity before the next article write.

## Migration Plan

1. Add collection, parsing, local rendering, and comparison with focused behavior checks. Capture a real loaded-character build and inspect a few item, spell, skill, and stance results.
2. Run complete parity for the current build. Repair each unexplained wiki difference and rerun until the full report passes. Do not mask incomplete coverage.
3. Wire the passing report into the article deploy preflight and document the update order in the wiki workflow skill and game data guide. Verify a stale report blocks a dry run and a current report passes.
4. Keep the accepted build's evidence and report in variant output. On rollback, restore code and generated input together, then recheck their report hashes before the next deploy.
