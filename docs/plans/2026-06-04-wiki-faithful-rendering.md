# Faithful Wiki Rendering Plan

> Companion to `docs/plans/2026-05-29-wiki-lua-migration-next-steps.md`. Covers
> Milestones 8d-8f: the item tooltip subsystem, first-class Spell/Skill/Stance
> modeling, and the faithfulness fixes uncovered by auditing the wiki against the
> authoritative game C#.

**Goal:** Every wiki value is faithful to the authoritative game implementation
(the decompiled C# under
`variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/`), rendered
through the real live extensions (PortableInfobox, LIBRARIAN/Cargo) and live's
own templates, with no hardcoded enum strings, invented fallbacks, denormalized
duplication, or approximations. Spells, Skills, and Stances become first-class
generated data + Lua modules + pages, not bare page links or item-embedded blobs.

**Source of truth:** the C# game code. Every formula below is cited to its C#
origin and must be replicated exactly.

---

## Game-authoritative reference

All citations are `File.cs:line` under the Assembly-CSharp directory above.

### Time / tick conversions

- Spell/effect **duration**: `SpellDurationInTicks * 3` seconds. One status tick
  = 3 real seconds (`Stats.TickTime` resets to 180, decremented at 60 Hz →
  180/60). Confirmed `SpellbookSlot.cs:151`, `ItemInfoWindow.cs:670`,
  `StatusEffectIcon.cs:73`.
- Spell **cast time**: `SpellChargeTime / 60` seconds (`SpellChargeTime` is in
  60 Hz charge ticks). Confirmed `SpellbookSlot.cs:159`, `ItemInfoWindow.cs:680`.
- **Cooldown** (both `Spell.Cooldown` and `Skill.Cooldown`): already in
  **seconds**. Internally multiplied by 60 for the countdown
  (`Hotkeys.cs:241`, `SpellbookSlot.cs:160`). Display the value as-is.
- The cast-time tick (60 Hz) and the status tick (3 s) are different concepts;
  do not collapse them to one "ticks per second" constant.

### Item quality scaling (`Item.cs:237-295`)

Quality tier comes from the slot `Quantity` field (1 Normal / 2 Blessed /
3 Godly), not from `Item`. Per-tier scaling:

- `CalcStat` (Str/End/Dex/Agi/Int/Wis/Cha/MR/ER/PR/VR): q1 = x; q2 = x +
  round(x/2) (+50%); q3 = x + x (+100%).
- `CalcRes` (Res): q1 = x; q2 = x+1; q3 = x+2.
- `CalcDmg` (WeaponDmg): q1 = x; q2 = x+1; q3 = x+2.
- `CalcACHPMC` (HP/AC/Mana): q1 = x; q2 = x + round(x/4) (+25%); q3 = x +
  round(x/2) (+50%).

### Economy (`VendorWindow.cs:167`, `GameData.cs:700`)

- Vendor sell = `round(ItemValue * 0.65)`.
- Auction default = `round(ItemValue * 5.0 * PriceMod)`.
- Unsellable when `ItemValue <= 0` or `NoTradeNoDestroy`.

### DPS display (`ItemInfoWindow.cs:818-843`) and proc chance (`Stats.cs:1634`)

These depend on live character stats and are shown in-game only; the wiki shows
base weapon damage/delay, not computed DPS. Record the formulas for reference but
do not invent a character context for static pages.

### Item classification (behavioral, `ItemInfoWindow.cs:183-642`)

There is no item-type enum. Classification priority: Charm (`RequiredSlot==Charm`)
> Aura (`Aura!=null`) > SpellScroll (`TeachSpell!=null`) > SkillBook
(`TeachSkill!=null`) > Mold (`Template`) > Consumable (`RequiredSlot==General` +
`ItemEffectOnClick` + `Disposable`) > Weapon (`RequiredSlot in
Primary/Secondary/PrimaryOrSecondary`) > Armor (other equip slot) > General.
`classify_item_kind` (`domain/entities/item_kind.py`) already mirrors this; keep
it as the single source and verify against the C# tree.

