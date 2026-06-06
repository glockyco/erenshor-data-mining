# Cargo Phase 2: Abilities schema (base + per-type detail) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Give spells, skills, and stances Cargo storage via a thin shared `Abilities` base table + per-type `Spells`/`Skills`/`Stances` detail tables joined on `StableKey`, plus an `AbilityClasses(StableKey, Class, RequiredLevel)` child table — implementing spec §5.2 + §6 (`AbilityClasses`).

**Architecture:** Mirror the Item/Character Cargo pattern (`cargoValue` + `cargoStoreText` + `p.cargoStore(frame)` → `frame:preprocess`; `{{#invoke|cargoStore}}` in `<includeonly>`; `#cargo_declare` in `<noinclude>`). The twist: the `Abilities` base is written by **two** templates — `Ability` (spells+skills, dispatched by `Module:Erenshor/Ability`) and `Stance`. The `Ability` template **declares** `Abilities` (+ `Spells`, `Skills`, `AbilityClasses`); the `Stance` template **`#cargo_attach`es** `Abilities` (and declares `Stances`) so `cargorecreatetables` re-parses both surfaces. A single page emits multiple `#cargo_store` calls (base + detail + N class rows).

**Tech Stack:** Lua (Scribunto), LIBRARIAN/Cargo, Python smoke harness (`wiki-dev`), local MediaWiki `http://localhost:8088`.

**Cargo = queryable subset.** Detail tables carry only filter/sort/join columns + single-reference relation StableKeys; the full per-entity field set stays in the Lua data modules for the infobox.

---

## Tables

`Abilities` (base; one row per spell/skill/stance; `Ability` declares, `Stance` attaches):
```
StableKey=String  Page=Page  Name=String  AbilityType=String  Image=File  Description=Text
```
`AbilityType` ∈ {`Spell`,`Skill`,`Stance`}.

`Spells` (detail; declared by `Ability`). Column ← Lua key:
```
StableKey←stableKey  Page←page  Name←name  Type←type  Line←line
RequiredLevel←requiredLevel  ManaCost←manaCost  CastTimeTicks←castTimeTicks
CooldownSeconds←cooldownSeconds  DurationTicks←durationTicks  Range←range
DamageType←damageType  TargetDamage←targetDamage  TargetHealing←targetHealing
CasterHealing←casterHealing  ShieldingAmt←shieldAmount  Aggro←aggro
SimUsable←simUsable(bool)  SelfOnly←selfOnly(bool)  GroupEffect←groupEffect(bool)
CrowdControl←crowdControl(bool)  GrantInvisibility←grantInvisibility(bool)
CannotInterrupt←cannotInterrupt(bool)  Jolt←jolt(bool)  NoResonate←noResonate(bool)
StatusEffect←statusEffectStableKey  AddProc←addProcStableKey  PetToSummon←petToSummonStableKey
```
(CastTimeTicks: raw ticks — see Deviations.)

`Skills` (detail; declared by `Ability`). Column ← Lua key:
```
StableKey←stableKey  Page←page  Name←name  Type←type
CooldownSeconds←(cooldownTicks/60)  Range←range  SkillPower←skillPower  PercentDmg←percentDmg
DamageType←damageType  Require2H←require2h  RequireDualWield←requireDw  RequireBow←requireBow
RequireShield←requireShield  RequireBehind←requireBehind
StanceToUse←stanceStableKey  EffectToApply←effectStableKey
CastOnTarget←castOnTargetStableKey  SpawnOnUse←spawnOnUseStableKey
```
(Skill cooldown is stored as ticks in data (`cooldownTicks`); the display divides by 60. Store `CooldownSeconds` as the divided value to match the Spells column unit — this conversion (÷60) is the documented one in `Skill.lua`, unlike the spell cast-time tick rate, so it is safe.)

`Stances` (detail; declared by `Stance`). Column ← Lua key:
```
StableKey←stableKey  Page←page  Name←name
MaxHpMod←maxHpMod  DamageMod←damageMod  ProcRateMod←procRateMod  DamageTakenMod←damageTakenMod
SelfDamagePerAttack←selfDamagePerAttack  AggroGenMod←aggroGenMod  SpellDamageMod←spellDamageMod
SelfDamagePerCast←selfDamagePerCast  LifestealAmount←lifestealAmount  ResonanceAmount←resonanceAmount
StopRegen←stopRegen(bool)
```

