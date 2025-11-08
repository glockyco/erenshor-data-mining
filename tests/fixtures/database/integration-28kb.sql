-- Integration test database fixture (28KB)
-- Contains minimal but realistic game data for testing
-- Schema + sample data for Items, Spells, Characters, Quests, and junction tables

-- === SCHEMA ===

-- Minimal schema for integration tests
-- Based on Unity export system table structure (matches actual database format)

CREATE TABLE IF NOT EXISTS "Items" (
"ItemDBIndex" integer ,
"Id" varchar primary key not null ,
"StableKey" varchar ,
"ItemName" varchar ,
"Lore" varchar ,
"RequiredSlot" varchar ,
"ThisWeaponType" varchar ,
"Classes" varchar ,
"ItemLevel" integer ,
"WeaponDly" float ,
"Shield" integer ,
"WeaponProcChance" float ,
"WeaponProcOnHit" varchar ,
"WeaponProcOnHitStableKey" varchar ,
"IsWand" integer ,
"WandRange" integer ,
"WandProcChance" float ,
"WandEffect" varchar ,
"WandEffectStableKey" varchar ,
"WandBoltColorR" float ,
"WandBoltColorG" float ,
"WandBoltColorB" float ,
"WandBoltColorA" float ,
"WandBoltSpeed" float ,
"WandAttackSoundName" varchar ,
"IsBow" integer ,
"BowEffect" varchar ,
"BowEffectStableKey" varchar ,
"BowProcChance" float ,
"BowRange" integer ,
"BowArrowSpeed" float ,
"BowAttackSoundName" varchar ,
"ItemEffectOnClick" varchar ,
"ItemEffectOnClickStableKey" varchar ,
"ItemSkillUse" varchar ,
"ItemSkillUseStableKey" varchar ,
"TeachSpell" varchar ,
"TeachSpellStableKey" varchar ,
"TeachSkill" varchar ,
"TeachSkillStableKey" varchar ,
"Aura" varchar ,
"AuraStableKey" varchar ,
"WornEffect" varchar ,
"WornEffectStableKey" varchar ,
"SpellCastTime" float ,
"AssignQuestOnRead" varchar ,
"AssignQuestOnReadStableKey" varchar ,
"CompleteOnRead" varchar ,
"CompleteOnReadStableKey" varchar ,
"Template" integer ,
"TemplateIngredientIds" varchar ,
"TemplateRewardIds" varchar ,
"ItemValue" integer ,
"SellValue" integer ,
"Stackable" integer ,
"Disposable" integer ,
"Unique" integer ,
"Relic" integer ,
"NoTradeNoDestroy" integer ,
"BookTitle" varchar ,
"Mining" integer ,
"FuelSource" integer ,
"FuelLevel" integer ,
"SimPlayersCantGet" integer ,
"AttackSoundName" varchar ,
"ItemIconName" varchar ,
"EquipmentToActivate" varchar ,
"HideHairWhenEquipped" integer ,
"HideHeadWhenEquipped" integer ,
"ResourceName" varchar );

