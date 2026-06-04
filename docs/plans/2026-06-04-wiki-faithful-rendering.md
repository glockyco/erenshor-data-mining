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
- **Cooldown units differ by ability kind.** Spell cooldown is already in seconds
  and is multiplied by 60 for the hotkey counter (`Hotkeys.cs:241`,
  `SpellbookSlot.cs:160`). Skill cooldown is stored in 60 Hz hotkey ticks and is
  assigned directly to the counter (`Hotkeys.cs:289`, `Hotkeys.cs:298`), whose UI
  displays `Cooldown / 60` (`Hotkeys.cs:168`). Display spells as-is and skills
  divided by 60.
- The cast-time tick (60 Hz), skill cooldown tick (60 Hz), and status tick (3 s)
  are different concepts; do not collapse them to one "ticks per second"
  constant.

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
SkillBook, SpellScroll) plus sub-templates (`Item/Header`, `Item/Stats`,
`Item/Vitals`, `Item/Resists`, `Item/SpellDetails`, `Item/Categories`,
`Item/CharmScaling`, `Item/ClassRestrictions`, `Item/DPS`, `SparkleIcon`). The
`item-tooltip-*` / `item-spell-details-*` CSS lives in the live
`MediaWiki:Common.css`, pulled into a gitignored local mirror by
`wiki sync-interface`; the render reuses those classes unchanged.

**Faithfulness principle.** The live item tooltips were built to match the
in-game tooltip, so we reproduce their DOM, layout, labels, ordering, and which
rows appear EXACTLY (two-column Item Stats | Vitals/Resists, abbreviated labels
with no colons, all attributes shown defaulting to 0, resists as "+N%", the
section order). We do NOT redesign or "improve" the visualization. Item pages
therefore match live except the documented game-logic corrections below; the
smoke/testcases are the primary gate.

**The live wiki is NOT authoritative for computed logic — only the main-variant
C# is.** Where the wiki's computed values disagree with the game, follow the
game (the only places item output diverges from live):
- 2-Handed classification drives both the "- 2-Handed" label and the Base DPS ×2,
  and applies ONLY to `TwoHandMelee`/`TwoHandStaff` (`ItemInfoWindow.cs:379`,
  `CalcDPSMelee:629`). Bows use `CalcDPSBow` with no ×2 (`:536`). The live wiki
  keys this off a string label and wrongly 2-hands/×2s bows; drive it off the
  `weaponType` enum.
- Weapon proc trigger style (`ItemInfoWindow.cs:446-460`): `weaponProc` shows
  "{chance}% chance on BASH" if `Shield`, "… on CAST" if slot `Bracer`, else
  "… on ATTACK"; `wandEffect`/`bowEffect` are always ATTACK. Derive from the
  item's `shield`/`slot` + proc-chance fields, not the wiki.
- Effect labels (`ItemInfoWindow.cs:404/430`): `clickEffect` → "Activatable:",
  `wornEffect` → "Worn Effect:", disposable → "Item Consumed Upon Use."
- Spell-detail formatting: `duration_sec = durationTicks × 3`, `cast_time =
  castTimeTicks / 60`, "/ tick" on DoT, cast-time hidden for worn/aura.
- Charm scaling labels (Physicality/Hardiness/Finesse/Defense/Arcanism/
  Restoration/Mind "/ 40", Mitigation "%") already match both the live template
  and `ItemInfoWindow` — faithful, not a change.

**Quality is shown by name color only** (live convention): the internal "Godly"
key maps to the tier-2 color (`item-tooltip-tier-2`) and is never printed. The
user-facing "Ascended" rename applies to non-tooltip surfaces (sheets/overview),
tracked separately.

**Future (playtest): item upgrade stages.** The playtest build adds upgrade
stages Normal+1..Normal+5. These layer onto the **Normal** quality tooltip ONLY
(Blessed/Ascended stay single); the plan is a stage selector switching Normal
between +0..+5. Not built yet (main has no upgrade data) — design the render seam
so the Normal quality can carry an ordered list of stages without restructuring
the other two.

