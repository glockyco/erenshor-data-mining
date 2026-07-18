---
title: Main vs Playtest Script Audit
type: audit
status: implemented
created: 2026-07-04
parent: 2026-07-09-erenshor-planning-overview
archived: 2026-07-18
---

# Main vs Playtest Script Audit

**Date:** 2026-07-04
**Scope:** All decompiled C# scripts in `Assembly-CSharp/` for both variants.
- **Main:** `variants/main/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/` (DLL dated May 17, 1.3MB)
- **Playtest:** `variants/playtest/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/` (DLL dated Jul 2, 1.7MB)

## Methodology

1. `diff -rq` to enumerate all file-level differences.
2. Per-file `diff` to extract changed lines, filtered for decompiler noise:
   - Explicit default initializers (`= 0`, `= 0f`, `= false`, `= true`, `= null`)
   - Discard rewrites (`_ = expr` → `T x = expr`)
   - Variable hoisting (`if (expr)` → `T x = expr; if (x)`)
   - Loop form changes (`for(int i)` → `foreach`)
   - Empty `if` blocks replacing discards
3. Seven parallel subagents audited file batches by domain, documenting every real gameplay/mechanic change with source lines and export-pipeline impact.

## Summary Statistics

| Category | Count |
|---|---|
| New `.cs` files in playtest only | 57 |
| Modified `.cs` files (both variants) | 233 |
| Files with meaningful diffs (>20 changed lines) | 67 |
| Files with decompiler-noise-only diffs (≤4 lines) | 66 |
| Third-party asset files (all noise) | 31 |
| Total diff lines across all files | ~17,000 |

### New files by system

| System | Files |
|---|---|
| Raid system (manager, UI, slots, save, tracking) | 12 |
| Boss encounter scripts | 25 |
| Blessing altar | 3 |
| Cosmetics / sim appearance | 2 |
| Spawn/audio/scene helpers + debug | 11 |
| Auction house save data | 1 |
| Misc (shapeshift, death touch, DPS checks) | 3 |

---

## 1. Third-Party Asset Files — No Gameplay Changes

All 31 third-party files (MTAssets, LunarCatsStudio, Hovl, HS_, StylizedWater, PsychoticLab, Koenigz, SFB) have diffs that are **exclusively decompiler noise**: default initializers, `for`→`foreach` rewrites, variable hoisting. No gameplay or export impact.

---

## 2. New Playtest-Only Files

### 2.1 Raid System (12 files)

**`RaidManager.cs`** — Central raid controller. Manages up to 3 raid groups, raider roster, role assignment (main assist/tank, puller, CC, healer), target assignment, group attack/pull/follow/stay orders, raid-wide DPS throttles, group auras, battle-rez charges via raid XP, loot distribution window, and raid setup save/load JSON. Runtime registry for boss scripts via `LooseAdds`.

**`RaidMemberSlot.cs`** — Raid roster slot UI/runtime: assigned sim, class icon, HP/mana bars, drag/drop swapping, role flags, battle-rez, DPS meter, per-target healing thresholds.

**`RaidRoleButton.cs`** — Toggles raid role flags (MA/MT, CC, puller, healer) for player or raid slot.

**`RaidHealSlider.cs`** — UI slider for healer per-target healing threshold.

**`PlayerRaidCard.cs`** — Player raid card UI: HP bar, DPS meter, battle-rez action.

**`RaidCommandButtonColors.cs`** — Colors raid target-command buttons green when target matches.

**`RaidDisplay.cs`** — Legacy/placeholder raid display (empty methods).

**`RaidSlotData.cs`** — Serializable DTO for saved raid slot (sim name, roles, heal assignments).

**`RaidStructureData.cs`** — Serializable raid profile DTO (all slots, group tasks, DPS settings).

**`RaidStructureSaveFile.cs`** — Wrapper for list of saved raid profiles.

**`TrackEngagedTargets.cs`** — Builds sorted list of hostile tracked targets from group targets, nearby enemies, raid loose adds, and raid group targets.

**`TrackedTarget.cs`** — UI bar for tracked enemy: name/HP, targeting, group attack commands.

**Export impact:** Mostly runtime/UI. `RaidManager.LooseAdds` is a bridge for script-spawned encounter adds absent from static spawn exports. No direct SQLite/wiki/sheets schema change.

### 2.2 Boss Encounter Scripts (25 files)