CREATE TABLE IF NOT EXISTS "Spells" (
"SpellDBIndex" integer primary key not null ,
"Id" varchar ,
"StableKey" varchar ,
"SpellName" varchar ,
"SpellDesc" varchar ,
"SpecialDescriptor" varchar ,
"Type" varchar ,
"Line" varchar ,
"Classes" varchar ,
"RequiredLevel" integer ,
"ManaCost" integer ,
"SimUsable" integer ,
"Aggro" integer ,
"SpellChargeTime" float ,
"Cooldown" float ,
"SpellDurationInTicks" integer ,
"UnstableDuration" integer ,
"InstantEffect" integer ,
"SpellRange" float ,
"SelfOnly" integer ,
"MaxLevelTarget" integer ,
"GroupEffect" integer ,
"CanHitPlayers" integer ,
"ApplyToCaster" integer ,
"TargetDamage" integer ,
"TargetHealing" integer ,
"CasterHealing" integer ,
"ShieldingAmt" integer ,
"Lifetap" integer ,
"DamageType" varchar ,
"ResistModifier" float ,
"AddProc" varchar ,
"AddProcStableKey" varchar ,
"AddProcChance" integer ,
"HP" integer ,
"AC" integer ,
"Mana" integer ,
"PercentManaRestoration" integer ,
"MovementSpeed" float ,
"Str" integer ,
"Dex" integer ,
"End" integer ,
"Agi" integer ,
"Wis" integer ,
"Int" integer ,
"Cha" integer ,
"MR" integer ,
"ER" integer ,
"PR" integer ,
"VR" integer ,
"DamageShield" integer ,
"Haste" float ,
"PercentLifesteal" float ,
"AtkRollModifier" integer ,
"BleedDamagePercent" integer ,
"RootTarget" integer ,
"StunTarget" integer ,
"CharmTarget" integer ,
"CrowdControlSpell" integer ,
"BreakOnDamage" integer ,
"BreakOnAnyAction" integer ,
"TauntSpell" integer ,
"PetToSummonResourceName" varchar ,
"PetToSummonStableKey" varchar ,
"StatusEffectToApply" varchar ,
"StatusEffectToApplyStableKey" varchar ,
"ReapAndRenew" integer ,
"ResonateChance" integer ,
"XPBonus" float ,
"AutomateAttack" integer ,
"WornEffect" integer ,
"SpellChargeFXIndex" integer ,
"SpellResolveFXIndex" integer ,
"SpellIconName" varchar ,
"ShakeDur" float ,
"ShakeAmp" float ,
"ColorR" float ,
"ColorG" float ,
"ColorB" float ,
"ColorA" float ,
"StatusEffectMessageOnPlayer" varchar ,
"StatusEffectMessageOnNPC" varchar ,
"ResourceName" varchar );

CREATE TABLE IF NOT EXISTS "Characters" (
"Id" integer primary key not null ,
"CoordinateId" integer ,
"Guid" varchar ,
"StableKey" varchar ,
"ObjectName" varchar ,
"NPCName" varchar ,
"MyWorldFaction" varchar ,
"MyFaction" varchar ,
"AggroRange" float ,
"AttackRange" float ,
"AggressiveTowards" varchar ,
"Allies" varchar ,
"IsPrefab" integer ,
"IsCommon" integer ,
"IsRare" integer ,
"IsUnique" integer ,
"IsFriendly" integer ,
"IsNPC" integer ,
"IsSimPlayer" integer ,
"IsVendor" integer ,
"IsMiningNode" integer ,
"HasStats" integer ,
"HasDialog" integer ,
"HasModifyFaction" integer ,
"IsEnabled" integer ,
"Invulnerable" integer ,
"ShoutOnDeath" varchar ,
"QuestCompleteOnDeath" varchar ,
"DestroyOnDeath" integer ,
"Level" integer ,
"BaseXpMin" float ,
"BaseXpMax" float ,
"BossXpMultiplier" float ,
"BaseHP" integer ,
"BaseAC" integer ,
"BaseMana" integer ,
"BaseStr" integer ,
"BaseEnd" integer ,
"BaseDex" integer ,
"BaseAgi" integer ,
"BaseInt" integer ,
"BaseWis" integer ,
"BaseCha" integer ,
"BaseRes" integer ,
"BaseMR" integer ,
"BaseER" integer ,
"BasePR" integer ,
"BaseVR" integer ,
"RunSpeed" float ,
"BaseLifeSteal" float ,
"BaseMHAtkDelay" float ,
"BaseOHAtkDelay" float ,
"EffectiveHP" integer ,
"EffectiveAC" integer ,
"EffectiveBaseAtkDmg" integer ,
"EffectiveAttackAbility" float ,
"EffectiveMinMR" integer ,
"EffectiveMaxMR" integer ,
"EffectiveMinER" integer ,
"EffectiveMaxER" integer ,
"EffectiveMinPR" integer ,
"EffectiveMaxPR" integer ,
"EffectiveMinVR" integer ,
"EffectiveMaxVR" integer ,
"AttackSkills" varchar ,
"AttackSpells" varchar ,
"BuffSpells" varchar ,
"HealSpells" varchar ,
"GroupHealSpells" varchar ,
"CCSpells" varchar ,
"TauntSpells" varchar ,
"PetSpell" varchar ,
"ProcOnHit" varchar ,
"ProcOnHitChance" float ,
"HandSetResistances" integer ,
"HardSetAC" integer ,
"BaseAtkDmg" integer ,
"OHAtkDmg" integer ,
"MinAtkDmg" integer ,
"DamageRangeMin" float ,
"DamageRangeMax" float ,
"DamageMult" float ,
"ArmorPenMult" float ,
"PowerAttackBaseDmg" integer ,
"PowerAttackFreq" float ,
"HealTolerance" float ,
"LeashRange" float ,
"AggroRegardlessOfLevel" integer ,
"Mobile" integer ,
"GroupEncounter" integer ,
"TreasureChest" integer ,
"DoNotLeaveCorpse" integer ,
"SetAchievementOnDefeat" varchar ,
"SetAchievementOnSpawn" varchar ,
"AggroMsg" varchar ,
"AggroEmote" varchar ,
"SpawnEmote" varchar ,
"GuildName" varchar ,
"ModifyFactions" varchar ,
"VendorDesc" varchar ,
"ItemsForSale" varchar );

