# Cargo Phase 2: Abilities schema (base + per-type detail) — Implementation Plan

> **⚠ Superseded (2026-06-07) on the Cargo storage model.** Research against the
> wiki.gg platform docs + production wikis (River/Leaguepedia, PoE) reversed two
> choices below: there is **no shared `Abilities` base table** (per-type `Spells`/
> `Skills`/`Stances` + an `AbilityClasses` junction declared by a dedicated
> `Template:AbilityClasses`), and storage is **centralized in `Module:Erenshor/Cargo`
> via `frame:callParserFunction('#cargo_store:', …)`** (wiki.gg disables the native Lua
> store; the hand-built-wikitext + `frame:preprocess` path is fragile). The authoritative
> design is now `2026-06-07-cargo-storage-architecture-research.md` + umbrella spec
> §7.2/§8. Prereqs A and B below are done and unaffected; the per-type detail column
> lists below remain valid. Ignore the "base table / `Spell` declares Abilities /
> `#cargo_attach` the base" wording.
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Give spells, skills, and stances Cargo storage via a thin shared `Abilities` base table + per-type `Spells`/`Skills`/`Stances` detail tables joined on `StableKey`, plus an `AbilityClasses(StableKey, Class, RequiredLevel)` child table — implementing spec §5.2 + §6.

**Architecture:** Mirror the Item/Character Cargo pattern (`cargoValue` + `cargoStoreText` + `p.cargoStore(frame)` → `frame:preprocess`; `{{#invoke|cargoStore}}` in `<includeonly>`; `#cargo_declare` in `<noinclude>`). Spells, skills, and stances are three distinct entity types with three distinct templates and three detail tables; they share one thin `Abilities` base. Because a base table written by multiple templates needs one declarer + others attaching, the `Spell` template **declares** `Abilities` (+ `AbilityClasses`); `Skill` and `Stance` **`#cargo_attach`** `Abilities` (and `Skill` attaches `AbilityClasses`). Each detail table is declared by its own template. A single page emits multiple `#cargo_store` calls (base + detail + N class rows).

**Two prerequisite cleanups (confirmed with maintainer) precede the Cargo work** so it is built on a clean, correct base:

- **Prereq A — times in seconds at generation.** Today the data modules carry raw ticks (`castTimeTicks`, `durationTicks`, skill `cooldownTicks`) and the Lua display layer converts. The game's own conversions (verified in `ItemInfoWindow.cs`/`SpellbookSlot.cs`) are: spell cast `SpellChargeTime/60`, spell duration `SpellDurationInTicks*3`, spell cooldown already seconds, skill cooldown `cooldownTicks/60`. Move these conversions into the **Python generators** so the data modules carry seconds (`castTimeSeconds`, `durationSeconds`, `cooldownSeconds`); the Lua accessors then only format. The wiki — display and Cargo — deals only in seconds.
- **Prereq B — split `{{Ability}}` into `{{Spell}}` + `{{Skill}}`.** The shared `{{Ability}}` infobox + `Module:Erenshor/Ability` stablekey-prefix dispatcher is a legacy artifact. Spells and skills are distinct entities; give each its own template invoking `Module:Erenshor/Spell`/`Skill` directly (modules already exist). Retire `Template:Ability` and `Module:Erenshor/Ability`. **Keep `Module:Erenshor/AbilityLink`** (cross-type link resolution is legitimate). The live `Template:Ability` is transcluded only by generated spell/skill pages, so regenerating them onto the new templates orphans it; the deploy bot can't delete pages, so the orphaned live page is a one-time manual delete.

**Cargo = queryable subset.** Detail tables carry only filter/sort/join columns + single-reference relation StableKeys; the full per-entity field set stays in the Lua data modules for the infobox.

**Tech Stack:** Lua (Scribunto), LIBRARIAN/Cargo, Python generators + smoke harness (`wiki-dev`), local MediaWiki `http://localhost:8088`.

---

## Tables

`Abilities` (base; one row per spell/skill/stance; **declared by `Spell`**, attached by `Skill` + `Stance`):
```
StableKey=String  Page=Page  Name=String  AbilityType=String  Image=File  Description=Text
```
`AbilityType` ∈ {`Spell`,`Skill`,`Stance`}.

`Spells` (detail; declared by `Spell`). Column ← Lua key:
```
StableKey←stableKey  Page←page  Name←name  Type←type  Line←line
RequiredLevel←requiredLevel  ManaCost←manaCost  CastTimeSeconds←castTimeSeconds
CooldownSeconds←cooldownSeconds  DurationSeconds←durationSeconds  Range←range
DamageType←damageType  TargetDamage←targetDamage  TargetHealing←targetHealing
CasterHealing←casterHealing  ShieldingAmt←shieldAmount  Aggro←aggro
SimUsable←simUsable(bool)  SelfOnly←selfOnly(bool)  GroupEffect←groupEffect(bool)
CrowdControl←crowdControl(bool)  GrantInvisibility←grantInvisibility(bool)
CannotInterrupt←cannotInterrupt(bool)  Jolt←jolt(bool)  NoResonate←noResonate(bool)
StatusEffect←statusEffectStableKey  AddProc←addProcStableKey  PetToSummon←petToSummonStableKey
```

`Skills` (detail; declared by `Skill`). Column ← Lua key:
```
StableKey←stableKey  Page←page  Name←name  Type←type
CooldownSeconds←cooldownSeconds  Range←range  SkillPower←skillPower  PercentDmg←percentDmg
DamageType←damageType  Require2H←require2h  RequireDualWield←requireDw  RequireBow←requireBow
RequireShield←requireShield  RequireBehind←requireBehind
StanceToUse←stanceStableKey  EffectToApply←effectStableKey
CastOnTarget←castOnTargetStableKey  SpawnOnUse←spawnOnUseStableKey
```