`AbilityClasses` (child; declared by `Ability`). One row per (ability, class):
```
StableKey=String  Class=String  RequiredLevel=Integer
```
- Spells: iterate `spell.classes` (flat name list); `RequiredLevel = spell.requiredLevel` for each.
- Skills: iterate `skill.classLevels`; `Class = entry.className` (canonical, join-safe), `RequiredLevel = entry.level`.
- Stances: none.

`Class` stores the **canonical** class name (`className`), not the display name (`displayName`, e.g. "Windblade"), so it joins/filters consistently with item `Classes` and the 6-class roster.

---

## Decomposition (atomic commits, each smoke+gate verified)

**Phase 2a — `Abilities` base + `Spells` + `Skills` + `AbilityClasses`** (the `Ability` template surface; spells and skills share it, so they land together — splitting them would require a no-op branch in the shared dispatcher, which we won't ship):
- `Spell.lua`: add `cargoValue` + `cargoStoreText(spell, pageTitle)` emitting the `Abilities` base row, the `Spells` detail row, and N `AbilityClasses` rows; expose nothing new (Ability dispatches).
- `Skill.lua`: same, emitting base + `Skills` + `AbilityClasses`.
- `Ability.lua`: add `p.cargoStore(frame)` that resolves via `moduleFor(args)` and returns the selected module's `cargoStoreText` (preprocessed). (Spell/Skill expose a `cargoStoreText`-style entry the dispatcher can call, e.g. `p.cargoStoreText(args, pageTitle)`.)
- `Ability.wiki`: add `{{#invoke:Erenshor/Ability|cargoStore}}` before `status` in `<includeonly>`; add `#cargo_declare` for `Abilities`, `Spells`, `Skills`, `AbilityClasses` in `<noinclude>`. Add `Ability/CargoDeclare.wiki` mirror.
- Harness: add `Abilities`/`Spells`/`Skills`/`AbilityClasses` to `cargo_check.py` `CARGO_TABLES`+`CARGO_TEMPLATES_BY_TABLE` (template `Ability` for all four), `CARGO_*_FIELDS` tuples + TSV fixtures in `wiki-dev/smoke/cargo.py`, `--cargo-*` args, load+check calls. Add Cargo fixture TSVs + smoke entries for the existing spell/skill fixture pages.
- Verify: import + smoke + cargo_check + full gate.

**Phase 2b — `Stances` + attach `Abilities`** (the `Stance` template surface):
- `Stance.lua`: add `cargoValue` + `cargoStoreText` emitting the `Abilities` base row (`AbilityType=Stance`) + the `Stances` detail row; `p.cargoStore(frame)`.
- `Stance.wiki`: add `{{#invoke:Erenshor/Stance|cargoStore}}`; add `#cargo_attach:_table=Abilities` + `#cargo_declare` for `Stances` in `<noinclude>`. Add `Stance/CargoDeclare.wiki`.
- Harness: add `Stances` table (template `Stance`); the `Abilities` recreate must re-parse attached Stance pages (verify recreate picks them up). Stance Cargo fixtures + smoke entries.
- Verify.

**Phase 2c — two-spell multi-entity fixture** (now that `Spells` exists): a `Regrowth`-style fixture page hosting two `spell:` entities (same name, distinct StableKeys) → two `Abilities`+`Spells` rows; smoke asserts both render; cargo_check requires both rows. Completes spec §11's two-spell case.

---

## Deviations (flagged per maintainer request)
- **`Spells.CastTimeTicks`** stores raw `castTimeTicks` rather than the spec's `CastTimeSeconds`. The data is ticks; the seconds shown in the infobox come from a display conversion whose tick rate is not obviously a clean ÷60 (fixture `castTimeTicks=120` renders as a non-2.0s value). Storing raw ticks is equally sortable/filterable and avoids encoding an unverified conversion. Skill `CooldownSeconds` keeps seconds because `Skill.lua`'s ÷60 is explicit. Reconsider if a unified seconds unit is preferred.

## Self-Review
- Coverage: implements §5.2 (base+detail), §6 `AbilityClasses`, §11 two-spell case. Reverse relations (used-by, items-with-effect, taught-by) are Phase 3, not here.
- Types: column→key mappings taken verbatim from the data-module field maps (`spells.py`/`skills.py`/`stances.py`); bools stored via `cargoValue` (`yes`/`no`); `AbilityClasses.Class` = canonical `className`.
- Attach: `#cargo_attach` is new to this wiki; Phase 2b must verify `cargorecreatetables` on the `Ability`-declared `Abilities` table rebuilds stance rows from attached `Stance` pages.
