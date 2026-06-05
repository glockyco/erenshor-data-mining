# Game-faithful spell & skill tooltips — Implementation Plan

> Execute task-by-task with TDD. Lua correctness is verified by the in-wiki
> `Module:Erenshor/*/testcases` modules run on the local MediaWiki harness
> (`http://localhost:8088`), the same mechanism used for the item tooltip.

**Goal:** Add `{{SpellTooltip}}` and `{{SkillTooltip}}` surfaces that reproduce the
in-game spellbook/skillbook tooltips, extracting the shared spell-detail
rendering primitives into `Module:Erenshor/Ability/Common` (and refactoring the
item tooltip onto it) so there is no duplication.

**Architecture:** Presentation Lua modules build the in-game DOM with `mw.html`,
reusing the live `item-tooltip-*` / `item-spell-*` CSS classes (CSS lives on the
wiki, not the repo), driven by the generated `Module:Erenshor/Data/*` modules.
Content/order is authoritative from the decompiled game source.

**Tech stack:** Lua/Scribunto modules, MediaWiki templates, local Docker
MediaWiki harness, `MediaWikiClient.expand_templates` for harness verification.

**Authoritative game sources:**
- Spell tooltip: `variants/main/unity/.../SpellbookSlot.cs:150-275`
- Skill tooltip: `variants/main/unity/.../SkillbookSlot.cs:146-156`
- Item tooltip (already implemented): `variants/main/unity/.../ItemInfoWindow.cs`

**Faithfulness rules:** match the game's content, order, labels, colors, and
which rows appear. Permitted conveniences only: render linked abilities/effects
as `{{AbilityLink}}`/page links and stances as links. No invented rows.

---

## File structure

- `wiki/modules/Erenshor/Ability/Common.lua` — NEW. Shared primitives: `num`,
  `truthy`, `isBlank`, `signedMod(value, suffix)`, `colorDamageType(type)`,
  `spellDuration(spell)`, `spellName(SpellData, key)`, `spellLink(SpellData, key)`,
  and `STAT_MODS` (ordered `{label, key}` pairs, HP→Attack Roll Modifier).
- `wiki/modules/Erenshor/Item/Tooltip.lua` — MODIFY. Use `Ability/Common` for the
  shared primitives; keep item-specific suffixes (`haste`/`lifesteal` → `%`) and
  the appended `Resonance` row so output is byte-identical.
- `wiki/modules/Erenshor/Spell/Tooltip.lua` — NEW. Spellbook tooltip renderer.
- `wiki/modules/Erenshor/Skill/Tooltip.lua` — NEW. Skillbook tooltip renderer.
- `wiki/modules/Erenshor/Spell.lua` — MODIFY. `require` Spell/Tooltip; add
  `p.renderTooltip(args, pageTitle)` and `p.tooltip(frame)`.
- `wiki/modules/Erenshor/Skill.lua` — MODIFY. Same for Skill/Tooltip.
- `wiki/templates/SpellTooltip.wiki`, `wiki/templates/SkillTooltip.wiki` — NEW.
- `wiki/modules/Erenshor/{Item,Spell,Skill}/testcases.lua` — MODIFY (add tooltip
  assertions).

Harness deploy/verify helper (used in every verification step): edit the module
page on the harness and run the testcases module, e.g.

```python
from erenshor.infrastructure.wiki.client import MediaWikiClient
c = MediaWikiClient(api_url="http://localhost:8088/api.php", rate_limit_delay=0.0)
# deploy a module file:
content = open("wiki/modules/Erenshor/Spell/Tooltip.lua").read()
base = c.get_page_revision_metadata("Module:Erenshor/Spell/Tooltip", assertion="bot")
c.safe_edit_page(title="Module:Erenshor/Spell/Tooltip", content=content,
                 base_revision=base, summary="dev", assertion="bot", assert_user=None)  # or safe_create
# run testcases:
print(c.expand_templates("{{#invoke:Erenshor/Spell/testcases|run}}"))
```

---

## Task 1: Extract shared primitives into `Ability/Common`

**Files:** Create `wiki/modules/Erenshor/Ability/Common.lua`; Modify
`wiki/modules/Erenshor/Item/Tooltip.lua`.

