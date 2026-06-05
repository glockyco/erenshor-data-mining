# Semantic Link Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementation subagents are explicitly out of scope for this work.

**Goal:** Replace raw returned cross-page link template strings with a shared, typed, Lua-rendered semantic link system that supports item, ability, quest, character, zone, faction, and class references.

**Architecture:** Public templates remain the stable article-facing API (`ItemLink`, `AbilityLink`, `QuestLink`, `CharacterLink`, `ZoneLink`, `FactionLink`, `ClassLink`). A new shared `Module:Erenshor/Link` renders those semantic links directly from Lua, including icon/link markup and future-friendly CSS/data attributes. Generated Lua data stores typed reference tables instead of unexpanded wikitext template strings.

**Tech Stack:** MediaWiki templates, Scribunto Lua modules, generated `mw.loadData` primitive tables, Python wiki_lua generators, local wiki smoke harness, Cargo local validation.

---

## Planned commits

1. `docs(wiki): plan semantic link architecture`
   - Add this plan.

2. `feat(wiki): add semantic link renderer`
   - Add `Module:Erenshor/Link` and templates for `ItemLink`, `AbilityLink`, `QuestLink`, `CharacterLink`, `ZoneLink`, `FactionLink`, and `ClassLink`.
   - Keep existing public template names working.
   - Add Lua testcases for every link kind.

3. `feat(wiki): emit typed reference links`
   - Convert generated relationship/provenance fields from raw template-call strings to typed reference tables.
   - Render typed references in `Item`, `Spell`, `Skill`, and `Character` field accessors.
   - Update fixture data, Lua testcases, and smoke expectations.

4. `test(wiki): validate semantic link cutover`
   - Import local wiki pages, run smoke/Cargo validation, add evidence to local validation docs if needed.

---

## Current problem

Scribunto return strings are inserted after template expansion. Returning `{{ItemLink|Abyssal Plate}}` or `{{AbilityLink|Ember Burst}}` from a Lua `#invoke` field accessor therefore renders literal braces on the page instead of expanding the template. Standard `[[...]]` links do render, but replacing semantic link templates with plain links would throw away item/ability/quest semantics and block future tooltip behavior.

The fix is to keep semantic links, but render them directly in Lua instead of returning raw template syntax.

---

## Task 1: Shared link renderer

**Files:**
- Create: `wiki/modules/Erenshor/Link.lua`
- Create: `wiki/modules/Erenshor/Link/testcases.lua`
- Modify: `wiki/templates/ItemLink.wiki`
- Modify: `wiki/templates/AbilityLink.wiki`
- Create: `wiki/templates/QuestLink.wiki`
- Create: `wiki/templates/CharacterLink.wiki`
- Create: `wiki/templates/ZoneLink.wiki`
- Create: `wiki/templates/FactionLink.wiki`
- Create: `wiki/templates/ClassLink.wiki`
- Modify: `wiki-dev/fixtures/smoke.tsv`

### Steps

- [ ] Add `Module:Erenshor/Link/testcases.lua` with failing tests for:
  - `Link.render({ kind = "item", page = "Abyssal Plate" })` includes `class="erenshor-link erenshor-link--item"`, `data-erenshor-kind="item"`, item icon markup, and `[[Abyssal Plate]]`.
  - `Link.render({ kind = "ability", stableKey = "spell:minor_lightning" })` matches current `AbilityLink` behavior: icon plus styled link.
  - `Link.render({ kind = "quest", page = "Reward Quest" })` matches live `QuestLink`: quest icon plus quest page link.
  - `character`, `zone`, `faction`, and `class` render semantic spans with normal page links and kind-specific CSS/data attributes.
  - `imageonly = "1"` suppresses text for item and ability links.

- [ ] Run local smoke after importing the testcase fixture and confirm the new testcase fails because `Module:Erenshor/Link` does not exist.

- [ ] Implement `Module:Erenshor/Link.lua`:
  - Parse template args via `Module:Erenshor/Args`.
  - Render one semantic wrapper `<span>` per link with `erenshor-link erenshor-link--KIND` and `data-erenshor-kind`.
  - Include `data-erenshor-key` when `stableKey` is present.
  - Use existing `Format.fileLink` and `Format.pageLink` helpers for safe wikitext link construction.
  - Resolve ability stable keys through `Module:Erenshor/Data/AbilityLinks`.
  - Resolve item stable keys if present through `Module:Erenshor/Data/Items` shards; fall back to explicit page/text/image.
  - Avoid requiring `Module:Erenshor/Item` from `Link.lua` so `Item.lua` can require `Link.lua` later without a circular dependency.

- [ ] Update `ItemLink.wiki` and `AbilityLink.wiki` to delegate to `Module:Erenshor/Link|item` and `Module:Erenshor/Link|ability`.

- [ ] Add `QuestLink`, `CharacterLink`, `ZoneLink`, `FactionLink`, and `ClassLink` wrapper templates that delegate to `Module:Erenshor/Link`.

- [ ] Add a smoke entry for `Module:Erenshor/Link/testcases`.

- [ ] Run `uv run python wiki-dev/import_pages.py` and `uv run python wiki-dev/smoke_test.py`; expect all link testcase assertions to pass.

- [ ] Run targeted style checks for Lua via the commit helper, or manually match existing stylua output if the standalone command is unavailable.

---

## Task 2: Typed reference data from Python generators

**Files:**
- Create: `src/erenshor/application/wiki_lua/links.py`
- Modify: `src/erenshor/application/wiki_lua/items.py`
- Modify: `src/erenshor/application/wiki_lua/spells.py`
- Modify: `src/erenshor/application/wiki_lua/skills.py`
- Modify: `src/erenshor/application/wiki_lua/characters.py`
- Modify tests under `tests/unit/application/wiki_lua/`