| File | Boss | Key Mechanics |
|---|---|---|
| `AEManaDrainEvent.cs` | Generic | Periodic mana drain from aggro table |
| `ArborScript.cs` | Arbor | Sapling adds at 60%/30% HP, raid loose-add registration |
| `BraxFightEvent.cs` | Brax | 4 crystals, golems, corruptors at 70%/30%, final construct phase |
| `BraxPlaneTrigger.cs` | Plane of Brax | Hot/cold environmental toggle |
| `Constellation.cs` | Soluna/Zenith-Nadir | Temporary mob spawns random prefab after timer |
| `DPSCheckAEEvent.cs` | Generic | Escalating AE damage/resist mod (soft enrage) |
| `DPSCheckArmorPen.cs` | Generic | Escalating armor penetration (soft enrage) |
| `DPSCheckAttackAbility.cs` | Generic | Escalating attack ability (soft enrage) |
| `DeathTouch.cs` | Generic | Periodic kill of non-tank aggro target, buffs boss |
| `FaithEvent.cs` | Faith | Spawns healing object that paths to Faith, heals 500K |
| `FaithTracker.cs` | Faith | Healing add: arrives at dest, heals/buffs Faith, self-destructs |
| `FernHighPriest.cs` | Fern High Priest | Void-pain reflect mechanic, escalating stats |
| `FernallaFight.cs` | Fernalla | Multi-form shapeshift (bear/spider/wolf/human), adds at HP thresholds |
| `GraceEvent.cs` | Grace | Full heal + duplicate adds below 33% HP (up to 2x) |
| `HonsusScript.cs` | Honsus (Vith Arena) | Drops aggro, runs to nav point, spawns executioner adds |
| `InfernoEnergy.cs` | Inferno/Frost Twins | Moving energy add, explodes near target twin |
| `InfernoTwins.cs` | Inferno/Frost Twins | Alternates sending energy to twin |
| `InfernoTwinsSpawnPoints.cs` | Inferno/Frost Twins | Wires twin cross-references on spawn |
| `MizukiEvent.cs` | Mizuki | Warp fight, shadow remnants, bleed, final AE phase below 1M HP |
| `POBraxBalance.cs` | Plane of Brax | Hot/cold environmental state, visual FX, fog |
| `RewardListener.cs` | Inferno/Frost Twins | Reward/enrage controller, spawns chest on twin death |
| `SolunaFight.cs` | Soluna | Corruptors at 75%/50%, constellation waves, shadow waves below 10%, knockback |
| `SprinklesEvent.cs` | Sprinkles | Ward phases, invulnerability while wards live, lifetap/offensive AE switching |
| `VithArena.cs` | Vith Arena | Coin-gated arena: 8 coin items → 8 fight prefab lists → award chests |
| `VitheoFight.cs` | Vitheo | Escalating legion waves, corruptors, endless spawns below 7% |
| `ZenithNadirScript.cs` | Zenith/Nadir | HP-synchronized pair, constellation stars, Syzygy add, chest on full clear |

**Export impact:** **HIGH.** These scripts encode dynamic prefab spawns, add spawn locations, reward chest spawns, linked spawns, and encounter relationships that will NOT appear as ordinary static spawn-point data. Existing spawn/loot exports miss these entirely.

### 2.3 Blessing Altar (3 files)

**`BlessingAltar.cs`** — Altar UI: sacrifice items to increase `GameData.BlessingTimer` (capped ~60 min). Rejects empty/low-value/no-trade/no-sell items. TMOGHIDE triggers a joke/punishment path.

**`BlessingColorShift.cs`** — UI visual effect cycling image color through HSV.

**`ReplenishTMOGHide.cs`** — Keeps an ItemIcon forced to TMOGHIDE.

**Export impact:** Item fields used (`ItemValue`, `ItemLevel`, `Stackable`, `NoTradeNoDestroy`, `PlayerCannotSell`) are already exported. Blessing formulas are scripted.

### 2.4 Cosmetics (2 files)

**`SimCosmeticManager.cs`** — Global manager for sim cosmetic inspection/equipment UI.

**`SimCosmeticSlot.cs`** — UI slot for selecting sim cosmetic items from held inventory.

**Export impact:** Uses exported item IDs/slot types. No new static records.

### 2.5 Spawn/Audio/Scene Helpers + Debug (11 files)