**Base DPS:** the deterministic `ceil(damage/delay)` (×2 for true 2-handed) with
the "Base DPS" label. The real `CalcDPSMelee/Bow` is player-stat-dependent and
cannot be a faithful item constant, so the wiki keeps a documented comparison
metric — but the ×2 follows the game's weapon classification.

**Rendering pattern (pure-Lua, separate tooltip template):** the bespoke stat
tooltip is its own template, `{{ItemTooltip|stablekey=…}}` →
`{{#invoke:Erenshor/Item|tooltip}}`, kept SEPARATE from the metadata `{{Item}}`
PortableInfobox. A live item page is `{{Item|…sources/quest/buy…}}` followed by a
wikitable of three `{{Item/Weapon|…75 flat params…}}` calls; we replace that whole
block with one `{{ItemTooltip}}`. `Module:Erenshor/Item` resolves the item by
stable key from `Module:Erenshor/Data/Items`; `Module:Erenshor/Item/Tooltip`
builds the HTML with `mw.html`, reusing the live `item-tooltip-*` CSS classes —
NO presentational sub-templates, NO flat-param hand-off. Weapons/armor render one
tooltip per quality (by name color); other types render one. The spell-detail box
joins `Module:Erenshor/Data/Spells` by the effect stable key via `mw.loadData`
(loaded once per page, cached; the data module is pure static data). Python data
stays faithful raw only; the Scribunto unit tests assert the real final markup.

**Generator migration (deploy path).** The Python page generator emits
`{{ItemTooltip|stablekey=…}}` and migrates existing pages by extending the
existing `mwparserfromhell` machinery in `generate_service` (`_replace_fancy_tables`
/ `_replace_wiki_table` / `_replace_item_type_templates`): replace the old
three-`{{Item/Weapon}}` table (and legacy `{{Fancy-weapon}}` / `{{Item/<type>}}`
tooltip templates) with the single `{{ItemTooltip}}`, idempotently, preserving the
`{{Item}}` infobox, manual content, and categories. This matches researched best
practices (idempotent, `matches()`-based, spacing/manual-edit-preserving, dry-run +
edit summaries) — reuse, do not reinvent.

- [x] **Step 1: Faithful raw item data** (`wiki_lua/items.py`) — DONE. Adds
  `description`, `book_title`, raw `wandRange`/`bowRange`, raw per-quality stat
  rows (quality key "Godly"), resolved crafting `ingredients`/`rewards`. No
  presentation in Python.
- [x] **Step 2: Pure-Lua tooltip render** — DONE for weapon, armor, charm,
  consumable, general, aura, and mold, each faithfully reproducing its live
  template DOM (game-correct 2-handed/DPS). `Module:Erenshor/Item/Tooltip` builds
  the HTML; `Template:ItemTooltip` is the single glue entry point and the nine
  per-type wrappers are removed.
- [x] **Step 3: Spell-detail join** (`Module:Erenshor/Item/Tooltip` →
  `Module:Erenshor/Data/Spells` via `mw.loadData`) reproducing `Item/SpellDetails`
  for `weaponProc`/`wandEffect`/`bowEffect`/`clickEffect`/`wornEffect`/`aura`.
  Proc header/style, labels, and duration/cast-time formatting per the game logic
  recorded above. No 40-field spell block in item data.
- [x] **Step 4: Book/scroll bodies + per-class teaching levels** from Skills/Spells
  data: SkillBook reads the skill's six `*RequiredLevel` (Duelist→Windblade);
  SpellScroll reads the spell `RequiredLevel` gated by `UsedBy`.
- [x] **Step 5: Item/Categories tracking** (weapon/armor/charm/etc. categories).
- [x] **Step 6: Generator migration + verify.** Emit `{{ItemTooltip|stablekey=…}}`
  from the Python item page generator; extend the `_replace_*` machinery to strip
  the old 3×table / legacy templates idempotently while preserving the infobox and
  manual content; tests for migrate-from-old and re-run-idempotent. Smoke +
  testcases for one fixture of each item type. Dead `Module:Erenshor/Render` is
  deleted.