- [ ] **Step 1:** Create `Ability/Common.lua` exposing `num`, `truthy`,
  `isBlank`, `signedMod(value, suffix)` (returns
  `<span class="item-spell-positive">+N</span>` / `item-spell-negative`),
  `colorDamageType(type)` (Physical `#FFFFFF`, Magic `#8080FF`, Elemental
  `#FFA500`, Poison `#50C878`, Void `#B030B0`, else raw — from
  `SpellbookSlot.GetColoredDamageType`), `spellDuration(spell)` (instant /
  `Effect Duration: ticks*3 sec` / `Damage over time: ticks*3 sec`),
  `spellName(SpellData, key)`, `spellLink(SpellData, key)`, and `STAT_MODS`
  (ordered `{label,key}`: Hitpoints/hp, Armor Class/ac, Mana/mana, Strength/str,
  Dexterity/dex, Endurance/end, Agility/agi, Wisdom/wis, Intelligence/int,
  Charisma/cha, Magic Resist/mr, Elemental Resist/er, Poison Resist/pr, Void
  Resist/vr, Movement Speed/movementSpeed, Damage Shield/damageShield, Haste/haste,
  Lifesteal/lifesteal, Attack Roll Modifier/atkRollModifier).

- [ ] **Step 2:** Refactor `Item/Tooltip.lua` to `require("Module:Erenshor/Ability/Common")`
  and use its `num`/`truthy`/`isBlank`/`signedMod`/`spellDuration`/`spellName`/
  `spellLink`. Replace the local `SPELL_MODS` with `Common.STAT_MODS`, applying
  the item suffixes (`haste`→`%`, `lifesteal`→`%`) and appending the existing
  `Resonance` row, so the rendered output is unchanged.

- [ ] **Step 3 (verify, must stay green):** Deploy `Ability/Common` and the
  modified `Item/Tooltip` to the harness; run
  `{{#invoke:Erenshor/Item/testcases|run}}`. Expected: `PASS`. The item tooltip
  output must be identical to before.

- [ ] **Step 4: Commit** — `refactor(wiki): extract shared ability tooltip primitives`

## Task 2: Spell tooltip module + testcases

**Files:** Create `wiki/modules/Erenshor/Spell/Tooltip.lua`; Modify
`wiki/modules/Erenshor/Spell.lua`, `wiki/modules/Erenshor/Spell/testcases.lua`.

- [ ] **Step 1 (red):** In `Spell/testcases.lua`, add assertions on
  `Spell.renderTooltip({ stablekey = "spell:ancient_presence" }, "Ancient Presence")`:
  contains `Effect Duration: 12 sec`, `Spell Type: Beneficial`, `Mana Cost: 0`,
  `Damage Shield <span class="item-spell-positive">+40</span>`,
  `Hitpoints <span class="item-spell-positive">+500</span>`,
  `Strength <span class="item-spell-positive">+20</span>`, `Group Effect`; and on
  `spell:ember` (Damage): contains `Instant Effect`, `Mana Cost: 25`,
  `Damage: 60`, `Cast Time: 2.0 sec`, and the Elemental-colored Resist Type.

- [ ] **Step 2 (red run):** Deploy `Spell/testcases` only; run it. Expected:
  FAIL (`renderTooltip` nil / module missing).

- [ ] **Step 3 (green):** Create `Spell/Tooltip.lua` reproducing
  `SpellbookSlot.cs:150-275` in order, using `Ability/Common`: duration line →
  `Spell Type: <type>` → `Mana Cost: <manaCost>` → `Damage: <targetDamage>`
  (`/ tick` when duration, only if `> 0`) → `Cast Time: <castTimeTicks/60> sec`
  → `Cooldown: <cooldownSeconds> sec` → `Resist Type: <colored damageType>`
  (when `targetDamage>0` or `type=="StatusEffect"` or `taunt`) → flags Lifetap/
  Group Effect/Stuns Target/Charms Target/Roots Target/`Taunt: <aggro> aggro` →
  `Apply Effects on Target: <AbilityLink/page link to statusEffectStableKey>` →
  nonzero `STAT_MODS` (lifesteal suffix `%`, haste no suffix — matching the game)
  → `SpecialDescriptor`. Title = spell name. Reuse `item-spell-*` classes.
  In `Spell.lua`: `local Tooltip = require("Module:Erenshor/Spell/Tooltip")`,
  `function p.renderTooltip(args, pageTitle) ... Tooltip.render(p.resolve(...)) end`,
  `function p.tooltip(frame) return p.renderTooltip(templateArgs(frame), currentTitleText()) end`.