CREATE INDEX IF NOT EXISTS "Characters_CoordinateId" on "Characters"("CoordinateId");

CREATE TABLE IF NOT EXISTS "Quests" (
"QuestDBIndex" integer primary key not null ,
"StableKey" varchar ,
"QuestName" varchar ,
"QuestDesc" varchar ,
"RequiredItemIds" varchar ,
"XPonComplete" integer ,
"ItemOnCompleteId" varchar ,
"GoldOnComplete" integer ,
"AssignNewQuestOnCompleteDBName" varchar ,
"CompleteOtherQuestDBNames" varchar ,
"DialogOnSuccess" varchar ,
"DialogOnPartialSuccess" varchar ,
"DisableText" varchar ,
"AffectedFactions" varchar ,
"AffectedFactionAmounts" varchar ,
"AssignThisQuestOnPartialComplete" integer ,
"Repeatable" integer ,
"DisableQuest" integer ,
"KillTurnInHolder" integer ,
"DestroyTurnInHolder" integer ,
"DropInvulnOnHolder" integer ,
"OncePerSpawnInstance" integer ,
"SetAchievementOnGet" varchar ,
"SetAchievementOnFinish" varchar ,
"DBName" varchar ,
"ResourceName" varchar );

CREATE TABLE IF NOT EXISTS "ItemClasses" (
"ItemId" varchar ,
"ClassName" varchar );

CREATE UNIQUE INDEX IF NOT EXISTS "ItemClasses_Primary_IDX" on "ItemClasses"("ItemId", "ClassName");

CREATE TABLE IF NOT EXISTS "CharacterAttackSpells" (
"CharacterId" integer ,
"SpellId" integer );

CREATE UNIQUE INDEX IF NOT EXISTS "CharacterAttackSpells_Primary_IDX" on "CharacterAttackSpells"("CharacterId", "SpellId");


-- === SAMPLE DATA ===

-- Sample Items (3 items)
INSERT INTO Items VALUES (
    0, 'rusty_sword', 'item:rustysword', 'Rusty Sword', 'A worn blade covered in rust.', 'Primary', 'OneHandSlash',
    'Warrior,Paladin', 1, 2.5, 0, 0.0, '', NULL, 0, 0, 0.0, '', NULL, 0.0, 0.0, 0.0, 0.0, 0.0, NULL,
    0, '', NULL, 0.0, 0, 0.0, NULL, '', NULL, '', NULL, '', NULL, '', NULL, '', NULL, '', NULL, 0.0, NULL, NULL, NULL, NULL, 0, '', '',
    5, 2, 0, 0, 0, 0, 0, '', 0, 0, 0, 0, NULL, 'icon_sword_rusty', '', 0, 0, 'RustySword'
);