### Steps

- [ ] Add failing Python tests that expect typed refs instead of strings:
  - Item provenance `questSource` is a list/table of quest refs, not `"{{QuestLink|...}}"`.
  - Item `componentFor`, `guaranteedDrops`, `dropRates`, and recipe links use item refs.
  - Spell `source` and `itemsWithEffect` use item refs; `usedBy` uses character refs.
  - Skill `source` and `itemsWithEffect` use item refs.
  - Character `spells` uses ability refs and `dropRates` uses item refs.

- [ ] Run the targeted unit tests and confirm they fail on the old string format.

- [ ] Implement `src/erenshor/application/wiki_lua/links.py` with helpers:
  - `link_ref(kind, link, stable_key=None, image=None) -> dict[str, object]`
  - `item_ref(link)`, `quest_ref(link)`, `character_ref(link)`, `zone_ref(link)`, `faction_ref(link)`, `class_ref(name)`.
  - Keep returned tables primitive/static: strings, numbers, booleans, lists, dictionaries.

- [ ] Update generators to store relationship fields as lists of refs or small row tables:
  - Simple list fields: `source`, `itemsWithEffect`, `usedBy`, `spells`, `vendorSource`, `questSource`, `relatedQuest`, `componentFor`, `guaranteedDrops`.
  - Probability fields: rows like `{ link = item_ref(...), probability = 28.3 }`.
  - Quantity fields: rows like `{ link = item_ref(...), quantity = 2 }`.

- [ ] Update Python tests to pass with the typed model.

---

## Task 3: Lua typed-reference rendering

**Files:**
- Modify: `wiki/modules/Erenshor/Item.lua`
- Modify: `wiki/modules/Erenshor/Spell.lua`
- Modify: `wiki/modules/Erenshor/Skill.lua`
- Modify: `wiki/modules/Erenshor/Character.lua`
- Modify: Lua testcases under `wiki/modules/Erenshor/*/testcases.lua`
- Modify fixture data under `wiki-dev/fixtures/modules/Erenshor/Data/`

### Steps

- [ ] Add failing Lua testcase assertions that field accessors render semantic link markup, not raw template strings:
  - Ember Longsword `proceffect` includes `erenshor-link--ability` and `Ember Burst`.
  - Minor Lightning `itemswitheffect` includes two `erenshor-link--item` links.
  - Minor Lightning `used_by` includes `erenshor-link--character`.
  - Quest relationship fields render `erenshor-link--quest`.

- [ ] Run `uv run python wiki-dev/import_pages.py` and `uv run python wiki-dev/smoke_test.py`; confirm the new assertions fail.

- [ ] Require `Module:Erenshor/Link` from the entity modules and render typed refs via a small local join helper:
  - `Link.render(ref)` for each typed ref.
  - `Link.join(refs, "<br>")` for lists.
  - `quantity .. "x " .. Link.render(row.link)` for recipes.
  - `Link.render(row.link) .. " (" .. probability .. "%)"` for drop-rate rows.

- [ ] Update fixture data to typed refs, matching the new generated structure.

- [ ] Update Lua testcases to assert rendered semantic link markup and absence of raw template strings.

---

## Task 4: Local smoke and parser-health guard

**Files:**
- Modify: `wiki-dev/smoke/render.py`
- Modify: `wiki-dev/fixtures/smoke.tsv`
- Modify: `tests/unit/test_wiki_dev_harness.py`
- Modify: `docs/wiki-local-validation/full-lua-cutover.md` if new validation evidence should be recorded.

### Steps

- [ ] Add failing harness test: rendered HTML containing raw `{{ItemLink|`, `{{AbilityLink|`, `{{QuestLink|`, `{{CharacterLink|`, `{{ZoneLink|`, `{{FactionLink|`, or `{{ClassLink|` is rejected.

- [ ] Add smoke expectations for representative pages:
  - `Ember Longsword` contains `erenshor-link--ability` and `Ember_Burst`.
  - `Minor Lightning` contains `erenshor-link--item`, `Abyssal_Plate`, `Healing_Draught`, `erenshor-link--character`, and `A_Grassland_Ogre_Mystic`.
  - A quest relationship page contains `erenshor-link--quest` once a fixture exists.

- [ ] Run the harness test and smoke command to confirm red.

- [ ] Implement the forbidden raw-template marker checks in `wiki-dev/smoke/render.py`.

- [ ] Import pages and validate local rendering:
  - `uv run python wiki-dev/import_pages.py`
  - `uv run python wiki-dev/null_edit.py`
  - `uv run python wiki-dev/smoke_test.py`
  - `uv run python wiki-dev/cargo_check.py`

- [ ] Update `docs/wiki-local-validation/full-lua-cutover.md` with the semantic link validation evidence if this materially changes the cutover gate.

---

## Verification commands

Run before final commit:

```bash
uv run pytest tests/unit/application/wiki_lua tests/unit/test_wiki_dev_harness.py -q
uv run ruff check src/erenshor/application/wiki_lua tests/unit/application/wiki_lua wiki-dev tests/unit/test_wiki_dev_harness.py
uv run mypy src
uv run python wiki-dev/import_pages.py
uv run python wiki-dev/null_edit.py
uv run python wiki-dev/smoke_test.py
uv run python wiki-dev/cargo_check.py
```

Final commits must use the project commit helper for body commits:

```bash
COMMIT_ACTION=commit \
COMMIT_SUBJECT="feat(wiki): ..." \
COMMIT_BODY="..." \
bun skill://commit/commit-helper.ts
```
