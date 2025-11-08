SELECT
   -- Identity & Basic Info
   c.Guid,
   c.ObjectName,
   c.NPCName,
   COALESCE(f.FactionDesc, c.MyWorldFaction) AS MyWorldFaction,
   c.MyFaction,
   c.Level,
   -- Effective Combat Stats (calculated runtime values players encounter)
   c.EffectiveHP,
   c.EffectiveAC,
   c.EffectiveAttackAbility,
   c.EffectiveBaseAtkDmg,
   c.EffectiveMinMR,
   c.EffectiveMaxMR,
   c.EffectiveMinER,
   c.EffectiveMaxER,
   c.EffectiveMinPR,
   c.EffectiveMaxPR,
   c.EffectiveMinVR,
   c.EffectiveMaxVR,
   -- Base Stats (no effective version exists)
   c.BaseMana,
   c.BaseStr,
   c.BaseEnd,
   c.BaseDex,
   c.BaseAgi,
   c.BaseInt,
   c.BaseWis,
   c.BaseCha,
   c.BaseRes,
   c.RunSpeed,
   c.BaseLifeSteal,
   c.BaseMHAtkDelay,
   c.BaseOHAtkDelay,
   -- XP & Rewards
   c.BaseXpMin,
   c.BaseXpMax,
   c.BossXpMultiplier,
   -- Combat Mechanics
   c.OHAtkDmg,
   c.MinAtkDmg,
   c.DamageRangeMin,
   c.DamageRangeMax,
   c.DamageMult,
   c.ArmorPenMult,
   c.PowerAttackBaseDmg,
   c.PowerAttackFreq,
   c.HealTolerance,
   -- AI Behavior & Movement
   c.AggroRange,
   c.AttackRange,
   c.LeashRange,
   c.AggressiveTowards,
   c.Allies,
   c.ModifyFactions,
   c.Mobile,
   c.GroupEncounter,
   c.AggroRegardlessOfLevel,
   -- Spells & Abilities
   -- Note: Attack/buff/heal/CC/taunt spells are now in junction tables:
   -- CharacterAttackSkillRecord, CharacterAttackSpellRecord, CharacterBuffSpellRecord,
   -- CharacterHealSpellRecord, CharacterGroupHealSpellRecord, CharacterCCSpellRecord, CharacterTauntSpellRecord
   c.PetSpellStableKey,
   c.ProcOnHitStableKey,
   c.ProcOnHitChance,
   -- Special Properties & Quest Integration
   c.Invulnerable,
   c.QuestCompleteOnDeath,
   c.SetAchievementOnDefeat,
   c.SetAchievementOnSpawn,
   -- Flavor Text & Messages
   c.AggroMsg,
   c.AggroEmote,
   c.SpawnEmote,
   c.ShoutOnDeath,
   -- Vendor Information
   c.IsVendor,
   c.VendorDesc,
   c.ItemsForSale
FROM Characters c
LEFT JOIN Factions f ON f.REFNAME = c.MyWorldFaction;