### Spell fields (`Spell.cs`)

Identity/classification: `SpellName`, `SpellDesc`, `Type` (Damage/StatusEffect/
Beneficial/AE/PBAE/Misc/Heal/Pet), `Line` (90-value enum), `UsedBy` (classes),
`RequiredLevel`, `SimUsable`, `WornEffect`, `SpecialDescriptor`, `HardcodedUseCase`,
`ForHardEncounters`. Timing: `SpellChargeTime`, `Cooldown`, `SpellDurationInTicks`,
`UnstableDuration`, `InstantEffect`, `CannotInterrupt`. Resource: `ManaCost`,
`Mana` (dual role: HOT/mana-regen per tick — NOT max-mana; `seMana` is dead code,
only `seManaRegen` is used, `Stats.cs:517`), `PercentManaRestoration`. Damage:
`TargetDamage`, `MyDamageType`, `ResistModifier`, `BleedDamagePercent` (binary: any
nonzero → flat 2% HP/tick), `Aggro`. Healing: `TargetHealing` (per-tick HOT),
`HP` (flat max-HP bonus), `CasterHealing`. `ShieldingAmt`. Stat mods: HP/AC/Str…
Cha/MR/ER/PR/VR, `MovementSpeed`, `DamageShield`, `Haste` (cap +60/-95%),
`percentLifesteal`, `AtkRollModifier` (floor -5), `ResonateChance`, `XPBonus`. CC:
`StunTarget`/`RootTarget`/`CharmTarget`/`FearTarget`/`TauntSpell`/`JoltSpell`/
`CrowdControlSpell`/`BreakOnDamage`/`BreakOnAnyAction`. Proc chains:
`StatusEffectToApply` (+`ApplyToCaster`), `AddProc`, `AddProcChance`. Misc:
`GroupEffect`, `Lifetap`, `InflictOnSelf`, `ReapAndRenew`, `SelfOnly`,
`MaxLevelTarget`, `GrantInvisibility`, `AutomateAttack`, `NoResonate`,
`StatusEffectMessageOnPlayer/NPC`.

### Skill fields (`Skill.cs`)

`SkillName`, `SkillDesc`, `Cooldown` (seconds), six per-class `*RequiredLevel`
ints (0 = unavailable), `TypeOfSkill` (Innate/Attack/Ranged/Utility/Other — no
"Passive"), `StanceToUse`, `EffectToApply`, `AffectPlayer`/`AffectTarget`,
`PlayerUses`/`NPCUses` (combat log), `SkillRange`, `SkillPower`, `PercentDmg`,
`RequireBehind`, `DmgType`, `Require2H`/`RequireDW`/`RequireBow`/`RequireShield`,
`ScaleOffWeapon`, `Interrupt`, `ProcShield`/`ProcWeap`/`GuaranteeProc`, `AESkill`,
`SimPlayersAutolearn`, `AutomateAttack`, `CastOnTarget`.

### Stance fields (`Stance.cs`)

`DisplayName`, `StanceDesc`, `SwitchMessage`, and float modifiers (default 1.0
unless noted): `MaxHPMod`, `DamageMod`, `ProcRateMod`, `DamageTakenMod`,
`SelfDamagePerAttack` (0), `AggroGenMod`, `SpellDamageMod`, `SelfDamagePerCast`
(0), `LifestealAmount`, `ResonanceAmount`, `StopRegen` (bool). Five built-in
stances (`SkillDB.cs`): Normal, Aggressive, Reckless, Taunting, Defensive.

---

## Milestone 8d: Item tooltip subsystem

Live item tooltips are bespoke HTML (not PortableInfobox), built from
`Template:Item/<type>` (Weapon, Armor, Charm, Consumable, General, Mold, Aura,
SkillBook, SpellScroll) and sub-templates `Item/Header`, `Item/Stats`,
`Item/Vitals`, `Item/Resists`, `Item/SpellDetails`, `Item/Categories`,
`Item/CharmScaling`, `Item/ClassRestrictions`, `SparkleIcon`. The `item-tooltip-*`
and `item-spell-details-*` CSS is already in the synced interface mirror.

