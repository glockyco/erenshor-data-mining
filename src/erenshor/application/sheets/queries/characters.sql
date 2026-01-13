SELECT
    -- Identity & Basic Info
    c.StableKey,
    c.ObjectName,
    c.NPCName,
    COALESCE(f.FactionDesc, c.MyWorldFactionStableKey) AS MyWorldFaction,
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
    (SELECT GROUP_CONCAT(FactionName, ', ')
     FROM CharacterAggressiveFactions caf
     WHERE caf.CharacterStableKey = c.StableKey) AS AggressiveTowardsFactions,
    (SELECT GROUP_CONCAT(FactionName, ', ')
     FROM CharacterAlliedFactions calf
     WHERE calf.CharacterStableKey = c.StableKey) AS AlliedFactions,
    (SELECT GROUP_CONCAT(FactionStableKey || ' (' || ModifierValue || ')', ', ')
     FROM CharacterFactionModifiers cfm
     WHERE cfm.CharacterStableKey = c.StableKey) AS FactionModifierStableKeys,
    c.Mobile,
    c.GroupEncounter,
    c.AggroRegardlessOfLevel,
    -- Spells & Abilities
    c.PetSpellStableKey,
    c.ProcOnHitStableKey,
    c.ProcOnHitChance,
    (SELECT GROUP_CONCAT(SpellStableKey, ', ')
     FROM CharacterAttackSpells cas
     WHERE cas.CharacterStableKey = c.StableKey) AS AttackSpellStableKeys,
    (SELECT GROUP_CONCAT(SpellStableKey, ', ')
     FROM CharacterBuffSpells cbs
     WHERE cbs.CharacterStableKey = c.StableKey) AS BuffSpellStableKeys,
    (SELECT GROUP_CONCAT(SpellStableKey, ', ')
     FROM CharacterHealSpells chs
     WHERE chs.CharacterStableKey = c.StableKey) AS HealSpellStableKeys,
    (SELECT GROUP_CONCAT(SpellStableKey, ', ')
     FROM CharacterGroupHealSpells cghs
     WHERE cghs.CharacterStableKey = c.StableKey) AS GroupHealSpellStableKeys,
    (SELECT GROUP_CONCAT(SpellStableKey, ', ')
     FROM CharacterCCSpells cccs
     WHERE cccs.CharacterStableKey = c.StableKey) AS CCSpellStableKeys,
    (SELECT GROUP_CONCAT(SpellStableKey, ', ')
     FROM CharacterTauntSpells cts
     WHERE cts.CharacterStableKey = c.StableKey) AS TauntSpellStableKeys,
    (SELECT GROUP_CONCAT(SkillStableKey, ', ')
     FROM CharacterAttackSkills cask
     WHERE cask.CharacterStableKey = c.StableKey) AS AttackSkillStableKeys,
    -- Special Properties & Quest Integration
    c.Invulnerable,
    c.QuestCompleteOnDeath AS QuestCompleteOnDeathStableKey,
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
    (SELECT GROUP_CONCAT(ItemStableKey, ', ')
     FROM CharacterVendorItems cvi
     WHERE cvi.CharacterStableKey = c.StableKey) AS VendorItemStableKeys
FROM Characters c
LEFT JOIN Factions f ON f.StableKey = c.MyWorldFactionStableKey;
