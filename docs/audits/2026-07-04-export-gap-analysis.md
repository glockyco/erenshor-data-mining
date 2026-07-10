# Export Gap Analysis: Main vs Playtest Audit

**Date:** 2026-07-04
**Scope:** Exhaustive list of fields and formula changes relevant to our data exports (wiki, sheets, map, AdventureGuide) that are missing or need updating based on the main-vs-playtest script audit.
> **Resolved by:** [`2026-07-04-playtest-reconciliation-quality-tiers-formulas-export-gaps`](../plans/archive/2026-07-04-playtest-reconciliation-quality-tiers-formulas-export-gaps.md).


---

## 1. Missing Serialized Fields — Should Be Exported

### 1.1 Spells (1 field)

| Field | Type | Source | Current Status | Why Export |
|---|---|---|---|---|
| `SimsNeedHelpToLearn` | bool | `Spell.cs:286` | **IGNORED** ("spell AI/runtime hint fields are not exported") | **Ignore reason is invalid.** This is player-facing spell acquisition data. SimPlayers only auto-learn spells when `!SimsNeedHelpToLearn || MyAcquiredSpells.Contains(spell)`. Item tooltips warn players. SimTradeWindow teaches these spells via scroll items. 18 playtest spell assets have `SimsNeedHelpToLearn = true`. Wiki/sheets/guide should show which spells require scroll acquisition. |

**Note:** `HardcodedUseCase` and `ForHardEncounters` are also ignored as "AI/runtime hints" — these are reasonable to leave ignored. `HardcodedUseCase` marks 2 specific spells (Invisibility, Meditate) as having special code paths. `ForHardEncounters` is an AI hint for encounter spell selection. Neither is player-facing data.

### 1.2 Characters/NPCs (17 fields)

These are public serialized fields on `NPC.cs` (a MonoBehaviour) — they ARE on prefabs and configurable by designers. The field-coverage manifest does not track `NPC` as a separate type, so these fields are invisible to the coverage gate.

#### High Priority (gameplay mechanics, many non-default prefabs)