| File | Purpose | Export Impact |
|---|---|---|
| `SpawnPointLinker.cs` | Synchronizes respawn timers between two linked spawn points | **Relevant** — encodes spawn-point pairing not in flat exports |
| `NPCAliveListener.cs` | Toggles GameObjects based on SpawnPoint NPC alive state | **Relevant** — spawn-visibility dependency not exported |
| `PlanarMusicManager.cs` | Planar-zone BGM, miniboss/boss music triggers | **Relevant** — encodes which spawn points are midboss/boss |
| `ShoutTrigger.cs` | Proximity-triggered NPC shout text | **Relevant** — flavor text not in exports |
| `ShapeshiftMngr.cs` | Swaps character between wolf/void/spider/bear/elemental/human | None (visual) |
| `ParticleRef.cs` | Holds wolf/bear/spider particle systems | None |
| `AHItemSaveData.cs` | Serializable AH item ID/quality/price DTO | None (save data) |
| `DispStatsOnInspector.cs` | Debug inspector for resist/AC | None |
| `NavAgentSpy.cs` | Debug inspector for NavMeshAgent | None |
| `RadioButtonFader.cs` | UI fade for radio buttons | None |
| `SimSpy.cs` | Debug inspector for sim/NPC nav/aggro | None |

---

## 3. Modified Files — Real Gameplay Changes

### 3.1 Combat & Character Core

#### `NPC.cs` (3941 diff lines — largest)

**New runtime fields** (lines 121-124, 349-390): `PastAggroTarget`, `GroupHOTSpell`, `MyEmitVitaeSpell`, `DPSThrottle`, `SpawnWithAtkDelay`, `SpawnWithBehaviorDelay`, `safePointProtect`, `AppliedForce`, `NoSelfHeal`, `forceSpellCD`, `MyRaidSlot`, `indexInRaid`.

**NPC balance/stat scaling** (lines 389-422, 470-509): New `ApplyBalanceAdjustments()` applies HP scaling via `ServerHPMod`, `HPScale`, level-based under-35/under-8 HP scale. Level ≥40 NPCs with `BossXp < 2` forced to `BossXp = 2`. Level >35 NPCs get all base attributes set to `Level * 20`.

**`NeverAggro` now suppresses behavior/nav loops** (lines 564-585, 5144-5162, 5340-5404): NPCs flagged `NeverAggro` skip nav/behavior coroutines and threat propagation entirely.

**Stormcaller imbue** (lines 661-676, 3994-4016): Skill id `58018670` cached in `myImbued`. `DoImbued()` fires via bow or casting.

**Forced movement** (lines 925-989, 1323-1395): `ApplyForce(Vector3)` and `HandleAppliedForce()` for knockback/physics. NavMesh recovery sample radius increased from 2f to 4f.

**Raid DPS throttle** (lines 1012-1234): `DPSThrottle = MyRaidSlot.DPSThrottle`. If >0.5f, charmed NPC target cleared and `NeverAggro = true`.

**Healer behavior** (lines 1655-2143): Heal selection now uses spell `HP` rather than `TargetHealing`. Group HoT logic added. `NoSelfHeal` prevents NPC self-heal. Player heals require proximity to `NearbyFriends`.

**Aggro changes** (lines 2325-2463, 3244-3328, 4305-4365): `NeverAggro` is a hard threat blocker. `Obscurity of the Deep` reduces threat to 25%. `Intimidation` adds 25000 threat. Ascension threat modifier ID changed from `16681322` to `7757160`.

**Combat rotation** (lines 2522-2913, 4019-4199): Attacks blocked while casting unless sim knows `Multifocus`. `Opportunist` gives 2% chance behind target to perform `Backstab`. Raid sims avoid AE/fear/skills.

**Resist debuff casting** (lines 2645-2730): New `CheckResistDebuffs()` finds and casts highest-level `Global_Magic_Debuff`.

**Innate avoidance formula** (lines 3372-3487): Behind/avoidance math changed from 15-point to 10-point increments. Shield block now includes Reaver as well as Paladin.

**Positioning** (lines 3537-3884): Non-tanks position behind targets using capsule bounds. In-melee threshold changed from `0.2f < distance <= 2f` to `distance <= 2.5f`.

**Stance selection** (lines 5294-5328): Raid MA/MT uses tank stance. Tanks prefer `HatefulStance` over `TauntingStance`. Non-tanks prefer `ExpertStance` over `AggressiveStance`.

**Full raid AI subsystem** (lines 5908-7496): `DoRaidBehavior()`, `CheckHealsRaid()`, `CheckAggroRaid()`, `CheckTauntRaid()`, `CrowdControlRaid()`, loose-add tracking, raid healer thresholds, group-based taunts, burn targets.

#### `Character.cs` (489 diff lines)

**Raid revive** (lines 331-477, 487-631): `RaidRevive()`, `IsRaidRelaxed()`, `IsRaidMemberAlive()`, `IsRaidMemberNearby()`. Raid wipe opens `RespawnWindow`.