`Stances` (detail; declared by `Stance`). Column ← Lua key:
```
StableKey←stableKey  Page←page  Name←name
MaxHpMod←maxHpMod  DamageMod←damageMod  ProcRateMod←procRateMod  DamageTakenMod←damageTakenMod
SelfDamagePerAttack←selfDamagePerAttack  AggroGenMod←aggroGenMod  SpellDamageMod←spellDamageMod
SelfDamagePerCast←selfDamagePerCast  LifestealAmount←lifestealAmount  ResonanceAmount←resonanceAmount
StopRegen←stopRegen(bool)
```

`AbilityClasses` (child; **declared by `Spell`**, attached by `Skill`). One row per (ability, class):
```
StableKey=String  Class=String  RequiredLevel=Integer
```
- Spells: iterate `spell.classes` (flat name list); `RequiredLevel = spell.requiredLevel` for each.
- Skills: iterate `skill.classLevels`; `Class = entry.className` (canonical), `RequiredLevel = entry.level`.
- Stances: none.

`Class` stores the **canonical** class name (`className`), not display name (`displayName`, e.g. "Windblade"), to join/filter consistently with item `Classes` and the 6-class roster.

---

## Decomposition (atomic commits, each smoke + full gate verified, spec progress updated per commit)

**Prereq A — times → seconds at generation:**
- `spells.py`: emit `castTimeSeconds` (`spell_charge_time/60`), `durationSeconds` (`spell_duration_in_ticks*3`); `cooldownSeconds` already correct. `skills.py`: emit `cooldownSeconds` (`cooldown_ticks/60`).
- `Spell.lua`/`Skill.lua`: accessors format the seconds values directly (drop the tick conversions).
- Update fixtures (`Data/Spells.lua`, `Data/Skills.lua`), Lua testcases (display strings unchanged; data keys change), and Python module snapshot tests.
- Verify: smoke + full gate.

**Prereq B — split `{{Ability}}` → `{{Spell}}` + `{{Skill}}`:**
- Create `Template:Spell` + `Template:Skill` invoking `Module:Erenshor/Spell`/`Skill` (`field`/`status`). Delete `Template:Ability` + `Module:Erenshor/Ability` (+ any Ability dispatcher testcase). Keep `AbilityLink`.
- Repoint the page generator that emits spell/skill infoboxes (and fixture pages `Minor_Lightning`, `Ancient_Presence`, `Backstab`, `Stance:_Aggressive`) to `{{Spell}}`/`{{Skill}}`. Update smoke testcase pages (`Lua Spell Smoke`/`Lua Skill Smoke` already test `Module:Erenshor/Spell`/`Skill`).
- Verify: smoke (all spell/skill pages still render) + full gate. Note the orphaned live `Template:Ability` for manual deletion.

**Phase 2a — `Spell` template Cargo** (declares `Abilities`, `Spells`, `AbilityClasses`):
- `Spell.lua`: add `cargoValue` + `cargoStoreText` emitting base + `Spells` + N `AbilityClasses` rows; `p.cargoStore(frame)`.
- `Spell.wiki`: `{{#invoke:Erenshor/Spell|cargoStore}}` in `<includeonly>`; `#cargo_declare` `Abilities`/`Spells`/`AbilityClasses` in `<noinclude>` + `Spell/CargoDeclare.wiki`.
- Harness: `CARGO_TABLES`/templates, `CARGO_*_FIELDS`, TSV fixtures, args, load+check, smoke entries for spell pages.
- Verify.

**Phase 2b — `Skill` template Cargo** (attaches `Abilities` + `AbilityClasses`; declares `Skills`):
- `Skill.lua`: `cargoStoreText` emitting base + `Skills` + N `AbilityClasses`; `p.cargoStore`.
- `Skill.wiki`: `cargoStore` invoke; `#cargo_attach` `Abilities` + `AbilityClasses`; `#cargo_declare` `Skills`.
- Harness + fixtures + smoke for skill pages. Verify (incl. that `Abilities`/`AbilityClasses` recreate picks up attached skill pages).

**Phase 2c — `Stance` template Cargo** (attaches `Abilities`; declares `Stances`):
- `Stance.lua`: `cargoStoreText` (base `AbilityType=Stance` + `Stances`); `p.cargoStore`.
- `Stance.wiki`: `cargoStore` invoke; `#cargo_attach` `Abilities`; `#cargo_declare` `Stances`.
- Harness + fixtures + smoke. Verify recreate of `Abilities` picks up attached stance pages.

**Phase 2d — two-spell multi-entity fixture**: a `Regrowth`-style page hosting two `spell:` entities (same name, distinct StableKeys) → two `Abilities`+`Spells` rows; smoke asserts both render; cargo_check requires both. Completes spec §11's two-spell case.

---

## Self-Review
- Coverage: implements §5.2 (base+detail), §6 `AbilityClasses`, §11 two-spell case, plus the confirmed template split and seconds cleanup. Reverse relations (used-by, items-with-effect, taught-by) are Phase 3.
- Types: column→key mappings from the data-module field maps; bools via `cargoValue` (`yes`/`no`); `AbilityClasses.Class` = canonical `className`; times are seconds (Prereq A).
- Attach: `#cargo_attach` is new to this wiki; 2b/2c must verify `cargorecreatetables` on the `Spell`-declared `Abilities`/`AbilityClasses` rebuilds rows from attached `Skill`/`Stance` pages.