**Rendering pattern:** each `Template:Item/<type>` is
`{{#invoke:Erenshor/Item|<type>Tooltip}}`; the Lua module resolves the item and
returns the wikitext that calls the sub-templates with resolved values. The
sub-templates own HTML/CSS; Lua owns data and which sub-templates to call. Article
params still override generated data; missing falls back to generated data;
`-` blanks; missing entity emits the visible marker + tracking category.

- [ ] **Step 1: Recreate the sub-templates** verbatim from live (`Item/Header`,
  `Item/Stats`, `Item/Vitals`, `Item/Resists`, `Item/SpellDetails`,
  `Item/Categories`, `Item/CharmScaling`, `Item/ClassRestrictions`,
  `SparkleIcon`) under `wiki/templates/`. Pure presentation wikitext; smoke-render
  each in isolation.
- [ ] **Step 2: Extend generated item data** (`wiki_lua/items.py`) with the
  tooltip fields the data path currently omits: `wand_range`/`bow_range` →
  `range`, `lore` → `description`, `book_title`, the `tier` from stat quality
  (Normal=0/Blessed=1/Godly=2), and resolved crafting `ingredients`/`rewards`
  (ItemLink + quantity) from `get_crafting_recipe`. Extend `ItemDataRepository`
  with the needed repo methods. TDD the Python.
- [ ] **Step 3: Generate a first-class Spells data module** (see M8e) and join
  the item's effect stable keys (`weaponProc`/`wandEffect`/`bowEffect`/
  `clickEffect`/`wornEffect`/`aura`) to render `Item/SpellDetails` — do NOT
  denormalize the 40-field spell block into item data.
- [ ] **Step 4: Per-class teaching levels.** SkillBook tooltips read the skill's
  six per-class `*RequiredLevel`; SpellScroll tooltips read the spell's
  `RequiredLevel` gated by `UsedBy` classes. Source these from the Skills/Spells
  data modules (M8e), not item data.
- [ ] **Step 5: Item module tooltip rendering.** Replace the four-field
  `renderTooltip` stub with one entry point per item type that emits the live
  sub-template calls with resolved data; wire the nine `Template:Item/<type>`.
- [ ] **Step 6: Verify** smoke + parity for one fixture of each item type against
  live, including proc/worn/aura spell details and charm scaling.

## Milestone 8e: First-class Spell / Skill / Stance modeling

Currently spells/skills/stances exist only as `AbilityLinks` (name/page/image/
kind) and bare page links. Model them properly so item tooltips, ability pages,
and links all draw from one faithful source.

- [ ] **Step 1: Inventory live ability templates.** Fetch the live `Template:Ability`
  (and any `Template:Spell`/`Skill`/`Stance`) source and transclusions to learn
  the exact param contract before building. Record findings here.
- [ ] **Step 2: Generated data modules.** Add `Module:Erenshor/Data/Spells`,
  `.../Skills`, `.../Stances` keyed by stable key with the full faithful field set
  from the C# reference above (spell timing via the verified conversions; skill
  per-class levels and flags; stance float modifiers). Add repository
  wiki-generation methods that select every needed column. TDD the Python
  generators (`wiki_lua/spells.py`, `skills.py`, `stances.py`).
- [ ] **Step 3: Lua modules.** Add `Module:Erenshor/Spell`, `Skill`, `Stance`
  with `resolve` + `field`/`status` accessors and an effect-summary builder used
  by both the ability pages and `Item/SpellDetails`.
- [ ] **Step 4: Ability templates/pages.** Render spell/skill/stance pages
  through live's ability template(s), fed by the new modules.
- [ ] **Step 5: Upgrade `AbilityLink`.** Let the link surface optionally pull
  class/level metadata from the new modules (still page-link-first).
- [ ] **Step 6: Verify** smoke + parity for representative spell, skill, and
  stance pages against live.

## Milestone 8f: Faithfulness fixes (audit remediation)

Fix the divergences found auditing the wiki against the C#. Each is a small,
testable change; group into atomic commits by theme.