**Death saves** (lines 782-842): `CheckUniversalWill()` added — status spell id `12943392` gives 10% chance to avoid death, restores to 25% HP.

**Raid kill credit** (lines 839-1117, 1133-1161): Raid-slot sim attackers count as player-party damage source. `NeverTrack` suppresses XP/kill tracking. `QuestCompleteOnDeath` triggers if `DmgFromPlayerSource > 0`.

**Magic damage mitigation** (line 1506-1578): Formula changed from `_dmg - _dmg * resist * DamageTakenMod` to `(_dmg - _dmg * resist) * DamageTakenMod`.

**DPS dummy** (line 1938): `GetCurHealthAsIntPercentage()` returns 0 when `DPSDummy` is true.

#### `Stats.cs` (728 diff lines)

**New stats**: `BaseAttackRollModifier`, `CannotBeSnared`, `BaseArmorPenPercentage`, `ArmorPenPercentage`.

**Armor penetration**: Participates in `MitigatePhysical()`. Attacker armor penetration reduces target mitigation.

**Shapeshift via status effects**: Wolf/Void/Elemental forms applied in status-effect add paths, cleared in `RemoveAllStatusEffects()`.

**Stun mechanics**: `Unstunnable`, `BreakOnDamage`, `StunCooldown` (non-sim NPCs only), `Feared`.

**Soft mez generalization**: `AmISoftMezzed()` now checks any break-on-damage stun, not hardcoded names.

**Movement speed**: Weapon haste lower cap changed from `-95` to `-200`. `CannotBeSnared` blocks negative movement-speed effects.

**DoT crit**: Ascension rank `19108265` enables DoT crits.

#### `PlayerControl.cs` (521 diff lines)

**Forced movement** (lines 91-92, 244-252): `AppliedForce`, `ApplyForce(Vector3)`, decay in `Update()`.

**Blessing altar interaction** (lines 371-382): Clicking `BlessingOrb` within 9f opens altar UI.

**Raid main-assist targeting** (lines 402-405): Player target drives `RaidManager.Group1Target` when raid-active and player is group-1 MA.

**Gear score** (lines 2515-2540): `CalcGearScore()` with quality multipliers (q2=1.2x, q3=1.3x, q>10=1.1x).

#### `PlayerCombat.cs` (91 diff lines)

**Auto-attack while stunned/casting**: Stuns suppress auto-attack. `Multifocus` allows auto-attacks during casting.

**Opportunist proc** (lines 345-350): 2% chance behind target to replace normal hit with `Backstab`.

**Ranged/wand lifesteal removed** (line 647): `HealMe(damage * PercentLifesteal/100)` removed from ranged-hit path.

#### `UseSkill.cs` (333 diff lines)

**Skill scaling cap removed** (lines 58-66): Level scaling `Level / 28f` no longer caps at 1f.

**Weapon-scaling skills** (lines 150-290): Base uses `MHDmg / 1.33f` (was `/ 2`). Crits explicitly applied (1.5x). `SkillPower` multiplies damage. Two-hand primary = 2x. `CombatStance.DamageMod` multiplies skill damage.

**Skill id `14354340`** (lines 192-248): Special HP-based strike — min damage `CurrentMaxHP * 0.07f * 3f`, crits at 1.3x, 1.5x multiplier, 1.7x for 2H, self-damages 15% max HP.

**Scaling curve** (lines 862-1014): `GetScalingBonus()` changed from linear (level 6-30, 0.5→1) to squared (level 6-35, 0.45→1).

#### `CastSpell.cs` (103 diff lines)

**Beneficial target selection** (lines 168-305): Healers can infer friendly tank from enemy's aggro target.

**Movement interrupts casting** (lines 454-477): Player movement input cancels interruptible casts.

**Overchant contribution** (lines 454-477): Changed from `0.2f` to `0.315f`.

#### `SpellVessel.cs` (717 diff lines)

**Damage formula** (lines 509-744): Stance spell damage bonus now additive (`TargetDamage * scaleDmg + TargetDamage * (stance.SpellDamageMod - 1f)`). Raid-slot sims count as player source.

**Healing formula** (lines 1365-1867): Wisdom scaling uses `WisScaleMod / 45f`. Heal cap changed from `spell.HP * 5` to `spell.HP * 3`. Ascension `29551128` marks crits (1.33x). Group heals now heal player, grouped sims, charmed NPCs, and apply status effects. Raid group heals apply to raid groups 1/2/3.

**Cooldowns** (lines 1988-2133): NPC spell cooldowns add `360f * DPSThrottle`. Player spell cooldowns scaled by `CDMult * scaleDmg`.