INSERT INTO Items VALUES (
    1, 'health_potion', 'item:healthpotion', 'Health Potion', 'Restores 50 health points.', 'None', 'None',
    '', 0, 0.0, 0, 0.0, '', NULL, 0, 0, 0.0, '', NULL, 0.0, 0.0, 0.0, 0.0, 0.0, NULL,
    0, '', NULL, 0.0, 0, 0.0, NULL, 'heal_minor', 'spell:heal_minor', '', NULL, '', NULL, '', NULL, '', NULL, '', NULL, 0.0, NULL, NULL, NULL, NULL, 0, '', '',
    10, 5, 1, 1, 0, 0, 0, '', 0, 0, 0, 0, NULL, 'icon_potion_health', '', 0, 0, 'HealthPotion'
);

INSERT INTO Items VALUES (
    2, 'wizard_staff', 'item:apprenticestaff', 'Apprentice Staff', 'A basic staff for beginning wizards.', 'Primary', 'TwoHandBlunt',
    'Wizard,Necromancer', 5, 3.0, 0, 0.0, '', NULL, 0, 0, 0.0, '', NULL, 0.0, 0.0, 0.0, 0.0, 0.0, NULL,
    0, '', NULL, 0.0, 0, 0.0, NULL, '', NULL, '', NULL, '', NULL, '', NULL, '', NULL, '', NULL, 0.0, NULL, NULL, NULL, NULL, 0, '', '',
    25, 12, 0, 0, 0, 0, 0, '', 0, 0, 0, 0, NULL, 'icon_staff_wood', '', 0, 0, 'ApprenticeStaff'
);

-- Sample Spells (3 spells)
INSERT INTO Spells VALUES (
    0, 'fireball', 'spell:fireball', 'Fireball', 'Hurls a ball of fire at your enemy.', '', 'Damage', 'Fire',
    'Wizard', 5, 25, 1, 100, 2.5, 0.0, 0, 0, 1, 30.0, 0, 0, 0, 0, 0,
    50, 0, 0, 0, 0, 'Fire', 0.0, '', NULL, 0, 0, 0, 0, 0, 0.0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', NULL, '', NULL, 0, 0, 0.0, 0, 0,
    12, 15, NULL, 0.0, 0.0, 1.0, 0.5, 0.0, 1.0, '', '', 'Fireball'
);

INSERT INTO Spells VALUES (
    1, 'heal', 'spell:minorheal', 'Minor Heal', 'Heals your target for a small amount.', '', 'Healing', 'Heal',
    'Cleric', 1, 10, 1, 0, 1.5, 0.0, 0, 0, 1, 25.0, 0, 0, 0, 0, 0,
    0, 30, 0, 0, 0, '', 0.0, '', NULL, 0, 0, 0, 0, 0, 0.0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', NULL, '', NULL, 0, 0, 0.0, 0, 0,
    8, 10, NULL, 0.0, 0.0, 0.8, 0.9, 0.8, 1.0, '', '', 'MinorHeal'
);

INSERT INTO Spells VALUES (
    2, 'shield', 'spell:arcaneshield', 'Arcane Shield', 'Surrounds you with a protective barrier.', '', 'Buff', 'Protection',
    'Wizard', 3, 15, 1, 0, 2.0, 0.0, 600, 0, 0, 0.0, 1, 0, 0, 0, 1,
    0, 0, 0, 0, 0, '', 0.0, '', NULL, 0, 0, 20, 0, 0, 0.0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', NULL, '', NULL, 0, 0, 0.0, 0, 0,
    11, 13, NULL, 0.0, 0.0, 0.5, 0.7, 0.9, 1.0, '', '', 'ArcaneShield'
);