### Unit / formula correctness
- [ ] Skill cooldown is in **seconds**, not ticks: `sections/skill.py:206-211`
  divides by 60 — remove the division (matches `Spell.Cooldown`, `Hotkeys.cs:241`).
- [ ] Spell duration `*3` is correct; document the two distinct tick concepts so
  the `GAME_TICKS_PER_SECOND` constant is not misapplied to duration
  (`sections/spell.py:195`).
- [ ] `xp_bonus` should emit whenever nonzero, not only when the spell has a
  duration (`sections/spell.py:165`); confirm the `*100` percent conversion
  against the C# `XPBonus` semantics (`sections/item.py:641`).

### Data-driven instead of hardcoded enum strings
- [ ] Character faction: replace the hardcoded `Villager/GoodHuman/...` →
  "Followers of Good/Evil" lists (`sections/character.py:122`, and the missing
  fallback in `wiki_lua/characters.py:190`) with a factions-table lookup; make
  both code paths consistent.
- [ ] Skill type fallback `"Passive"` is not a real `SkillType`
  (`sections/skill.py:122`); use "Other" or blank.
- [ ] Weapon-type 2H detection hardcodes C# enum names
  (`sections/item.py:301`); drive from the exported `weapon_type`.
- [ ] Item-kind display `capitalize()` fallback (`wiki_lua/items.py:225`); use an
  explicit map for every `ItemKind`.
- [ ] Zone type is binary Dungeon/Zone (`wiki_lua/zones.py:54`); model from richer
  game data if available, else document the two-value domain.

### Faction-change and link fidelity
- [ ] Quest faction changes emit raw REFNAME strings (`wiki_lua/quests.py:67`);
  join the factions table to emit `[[FactionPage|Display]] +N`.
- [ ] Restore discarded `add_proc_image_name` / `status_effect_image_name` so
  add-proc and status-effect links carry icons (`repositories/spells.py:116`).

### Completeness / omissions
- [ ] Single guaranteed drop is suppressed by a `>= 2` threshold
  (`sections/character.py:319`, `wiki_lua/characters.py:289`); show guaranteed
  drops regardless of count.
- [ ] Mold `station` (`sections/item.py:220`) and general `stack_size`
  (`sections/item.py:249`) are always blank; export from C# if the data exists,
  else omit the rows rather than render empty.
- [ ] Item `othersource` is always blank (`sections/item.py:374`) though dialog/
  fishing/mining sources are known; surface them.
- [ ] Crafting recipe uses only the first mold (`pages/entities.py:285`); show all
  molds / deduplicate materials.
- [ ] Skill template omits `percent_dmg`, `scale_off_weapon`, `proc_shield`,
  `guarantee_proc`, `interrupt`, `automate_attack`, `player_uses`/`npc_uses`,
  `status_effect`, `itemswitheffect` (`sections/skill.py`); spell template omits
  `effects`, `JoltSpell`, `GrantInvisibility`, `CannotInterrupt`,
  `ForHardEncounters`, `NoResonate` (`sections/spell.py`). Emit the faithful set.
- [ ] Spell `classes` only fetched when teaching items exist
  (`pages/entities.py:332`); always fetch class restrictions.

### Hygiene
- [ ] Replace the hardcoded interactive-map URL literal in `Character.lua` /
  `Zone.lua` with a single shared constant.
- [ ] Remove dead `categoryForType` "Sim" branch (`Character.lua:219`).
- [ ] Move the raw `item_repo._execute_raw` crafting-rewards query out of the page
  generator into the repository (`pages/entities.py:329`).

---

## Notes

- Most M8f fixes live in the **legacy** Python generator (`generators/`), which is
  scheduled for deletion (Milestone 14). Fix the same divergence in the **Lua
  data path** (`wiki_lua/` + `wiki/modules/`) — the production target — and only
  fix the legacy path where it still feeds live output before cutover.
- The Mana-as-max-mana, BleedDamagePercent-as-percent, and stun-cooldown-multiplier
  subtleties (see reference) are game-internal; surface them in wiki copy only if a
  page actually displays them, and never invent values.