**New misc spell action**: `Access Bank` opens bank UI. `Repel Darkness` only changes fog in `Blight` scene.

### 3.2 SimPlayer System

#### `SimPlayer.cs` (2286 diff lines)

**Raid membership**: `InRaid`, `LoadNewInstanceIntoRaid()`, A-team auto-add, raid revive/follow/guard/pulling, raid target sharing, raid pull attack orders, raid chat.

**Azure free-roam**: Grouped SimPlayers in Azure get `freeRoamAzure = true`, wander/do city tasks, excluded from follow/AFK reset.

**Dynamic spread radius**: `randomizeMagnitude` uses raid spread or group spread.

**NavMesh gating**: Returns early if off NavMesh; guards `SetDestination` calls.

**Spell learning overhaul**: Persistent `MyAcquiredSpells`. Only auto-loads spells when `!spell.SimsNeedHelpToLearn || MyAcquiredSpells.Contains(spell)`. Gear/item click effects can bypass level requirements.

**Skill autolearn restrictions**: Requires `skill.SimPlayersAutolearn` for attack/ranged autolearn. Innate skills added for all classes. Reaver stance utility skills added.

**Cosmetic slots**: 8 per-slot cosmetic ItemSaveData fields (head/chest/back/arm/foot/wrist/leg/hand).

**Gear score**: `CalcGearScore()` summing equipped item levels with quality multipliers.

**Equipment AC**: Now uses `CalcAC` instead of `CalcACHPMC`.

#### `SimPlayerMngr.cs` (799 diff lines)

**Raid bring-to-zone**: `BringRaidToZone()` spawns raid SimPlayers around player.

**A-team assignment**: `SetATeamForChar()` marks SimPlayers from character slot A-team list.

**Gear score propagation**: Copied from save data for premade/saved/newly generated Sims.

#### `SimPlayerGrouping.cs` (213 diff lines)

**Raid hotkey**: `Shift+1` during raid calls `RaidManager.OrderAttack()`.

**Spread magnitude**: `SpreadMagnitude` field for group positioning.

**Azure free-roam gating**: Group attack/pull/invis commands refuse if members are free-roaming.

#### `SimPlayerTracking.cs` (210 diff lines)

**New tracking fields**: `ATeam` and `GearScore`.

#### `SimInspect.cs` (220 diff lines)

**Cosmetic inspection**: UI for viewing/managing SimPlayer cosmetic slots.

**Spell/skill list view**: `DoSpellsAndSkills()` lists known spells/skills.

**Ascension rank view**: `DoAscensionsView()`.

#### `SimTradeWindow.cs` (55 diff lines)

**Spell-teaching trades**: Support for `TeachSpell` items where `SimsNeedHelpToLearn` is true.

#### `SimPlayerSaveData.cs` (60 diff lines)

**New persisted fields**: `AcquiredSpells`, `ATeam`, 8 cosmetic slot ItemSaveData fields, `GearScore`.

### 3.3 Items, Spells, Skills

#### `Item.cs` (132 diff lines)

**New fields**:
- `MustBeEquippedToClick` (bool) — items can require equipping before click effects
- `PlayerCannotSell` (bool) — items can be blocked from vendor sale

**Stat formula rewrites**:
- `CalcStat`: quality 2 = `_stat + round(_stat / 3) + 3`, quality 3 = `max(_stat * 2, q2 + 5, _stat + 6)`, qualities 11-15 = `_stat + (qual - 10)`
- `CalcResists`: New method for MR/ER/PR/VR (decoupled from `CalcStat`)
- `CalcACHPMC`: HP/mana quality 2 = `_stat + round(_stat / 5) + 30`, quality 3 = `max(_stat + round(_stat / 2) + 50, q2 + 1, _stat + 26)`
- `CalcAC`: New method for AC (decoupled from HP/mana)

#### `ItemIcon.cs` (694 diff lines)

**New slot flags**: `CosmeticOnly`, `NoStackables`, `DisplayOnly`, `DistSlot`.

**High-tier quality UI**: Quantities >10 show green sparkler highlighting and `+N` suffix.

**Quick-transfer**: `QuickBank`, `QuickSell`, `QuickBuy`, `QuickLoot`, `QuickDebank`, `QuickSmith`, `QuickTrade` methods.

**Blessed item transfer restrictions removed**: `CanTakeBlessedItem` checks deleted.

**MustBeEquippedToClick enforcement**: Right-click use blocked unless equipped.