-- Sample Characters (3 characters)
INSERT INTO Characters VALUES (
    1, NULL, 'char_001', 'character:goblin scout', 'Goblin Scout', 'Goblin Scout', NULL, 'Goblin', 15.0, 3.0, '', '',
    1, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, NULL, NULL, 0,
    3, 10.0, 12.0, 1.0, 45, 10, 0, 8, 10, 6, 8, 5, 6, 5, 0, 15, 20, 10, 15,
    1.0, 0.0, 2.0, 0.0, 45, 10, 8, 6.0, 15, 20, 20, 25, 10, 15, 15, 20,
    '', '', '', '', '', '', '', '', '', 0.0, 0, 0, 8, 0, 2, 0.8, 1.2, 1.0, 0.0, 0, 0.0, 0.0,
    50.0, 0, 1, 0, 0, 0, '', '', 'You dare challenge me?', 'growls', 'appears', '', '', '', NULL
);

INSERT INTO Characters VALUES (
    2, NULL, 'char_002', 'character:marcus the guard', 'Town Guard', 'Marcus the Guard', NULL, 'Guard', 0.0, 3.0, 'Goblin', '',
    1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 1, 0, NULL, NULL, 0,
    10, 50.0, 60.0, 1.0, 200, 50, 0, 30, 35, 25, 30, 20, 25, 20, 0, 40, 35, 30, 35,
    1.0, 0.0, 2.5, 0.0, 200, 50, 25, 20.0, 40, 50, 35, 45, 30, 40, 35, 45,
    '', '', '', '', '', '', '', '', '', 0.0, 0, 0, 25, 0, 15, 0.85, 1.15, 1.0, 0.0, 0, 0.0, 0.0,
    100.0, 0, 1, 0, 0, 0, '', '', '', '', '', '', '', '', NULL
);

INSERT INTO Characters VALUES (
    3, NULL, 'char_003', 'character:archmage elara', 'Elder Mage', 'Archmage Elara', NULL, 'Mage', 0.0, 25.0, '', '',
    1, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0, 0, 1, 1, NULL, NULL, 0,
    40, 800.0, 1000.0, 2.0, 500, 30, 400, 15, 25, 20, 25, 80, 75, 50, 0, 85, 80, 75, 80,
    1.0, 0.0, 3.0, 0.0, 500, 30, 45, 50.0, 85, 90, 80, 85, 75, 80, 80, 85,
    '', '0,1', '2', '', '', '', '', '', '', 0.0, 0, 0, 45, 0, 20, 0.9, 1.1, 1.0, 0.0, 0, 0.0, 0.0,
    150.0, 0, 1, 0, 0, 0, 'DEFEAT_ARCHMAGE', '', '', '', '', '', '', '', NULL
);

-- Sample Quests (2 quests)
INSERT INTO Quests VALUES (
    0, 'quest:goblin_trouble', 'Goblin Trouble', 'The goblins have been raiding our supplies. Bring me 5 goblin ears as proof of your valor.',
    'goblin_ear (5)', 100, 'rusty_sword', 50, '', '', 'Well done! Those goblins won''t trouble us anymore.',
    'You still need more goblin ears.', '', '', '', 0, 0, 0, 0, 0, 0, 0, '', '', 'GOBLIN_TROUBLE', 'QuestGoblinTrouble'
);

INSERT INTO Quests VALUES (
    1, 'quest:learn_the_basics', 'Learn the Basics', 'Speak with the trainer to learn your first spell.',
    '', 50, '', 10, 'GOBLIN_TROUBLE', '', 'Excellent! Now you''re ready for real adventure.',
    '', '', '', '', 0, 0, 0, 0, 0, 0, 0, '', 'COMPLETE_TRAINING', 'LEARN_BASICS', 'QuestLearnBasics'
);

-- Sample Junction Data
INSERT INTO ItemClasses VALUES ('rusty_sword', 'Warrior');
INSERT INTO ItemClasses VALUES ('rusty_sword', 'Paladin');
INSERT INTO ItemClasses VALUES ('wizard_staff', 'Wizard');
INSERT INTO ItemClasses VALUES ('wizard_staff', 'Necromancer');

INSERT INTO CharacterAttackSpells VALUES (3, 0);
INSERT INTO CharacterAttackSpells VALUES (3, 1);