- [ ] **Step 4 (green run):** Deploy `Spell`, `Spell/Tooltip`, `Spell/testcases`;
  run `{{#invoke:Erenshor/Spell/testcases|run}}`. Expected: `PASS`.

- [ ] **Step 5: Commit** — `feat(wiki): add game-faithful spell tooltip`

## Task 3: Skill tooltip module + testcases

**Files:** Create `wiki/modules/Erenshor/Skill/Tooltip.lua`; Modify
`wiki/modules/Erenshor/Skill.lua`, `wiki/modules/Erenshor/Skill/testcases.lua`.

- [ ] **Step 1 (red):** Add assertions on `Skill.renderTooltip(...)`: an
  activatable skill → title contains `<Name> - Activatable` and body contains
  `SkillDesc`; a stance-changing skill → body contains `Change Stance`, the
  stance display name, and the stance description. Pick fixtures from
  `wiki-dev/fixtures/modules/Erenshor/Data/Skills.lua` + `Stances.lua`.

- [ ] **Step 2 (red run):** Deploy `Skill/testcases`; run. Expected: FAIL.

- [ ] **Step 3 (green):** Create `Skill/Tooltip.lua` reproducing
  `SkillbookSlot.cs:146-156`: title `<SkillName> - <Activatable|Passive>`
  (Activatable when `type != "Innate"`); body `description`, or when
  `stanceStableKey` is set, `Change Stance` + stance name + stance description
  (join via `mw.loadData("Module:Erenshor/Data/Stances")`). Add `p.renderTooltip`
  + `p.tooltip` to `Skill.lua`.

- [ ] **Step 4 (green run):** Run `{{#invoke:Erenshor/Skill/testcases|run}}`.
  Expected: `PASS`.

- [ ] **Step 5: Commit** — `feat(wiki): add game-faithful skill tooltip`

## Task 4: Template surfaces

**Files:** Create `wiki/templates/SpellTooltip.wiki`, `wiki/templates/SkillTooltip.wiki`.

- [ ] **Step 1:** `SpellTooltip.wiki`:
  `<includeonly>{{#invoke:Erenshor/Spell|tooltip}}</includeonly><noinclude>…doc…</noinclude>`
  and `SkillTooltip.wiki` analogously with `Erenshor/Skill`.

- [ ] **Step 2 (verify):** Deploy both templates to the harness; create a temp
  page `{{SpellTooltip|stablekey=spell:ancient_presence}}` and
  `{{SkillTooltip|stablekey=skill:…}}`; confirm rendered output matches the
  module output (no template/parse errors).

- [ ] **Step 3: Commit** — `feat(wiki): add SpellTooltip and SkillTooltip surfaces`

## Task 5: Re-verify item tooltip against game source

**Files:** Modify `wiki/modules/Erenshor/Item/Tooltip.lua` (only if drift found).

- [ ] **Step 1:** Read `ItemInfoWindow.cs` proc/click/worn spell-detail rows and
  compare field-by-field against `Item/Tooltip.lua spellDetails` (labels, order,
  haste `%` vs no-suffix, cast-time/worn handling). Note any divergence.

- [ ] **Step 2:** Fix only genuine divergences with a failing item testcase first;
  keep all item testcases green.

- [ ] **Step 3: Commit (if changes)** — `fix(wiki): align item tooltip with game source`

---

## Self-review

- Spec coverage: Category E (audit) → Tasks 1-4; "re-verify ItemTooltip" → Task 5.
- No placeholders: each module step cites the exact game source range for content.
- Type consistency: `renderTooltip(args, pageTitle)` + `tooltip(frame)` mirror the
  item module (`Item.lua:529-636`); `Tooltip.render(<resolved entity>)` mirrors
  `Item/Tooltip.render`.
- Out of scope here: data-generation gaps (Categories A/B) and override-apply —
  tracked as Milestone 10c in `2026-05-29-wiki-lua-migration-next-steps.md`.