**Cosmetic slot class bypass**: Class restrictions bypassed for `CosmeticOnly` slots.

#### `Inventory.cs` (140 diff lines)

**Transmog slots**: Added transmog item/slot lists. `Awake()` initializes transmog slots into `ALLSLOTS`.

**Stackable insertion**: `AddItemToInv(Item, int)` now merges stackable items into existing stacks.

**Equipment stat aggregation**: Uses `CalcAC` for AC and `CalcResists` for MR/ER/PR/VR.

#### `Spell.cs` (59 diff lines)

**New fields**:
- `LevelScaledManaRestoration` (float) — mana restoration scaled by caster level
- `SimsNeedHelpToLearn` (bool) — spells can require scroll acquisition before sim use
- `ShapeshiftForm` (string) — Wolf/Void/Elemental forms
- `ArmorPenPercent` (int) — armor penetration percentage
- `SpellLine.Duelist_Armor_Pen = 90` — new spell line enum

#### `SpellDB.cs`

**New refs**: `BleedRef`, `Intimidation` — singleton spell references for AI/event use.

#### `SkillDB.cs`

**New refs**: `ExpertStance`, `HatefulStance` — singleton stance references for AI stance selection.

#### `SpellEffectDB.cs`

**New ref**: `ReviveFX` (GameObject) — visual effect for raid revive.

#### `Smithing.cs` (103 diff lines)

**Template `2265228` combine path**: Combines two matching equipment items into higher-tier quantity (11-15). Rules:
- Components cannot be General, Aura, or Charm
- Quantities 2-10 rejected as "magic too strong"
- Result: 11 from two q1 items, otherwise previous + 1

**Planar-stone recipe**: Rejects `FuelSource.Quantity > 1`.

#### `Stance.cs`

No real changes (only default initializers).

### 3.4 GameData, GameManager, Loot

#### `GameData.cs` (112 diff lines)

**Raid state**: `RaidLootDist GroupLootDist`, `RaidManager RaidManager`, `RaidAny`, `RaidActive`.

**Raid XP routing**: `AddExperience()` short-circuits when `RaidActive`, calls `GiveRaidXP()`.

**New tuning constants**: `Under35HPScale = 1.75f`, `Under8HPScale = 1.33f`, `LootBlessBonus`, `BlessingTimer`, `UseZoneAsTempBind`.

**Vendor sell eligibility**: `PlayerCannotSell` now enforced in vendor prompt.

#### `GameManager.cs` (303 diff lines)

**Blessing timer** (lines 195-207): `LootBlessBonus = 1` when `BlessingTimer > 0`, else 0.

**Zone display name mapping** (lines 1135-1275): `GetZoneDisplayNameFromZoneFileName()` — scene file names → display names (e.g., `Soluna` → `Soluna's Landing`, `PlaneOfVitheo` → `Vitheo's Plane`).

**Cosmetic save persistence**: `CharacterCosmetics` and `CosmeticSlotQuantities` saved/loaded.

**UI window management**: `OpenCloseAscensionWindow()`, `OpenInvWindow()`, `OpenCloseCosmeticWindow()`.

#### `LootTable.cs` (119 diff lines)

**Host character guard**: Returns early if no character, `DestroyOnDeath`, or `DoNotLeaveCorpse`.

**Guaranteed drops scale**: `NumberOfGuaranteedDrops` increments when `ServerLootRate + LootBlessBonus > 1.99/2.99/3.99/4.99`. Up to 10 retries to avoid duplicates.

**Level 42 gold override**: `MyGold = Random.Range(2500, 42500)` for level-42 characters.

**Blessing modifies rarity rolls**: Divisor changed to `ServerLootRate + LootBlessBonus`.

**Special drops**: Sivak chance 2.5x (0.001→0.0025). New `EssenceOfAmarion` drop at `0.0045454544f * multiplier`.

#### `LootWindow.cs` (100 diff lines)

**High-tier quality rolls**: `Random.Range(0, 200)` when `num2 > 94`, producing quantities 11-15.

**Charm exclusion**: Charms excluded from quality-upgrade rolls.

**Blessing indicator**: `BlessingBox` visible when `BlessingTimer > 0`.

**Quality-colored loot messages**: Green `+N` for quantities >10.

### 3.5 Guild, Auction, Trade

#### `GuildManager.cs` (270 diff lines)

**Raid lifecycle** (lines 2076-2131): `CallToRaid()`/`EndRaid()` — blocks raid while group slots occupied, requires Reliquary unless `RaidAny`, enables raid UI, adds A-team members.

#### `AuctionHouse.cs` (197 diff lines)