| Field | Type | Non-default prefabs | Why Export |
|---|---|---|---|
| `NeverAggro` | bool | 14 (Constellation, FlameEnergy, Ward of the Forest, etc.) | NPCs flagged `NeverAggro` skip ALL nav/behavior/threat loops. Hard threat blocker. Critical for map/guide — these NPCs don't initiate combat. |
| `NoDmgCap` | bool | 103 | Bypasses NPC damage cap in `TakeDamage`. Very common on bosses. Sheets/guide should show this. |
| `CanPhantomStrike` | bool | 41 (Torturer, Lost King's Guard, Dreambear, etc.) | Special combat mechanic — phantom strike teleports behind target. Guide/wiki should document. |
| `Enrage` | float | 17 (Darkwarden Awxa/Ealdred, Spike, Crazed Prisoner, etc.) | Encounter timer/mechanic. When >0, NPC enrages over time. Sheets/guide should show. |
| `AggroRegardlessofLOS` | bool | 12 (Shivering step mobs) | NPC aggro ignores line-of-sight checks. Map/guide relevant. |
| `IgnoreLOSForAggro` | bool | 8 (Azynthian Corruptor/Keeper) | `CheckLOS()` returns true when set. Distinct from above — this one skips the LOS check itself. Map/guide relevant. |
| `SpawnWithStatus` | Spell ref | Non-null on Fernallan High Priest, Subterranean Magmite | NPC spawns with a status effect pre-applied. Should be captured as a spell relation. |
| `NoSelfHeal` | bool | Non-default on Sapling | Disables self-heal at low HP. Guide/wiki mechanic. |

#### Medium Priority (spell relations, AI behavior)

| Field | Type | Non-default prefabs | Why Export |
|---|---|---|---|
| `GroupHOTSpell` | Spell ref | None found in prefabs (behavior when set) | Raid group heal-over-time spell. Add as role-specific spell relation. |
| `MyEmitVitaeSpell` | Spell ref | None found in prefabs | Reaver-style emit vitae spell. Add as role-specific spell relation. |
| `MyHOTSpell` | Spell ref | (existing, not captured) | Single-target HOT spell. Already not captured — add as spell relation. |
| `AETaunt` | Spell ref | (existing, not captured) | AE taunt spell. Already not captured — add as spell relation. |
| `SimPlayersIgnoreUntilOrdered` | bool | Brax Elemental Crystal | Raid sim AI: NPC waits for orders. Low public value but useful for encounter auditing. |
| `SpawnWithAtkDelay` | bool | Brax Elemental Crystal, Vithean Archer, Executioner | Delays first attack after spawn. Encounter timing. |
| `SpawnWithBehaviorDelay` | float | Vithean Azynthian Corruptor | Delays AI behavior loop after spawn. Encounter timing. |

#### Low Priority (probably leave ignored)

| Field | Type | Verdict |
|---|---|---|
| `HoldDPS` | float | SimPlayer DPS threshold. No non-default values in prefabs. Leave ignored. |
| `ChestDurability` | int | Runtime randomized 3-6 on Start(). Not authored data. Leave ignored. |

### 1.3 Stats (3 fields)

These are public serialized fields on `Stats.cs` (a MonoBehaviour) — they ARE on prefabs. The manifest does not track `Stats` as a type.

| Field | Type | Non-default prefabs | Why Export |
|---|---|---|---|
| `BaseArmorPenPercentage` | int | 8 (Opus=60, Jinx/Jinx2=20, Summoned Treant=10) | Base armor penetration stat. `CalcStats()` sets `ArmorPenPercentage` from it. Affects physical damage mitigation. Sheets/guide should show. |
| `BaseAttackRollModifier` | int | 4 (God Brax=3, Vitheo=2, Jinx/Jinx2=4) | Base attack roll modifier. `CalcStats()` adds it to `AtkRollModifier`. Affects hit chance. Sheets/guide should show. |
| `CannotBeSnared` | bool | 33 | Immunity to snare/root effects. Status effect processing blocks negative movement speed when set. Guide/wiki mechanic. |

### 1.4 Zones (2 fields)

| Field | Type | Non-default prefabs | Current Status | Why Export |
|---|---|---|---|---|
| `RaidCapable` | bool | PlaneOfVitheo, PlaneOfSoluna, Reliquary, PlaneOfBrax, PlaneOfFernalla | **IGNORED** ("zone runtime/UI/camera metadata") | **Ignore reason is invalid.** This is zone access/group-size gameplay metadata. Non-raid zones end active raids. Wiki zone pages, zones sheet, and guide routing should show this. |
| `UseZoneAsTempBind` | string | PlaneOfVitheo, PlaneOfSoluna, PlaneOfBrax, PlaneOfFernalla | **IGNORED** ("zone runtime/UI/camera metadata") | **Ignore reason is invalid.** This is death/respawn behavior. Dying in these zones redirects respawn to Reliquary. Guide/wiki should document. |

### 1.5 Items (0 missing fields)

All non-visual serialized Item fields are already captured by `ItemListener`. The only ignored fields are equipment trim/color visual fields (13 fields) — correctly ignored.

**Note:** `TeachSpell` is already exported end-to-end as `teach_spell_stable_key`.

### 1.6 Skills & Stances (0 missing fields)

All Skill and Stance public serialized fields are already captured. `SimPlayersAutolearn` and `SkillCanCrit` are both exported and surfaced in wiki/sheets.

---

## 2. Missing Fields — Manifest Coverage Gap

The field-coverage manifest tracks these Unity types: `Character`, `Item`, `Spell`, `Skill`, `Stance`, `LootTable`, `SpawnPoint`, `ZoneAnnounce`, etc. But it does **NOT** track:

- **`NPC`** — 17 gameplay-relevant public fields are invisible to the coverage gate (listed in §1.2)
- **`Stats`** — 3 gameplay-relevant public fields are invisible to the coverage gate (listed in §1.3)

**Recommendation:** Add `NPC` and `Stats` as tracked types in the manifest, with all public fields classified as `captured` or `ignored` with valid reasons. This ensures future field additions trip the coverage gate.

---

## 3. Formula Changes — Wiki/Sheets Documentation Updates

These are runtime formulas (not serialized fields), but wiki/sheets that describe derived stats or combat mechanics need updating.

### 3.1 Item Quality Stat Scaling (`Item.cs`)

The quality stat scaling formulas were substantially rewritten. If wiki/sheets compute or display blessed/godly/high-tier effective stats:

| Method | Old Formula | New Formula |
|---|---|---|
| `CalcStat` (Str/End/Dex/Agi/Int/Wis/Cha) | q2: `stat + round(stat/2)`, q3: `stat * 2` | q2: `stat + round(stat/3) + 3`, q3: `max(stat*2, q2+5, stat+6)`, q11-15: `stat + (qual-10)` |
| `CalcResists` (MR/ER/PR/VR) | Used `CalcStat` | New separate method: q2: `stat + round(stat/3) + 1`, q3: `max(stat*2, q2+1, stat+2)`, q13-14: `stat + 1` |
| `CalcAC` | Used `CalcACHPMC` | New separate method: q2: `stat + round(stat/6) + 3`, q3: `max(stat+round(stat/2), q2+4, stat+8)`, q11-15: `stat + (qual-10)` |
| `CalcACHPMC` (HP/Mana) | q2: `stat + round(stat/4)`, q3: `stat + round(stat/2)` | q2: `stat + round(stat/5) + 30`, q3: `max(stat+round(stat/2)+50, q2+1, stat+26)`, q11-15: `stat + 5*(qual-10)` |

**New quality tiers 11-15** represent forged/combined items displayed as green `+1` through `+5`.

### 3.2 Combat Formulas

| Formula | File | Change |
|---|---|---|
| Magic damage mitigation | `Character.cs:1506` | `(_dmg - _dmg * resist) * DamageTakenMod` (was `_dmg - _dmg * resist * DamageTakenMod`) |
| Spell damage bonus | `SpellVessel.cs:509` | Additive: `TargetDamage * scaleDmg + TargetDamage * (stance.SpellDamageMod - 1f)` |
| Healing cap | `SpellVessel.cs:1365` | `spell.HP * 3` (was `spell.HP * 5`) |
| Overchant contribution | `SpellVessel.cs:454` | `0.315f` (was `0.2f`) |
| Skill level scaling | `UseSkill.cs:58` | No cap (was capped at 1f) |
| Skill weapon scaling | `UseSkill.cs:150` | Base `MHDmg / 1.33f` (was `/ 2`). Two-hand = 2x. |
| Skill scaling curve | `UseSkill.cs:862` | Squared curve level 6-35, 0.45→1 (was linear 6-30, 0.5→1) |
| Innate avoidance | `NPC.cs:3372` | 10-point increments (was 15-point). Reaver shield block. |
| Loot drop probability | `LootTableProbabilityCalculator.cs:78` | Legendary base `1.97` (was `2.3` — cumulative threshold). **Already fixed.** |

### 3.3 Smithing Combine (Template `2265228`)

New combine path for high-tier item progression. Not currently exported (smithing recipes are not in the export pipeline), but if wiki documents smithing:
- Template `2265228` combines two matching equipment items into quantities 11-15
- Components cannot be General, Aura, or Charm
- Quantities 2-10 rejected as "magic too strong"

---

## 4. Dynamic Spawn Coverage

The audit identified 25 new boss encounter scripts that spawn adds dynamically. The `DynamicSpawnSourceListener` already covers most of these through the dynamic spawn catalog. Verified coverage:

- **VithArena** — 21 fields captured by `VithArenaListener`, dynamic spawns cataloged
- **Boss encounter scripts** — These are MonoBehaviour components on scene objects, not prefabs. Their dynamic spawns (adds, chests, constellations) are registered via `RaidManager.LooseAdds` at runtime. The dynamic spawn system catalogs spawn-point-driven spawns, not script-instantiated prefabs.

**Known gap (Category C, deferred):** Sivakayan Spectres zone-wide random spawns are intentionally deferred per the dynamic-spawn coverage plan.

**No new gaps identified** beyond the already-documented Category C deferral.

---

## 5. Zone Display Name Mapping

`GameManager.GetZoneDisplayNameFromZoneFileName()` (lines 1135-1275) maps scene file names to display names. Current zone exports use `scene_name` and `zone_name` (from `ZoneAnnounce.ZoneName`). The mapping includes entries like:
- `Soluna` → `Soluna's Landing`
- `PlaneOfVitheo` → `Vitheo's Plane`
- `Azynthi` → `Dark Azynthi's Garden`

**Action:** Check whether current zone exports already capture display names correctly. If `ZoneAnnounce.ZoneName` already contains the display name (not the scene name), no change needed. If exports use scene names, consider adding the display name mapping.

---

## 6. Summary Checklist

### Fields to Add to Export Pipeline

| Priority | Field | Type | Unity Type | Surfaces |
|---|---|---|---|---|
| **High** | `SimsNeedHelpToLearn` | bool | Spell | Wiki, Sheets, Guide |
| **High** | `NeverAggro` | bool | NPC | Sheets, Guide, Map |
| **High** | `NoDmgCap` | bool | NPC | Sheets, Guide |
| **High** | `CanPhantomStrike` | bool | NPC | Sheets, Guide |
| **High** | `Enrage` | float | NPC | Sheets, Guide |
| **High** | `SpawnWithStatus` | Spell ref | NPC | Wiki, Sheets, Guide |
| **High** | `NoSelfHeal` | bool | NPC | Sheets, Guide |
| **High** | `AggroRegardlessofLOS` | bool | NPC | Sheets, Guide, Map |
| **High** | `IgnoreLOSForAggro` | bool | NPC | Sheets, Guide, Map |
| **High** | `BaseArmorPenPercentage` | int | Stats | Sheets, Guide |
| **High** | `BaseAttackRollModifier` | int | Stats | Sheets, Guide |
| **High** | `CannotBeSnared` | bool | Stats | Sheets, Guide |
| **High** | `RaidCapable` | bool | ZoneAnnounce | Wiki, Sheets, Guide |
| **High** | `UseZoneAsTempBind` | string | ZoneAnnounce | Wiki, Guide |
| Medium | `GroupHOTSpell` | Spell ref | NPC | Wiki, Guide |
| Medium | `MyEmitVitaeSpell` | Spell ref | NPC | Wiki, Guide |
| Medium | `MyHOTSpell` | Spell ref | NPC | Wiki, Guide |
| Medium | `AETaunt` | Spell ref | NPC | Wiki, Guide |
| Medium | `SimPlayersIgnoreUntilOrdered` | bool | NPC | Sheets |
| Medium | `SpawnWithAtkDelay` | bool | NPC | Sheets |
| Medium | `SpawnWithBehaviorDelay` | float | NPC | Sheets |

### Manifest Updates

- Add `NPC` as a tracked type in `field-coverage.json`
- Add `Stats` as a tracked type in `field-coverage.json`
- Update `Spell.SimsNeedHelpToLearn` ignore reason → `captured`
- Update `ZoneAnnounce.RaidCapable` ignore reason → `captured`
- Update `ZoneAnnounce.UseZoneAsTempBind` ignore reason → `captured`

### Formula Documentation (No Schema Change)

- Item quality stat scaling (`CalcStat`, `CalcResists`, `CalcAC`, `CalcACHPMC`)
- New quality tiers 11-15 (green `+N` items)
- Combat formulas (magic mitigation, spell damage, healing cap, overchant)
- Skill scaling curve and weapon scaling
- Smithing combine path (template `2265228`)

### Already Covered (No Action Needed)

- All Item fields (80 captured, 13 visual-only ignored)
- All Skill fields (38 captured, 0 ignored)
- All Stance fields (14 captured, 0 ignored)
- `Spell.LevelScaledManaRestoration`, `Spell.ShapeshiftForm`, `Spell.ArmorPenPercent` — already exported
- `SpellLine` enum — exported as string via `Line.ToString()`, new `Duelist_Armor_Pen` value flows through automatically
- `LootTable.NumberOfGuaranteedDrops` — already captured
- `GameData.LootBlessBonus` — already exported as game constant
- `Character.CanNeverSeeInvis`, `DPSDummy`, `IsWyrm`, `NoRun` — already exported
- `Item.MustBeEquippedToClick`, `PlayerCannotSell`, `RareItem` — already exported
- Dynamic spawn coverage — existing catalog covers spawn-point-driven spawns
- `TeachSpell` on items — already exported as `teach_spell_stable_key`
