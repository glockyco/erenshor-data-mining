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

**Current status:** The Stance vertical slice is complete for generated data,
`Module:Erenshor/Stance`, `Template:Stance`, smoke fixtures, and local-vs-live
PortableInfobox parity. `activated_by` is intentionally still article-override
only in the Stance module because the relationship is not a Stance field in the
game; it must be derived when Skills are modeled from `Skill.StanceToUse`
(`Skill.cs`) to the target stance stable key. Do not denormalize that
relationship into Stance data before the Skills module exists.


- [ ] **Step 1: Inventory live ability templates.** Fetch the live `Template:Ability`
  (and any `Template:Spell`/`Skill`/`Stance`) source and transclusions to learn
  the exact param contract before building. Record findings here.
- [ ] **Step 2: Generated data modules.** `Module:Erenshor/Data/Stances` is
  complete, keyed by stable key with the faithful stance modifier fields from
  `Stance.cs`. Add `Module:Erenshor/Data/Spells` and `.../Skills` keyed by
  stable key with the full faithful field set from the C# reference above (spell
  timing via the verified conversions; skill per-class levels and flags). Add
  repository wiki-generation methods that select every needed column. TDD the
  Python generators (`wiki_lua/spells.py`, `skills.py`; `stances.py` is done).
- [ ] **Step 3: Lua modules.** `Module:Erenshor/Stance` is complete with
  `resolve` + `field`/`status` accessors. Add `Module:Erenshor/Spell` and
  `Skill` with the same accessors and an effect-summary builder used by both the
  ability pages and `Item/SpellDetails`.
- [ ] **Step 4: Ability templates/pages.** Stances render through live's separate
  `Template:Stance`; keep that surface. Render spells and skills through live's
  unified `Template:Ability`, fed by the new modules.
- [ ] **Step 5: Upgrade `AbilityLink`.** Let the link surface optionally pull
  class/level metadata from the new modules (still page-link-first).
- [ ] **Step 6: Verify** smoke + parity for representative spell and skill pages
  against live. Stance smoke + parity against live `Aggressive` is complete; rerun
  it when Skills populate `activated_by`.

## Milestone 8f: Faithfulness verification (audit triage)

The original audit was run by a subagent that did not know maintainer intent and
over-reported. Each candidate below must be **verified against the game data and
confirmed with the maintainer before any change** — several "issues" turned out to
be correct or intentional. Do not presumptively "fix" working behavior. Only the
production Lua path (`wiki_lua/` + `wiki/modules/`) matters; the legacy generator
(`generators/`) is deleted in Milestone 14, so do not spend effort there.

### Confirmed correct or intentional (do NOT change; recorded so future audits stop re-flagging)
- **Cooldown units are correct in both paths.** Verified against `Hotkeys.cs`:
  spells set the counter to `Spell.Cooldown * 60f` (so `Spell.Cooldown` is in
  seconds → `spell.py` prints it directly), skills set the counter to
  `Skill.Cooldown` with no multiply (so `Skill.Cooldown` is in 60 Hz frames →
  `skill.py` divides by 60). The game stores the two in different units on
  purpose. Both wiki conversions are right.
- **Spell duration `* 3` is correct** (status tick = 3 s; distinct from the 60 Hz
  cast-charge tick). Keep; do not "unify" the constants.
- **Single guaranteed drop is intentionally suppressed** (`>= 2` threshold): it
  makes no sense to list one item twice. Keep.
- **`othersource` is a manual-only field** for sources we deliberately do not
  auto-extract; it is correctly blank from generation.
- **Crafting recipe uses one mold by design.** Keep.
- **Spell class restrictions are intentionally shown only when learnable** — an
  unlearnable/legacy spell shows none so readers are not misled. Keep.
- **Zone type is Dungeon/Zone by design** (matches the game's distinction).

### Verify against game data; fix only if a real divergence is confirmed
- [ ] Quest faction changes (`wiki_lua/quests.py`): confirm whether
  `affected_factions` already holds display names or raw internal REFNAMEs. If
  REFNAMEs leak to the page, join the factions table for display name + link;
  if they are already display names, record as correct.
- [ ] Character faction in the Lua path (`wiki_lua/characters.py`): confirm the
  world-faction-only behavior is intended (it may be deliberate that characters
  without an explicit world faction show none). Change only if the maintainer
  wants the Good/Evil grouping surfaced.
- [ ] Add-proc / status-effect link icons (`repositories/spells.py`): confirm
  whether omitting icons on those links is intentional before wiring
  `add_proc_image_name` / `status_effect_image_name` through. Relevant to M8e.

### Optional hygiene (non-behavioral; only if touching the file anyway)
- The interactive-map URL literal is duplicated in `Character.lua` / `Zone.lua`;
  could be a single shared constant.
- Dead `categoryForType` "Sim" branch in `Character.lua`.

---

## Notes

- Most M8f fixes live in the **legacy** Python generator (`generators/`), which is
  scheduled for deletion (Milestone 14). Fix the same divergence in the **Lua
  data path** (`wiki_lua/` + `wiki/modules/`) — the production target — and only
  fix the legacy path where it still feeds live output before cutover.
- The Mana-as-max-mana, BleedDamagePercent-as-percent, and stun-cooldown-multiplier
  subtleties (see reference) are game-internal; surface them in wiki copy only if a
  page actually displays them, and never invent values.