**Quality-aware listings**: `AHItemSaveData` with `itemQual`. Quality 2 = 2x price, 3 = 3x, >10 = 1.5x.

**NPC auction refresh**: 4% chance to generate augmented-quality listings (11-15).

**Filtering tightened**: Rejects `NoTradeNoDestroy`, zero-value, `PlayerCannotSell`, furniture items.

#### `TradeWindow.cs` (205 diff lines)

**Quality-aware trade matching**: `TradeEntry` objects distinguish stack count from equipment quality. Blessed/augmented equipment no longer satisfies multiple quest requirements.

**Braxonian Flame Well**: Accepts `Quantity == 1 || Quantity > 10`.

### 3.6 Zones, Quests, Events

#### `ZoneAnnounce.cs` (44 diff lines)

**`RaidCapable` flag** (line 38): Zones can declare whether raids are allowed. Non-raid zones end active raids.

**`UseZoneAsTempBind`** (line 36): Zones can set a temporary bind that redirects death respawn to Reliquary.

#### `Zoneline.cs` (43 diff lines)

**Raid members skip normal zonelines**: SimPlayers with `InRaid` don't trigger zoneline zoning.

**Raid status effects persisted**: `AssignedSimTracking.CurrentSEs` populated before zoning.

#### `Respawn.cs` (17 diff lines)

**Temp bind override**: If `UseZoneAsTempBind` matches active scene, respawn redirects to Reliquary at `(275, 1.82, 309)`.

**Status clearing**: Uses `RemoveAllStatusEffects()` instead of manual loop.

#### `AEEvent.cs` (64 diff lines)

**New fields**: `CastSpell`, `addEffect`, `isLifetap`, `lifetapHealMod`, `TriggerOnly`.

**AE target source**: Iterates `MyNPC.AggroTable` instead of `NearbyEnemies`. Physical AE damage supported via `DamageMe`.

**Manual triggering**: `TriggerAE()` method for encounter scripts.

#### `FernallaPortalBoss.cs`

**HP thresholds changed**: Ward1: 12000→25000. Ward2/3: 7000→5000.

#### `AllBooks.cs`

**"Benjamin's Journal" expanded**: 10→13 strings. Lore now points to The Planes, Fernalla/Vitheo, two halves of a contraption.

#### `ChatLogLine.cs` + `AdjustWindowFilters.cs`

**Raid log type**: `LogType.Raid = 0x800000` added. Chat filter UI gains Raid toggle.

#### `TypeText.cs` (188 diff lines)

**New dev commands**: `/raidlvl`, `/ateamme`, `/rdlvlup`, `/p-stone`, `/imawolf`, `/imavoid`, `/imaelem`, `/imadude`, `/bless+3`, `/bless+2`, `/item900`, `/item1k0`, `/item1k1`.

#### `WandBolt.cs` (25 diff lines)

**Homing target adjusted for scale**: `Vector3.up * TargetChar.transform.localScale.y / 1.66f`.

**Physical wand damage**: Now includes `SourceChar.MyStats.AtkRollModifier`.

### 3.7 Other Notable Changes

#### `Hotkeys.cs` (45 diff lines)

**Stun blocks hotkeys**: Checks `GameData.PlayerStats.Stunned`.

**MustBeEquippedToClick enforcement**: Item hotkeys refuse use if item requires equipping.

#### `CameraController.cs` (40 diff lines)

**Zoom**: Scroll speed 2f→6f. Max zoom-out distance -11f→-20f. Vertical offset max now dynamic.

#### `RunWindow.cs` (33 diff lines)

**Reliquary raid escape**: Dead players can be extracted to Reliquary by surviving raid member after 6-second delay.

#### `SaveGameData.cs` (16 diff lines)

**New save fields**: `CharacterCosmetics`, `CosmeticSlotQuantities`, `ATeam`.

#### `TestDummy.cs` (40 diff lines)

**Level cap**: Training dummy level capped at 42.

---

## 4. Export Pipeline Impact Summary

### Already Exported (verified in prior sessions)

These fields were added to the export pipeline in recent commits:
- `Item.MustBeEquippedToClick`, `Item.PlayerCannotSell`, `Item.RareItem`
- `Spell.ArmorPenPercent`, `Spell.LevelScaledManaRestoration`, `Spell.ShapeshiftForm`
- `Skill.SkillCanCrit`
- `Character.CanNeverSeeInvis`, `Character.DPSDummy`, `Character.IsWyrm`, `Character.NoRun`
- `GameData.LootBlessBonus` (game constant)
- `NumberOfGuaranteedDrops` (loot table field, already captured by calculator)