**Note (mw.loadData):** item shards carry lore prose (tooltips need it); shards
are per-type and loaded per page; revisit only if shard size hurts parser memory.

## Milestone 8e: First-class Spell / Skill / Stance modeling

Currently spells/skills/stances exist only as `AbilityLinks` (name/page/image/
kind) and bare page links. Model them properly so item tooltips, ability pages,
and links all draw from one faithful source.

**Current status:** The Stance vertical slice is complete for generated data,
`Module:Erenshor/Stance`, `Template:Stance`, smoke fixtures, and local-vs-live
PortableInfobox parity. Spell generated data, `Module:Erenshor/Spell`,
`Template:Ability` spell rendering, smoke fixtures, and local-vs-live
PortableInfobox parity are complete with raw C#-faithful spell fields and class
restrictions. Skill generated data, `Module:Erenshor/Skill`, `Template:Ability`
skill dispatch, smoke fixtures, and local-vs-live PortableInfobox parity are
complete with raw C#-faithful skill fields, DB-derived class display names, and
per-class levels. Stance `activated_by` now derives from `Skill.StanceToUse`
through the Skills data module.


- [ ] **Step 1: Inventory live ability templates.** Fetch the live `Template:Ability`
  (and any `Template:Spell`/`Skill`/`Stance`) source and transclusions to learn
  the exact param contract before building. Record findings here.
- [ ] **Step 2: Generated data modules.** `Module:Erenshor/Data/Stances` is
  complete, keyed by stable key with the faithful stance modifier fields from
  `Stance.cs`. `Module:Erenshor/Data/Spells` is complete, keyed by stable key
  with raw spell timing/resource/effect/stat/CC fields plus class restrictions;
  Lua owns display conversion for cast time, cooldown, and duration.
  `Module:Erenshor/Data/Skills` is complete, keyed by stable key with raw skill
  fields, per-class levels, DB-derived display class names, and stance/effect
  stable-key relationships. Lua owns display conversion for skill cooldown
  ticks. `wiki_lua/stances.py`, `spells.py`, and `skills.py` are done.
- [ ] **Step 3: Lua modules.** `Module:Erenshor/Stance`, `Module:Erenshor/Spell`,
  and `Module:Erenshor/Skill` are complete with `resolve` + `field`/`status`
  accessors. Stance `activated_by` is generated from Skills data. The remaining
  shared ability work is to extract effect-summary builders only when
  `Item/SpellDetails` needs them.
- [ ] **Step 4: Ability templates/pages.** Stances render through live's separate
  `Template:Stance`; keep that surface. Spells and Skills render through live's
  unified `Template:Ability`, dispatched by stable-key prefix.
- [ ] **Step 5: Upgrade `AbilityLink`.** Let the link surface optionally pull
  class/level metadata from the new modules (still page-link-first).
- [ ] **Step 6: Verify** smoke + parity for representative ability pages against
  live. Stance smoke + parity against live `Aggressive`, spell smoke + parity
  against live `Minor Lightning`, and skill smoke + parity against live
  `Backstab` are complete.

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
- [x] Quest faction changes (`wiki_lua/quests.py`): confirmed real divergence.
  The clean DB stores faction changes in `quest_faction_affects` keyed by world
  faction stable key; `quests` rows do not carry display-ready faction strings.
  Fixed by joining `quest_variants` → `quest_faction_affects` → `factions` in
  `QuestRepository` and emitting linked display names in Lua data.
- [x] Character faction in the Lua path (`wiki_lua/characters.py`): confirmed
  correct. `MyFaction` is the exported AI/friendliness enum (`OtherEvil`,
  `GoodHuman`, etc.), while `MyWorldFaction` is the wiki-facing reputation
  faction. Keep world-faction-only output so internal grouping labels do not leak
  to articles.
- [x] Add-proc / status-effect link icons (`repositories/spells.py`): confirmed
  correct for item tooltips. The spell-detail block owns the icon as a separate
  spell-box cell; proc/status spell names inside that block must not render
  `AbilityLink` inline icons. A Lua testcase now locks this structure. The legacy
  Python repository helper still drops joined image columns, but that path is not
  the cutover target.

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