### New Fields/Systems Not Yet Exported

| Field/System | Source | Impact |
|---|---|---|
| `Spell.SimsNeedHelpToLearn` | `Spell.cs:286` | Wiki/sheets should show which spells require scroll acquisition |
| `Spell.SpellLine.Duelist_Armor_Pen = 90` | `Spell.cs:110` | Spell line enum mapping needs update |
| `Skill.SimPlayersAutolearn` | Referenced in `SimPlayer.cs` | Skill wiki should note sim autolearn eligibility |
| `ZoneAnnounce.RaidCapable` | `ZoneAnnounce.cs:38` | Zone exports should show raid capability |
| `ZoneAnnounce.UseZoneAsTempBind` | `ZoneAnnounce.cs:36` | Zone exports should show temp-bind behavior |
| `NPC.SpawnWithAtkDelay`, `SpawnWithBehaviorDelay` | `NPC.cs:349-390` | Character export if behavior fields are serialized |
| `NPC.NoSelfHeal` | `NPC.cs:349-390` | Character export if serialized |
| `NPC.GroupHOTSpell`, `NPC.MyEmitVitaeSpell` | `NPC.cs:349-390` | Character export if serialized |
| `Stats.BaseArmorPenPercentage`, `BaseAttackRollModifier`, `CannotBeSnared` | `Stats.cs` | Stats/status export if serialized |

### Formula Changes (Wiki/Sheets Documentation)

| Formula | File | Change |
|---|---|---|
| Item stat scaling (Str/End/Dex/etc.) | `Item.cs:257-291` | Quality 2: `+round(stat/3)+3` (was `+round(stat/2)`). Quality 3: `max(stat*2, q2+5, stat+6)` (was `stat*2`). New qualities 11-15. |
| Item resist scaling (MR/ER/PR/VR) | `Item.cs:296-310` | New `CalcResists` method, decoupled from `CalcStat` |
| Item AC scaling | `Item.cs:351-378` | New `CalcAC` method, decoupled from `CalcACHPMC` |
| Item HP/Mana scaling | `Item.cs:334-349` | Quality 2: `+round(stat/5)+30` (was `+round(stat/4)`). Quality 3: `max(+round(stat/2)+50, q2+1, stat+26)` (was `+round(stat/2)`) |
| Magic damage mitigation | `Character.cs:1506` | `(_dmg - _dmg * resist) * DamageTakenMod` (was `_dmg - _dmg * resist * DamageTakenMod`) |
| Spell damage bonus | `SpellVessel.cs:509-744` | Additive: `TargetDamage * scaleDmg + TargetDamage * (stance.SpellDamageMod - 1f)` |
| Healing cap | `SpellVessel.cs:1365-1867` | `spell.HP * 3` (was `spell.HP * 5`) |
| Overchant contribution | `SpellVessel.cs:454-477` | `0.315f` (was `0.2f`) |
| Skill level scaling | `UseSkill.cs:58-66` | No cap (was capped at 1f) |
| Skill weapon scaling | `UseSkill.cs:150-290` | Base `MHDmg / 1.33f` (was `/ 2`). Two-hand = 2x. |
| Skill scaling curve | `UseSkill.cs:862-1014` | Squared curve level 6-35 (was linear 6-30) |
| Innate avoidance | `NPC.cs:3372-3487` | 10-point increments (was 15-point). Reaver shield block. |
| Loot drop probabilities | `LootTableProbabilityCalculator.cs:78` | Legendary base prob `1.97` (was `2.3` — cumulative threshold) |

### Dynamic Spawn Gaps

The following encounter-driven spawns are NOT captured by static spawn-point exports:
- **Boss add spawns**: Arbor saplings, Brax crystals/golems/corruptors, Fernalla fawns/spiderlings/wolves, Soluna corruptors/constellations/shadows, Sprinkles wards, Vitheo legion waves, Zenith/Nadir constellation stars + Syzygy
- **Reward chests**: Inferno/Frost twins, Zenith/Nadir, Vith Arena award chests
- **Paired/linked spawns**: Inferno/Frost twins cross-wiring, SpawnPointLinker respawn sync
- **Vith Arena**: Coin-gated fight prefab lists → award chest mapping

### Zone Display Name Mapping

`GameManager.GetZoneDisplayNameFromZoneFileName()` provides a scene-file-name → display-name mapping (e.g., `Soluna` → `Soluna's Landing`, `PlaneOfVitheo` → `Vitheo's Plane`). Zone/wiki/map exports should be checked for whether they use scene IDs or display names.
