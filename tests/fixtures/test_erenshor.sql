-- Minimal test database for integration tests
-- Contains representative data for all content types:
-- - 20 items (weapons, armor, auras, consumables, ability books, molds)
-- - 10 characters (unique, hostile, friendly, bosses)
-- - 11 abilities (8 spells and 3 skills)
-- - 3 fishing zones
-- This is a minimal dataset designed for fast tests, not comprehensive coverage

-- Core tables schema
CREATE TABLE IF NOT EXISTS "Items" (
"ItemDBIndex" integer ,
"Id" varchar primary key not null ,
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
"IsWand" integer ,
"WandRange" integer ,
"WandProcChance" float ,
"WandEffect" varchar ,
"WandBoltColorR" float ,
"WandBoltColorG" float ,
"WandBoltColorB" float ,
"WandBoltColorA" float ,
"WandBoltSpeed" float ,
"WandAttackSoundName" varchar ,
"IsBow" integer ,
"BowEffect" varchar ,
"BowProcChance" float ,
"BowRange" integer ,
"BowArrowSpeed" float ,
"BowAttackSoundName" varchar ,
"ItemEffectOnClick" varchar ,
"ItemSkillUse" varchar ,
"TeachSpell" varchar ,
"TeachSkill" varchar ,
"Aura" varchar ,
"WornEffect" varchar ,
"SpellCastTime" float ,
"AssignQuestOnRead" varchar ,
"CompleteOnRead" varchar ,
"Template" integer ,
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
"ResourceName" varchar
);

CREATE TABLE IF NOT EXISTS "ItemStats" (
"ItemId" varchar ,
"Quality" varchar ,
"WeaponDmg" integer ,
"HP" integer ,
"AC" integer ,
"Mana" integer ,
"Str" integer ,
"End" integer ,
"Dex" integer ,
"Agi" integer ,
"Int" integer ,
"Wis" integer ,
"Cha" integer ,
"Res" integer ,
"MR" integer ,
"ER" integer ,
"PR" integer ,
"VR" integer ,
"StrScaling" float ,
"EndScaling" float ,
"DexScaling" float ,
"AgiScaling" float ,
"IntScaling" float ,
"WisScaling" float ,
"ChaScaling" float ,
"ResistScaling" float ,
"MitigationScaling" float ,
"WikiString" varchar
);
CREATE UNIQUE INDEX "ItemStats_Primary_IDX" on "ItemStats"("ItemId", "Quality");

CREATE TABLE IF NOT EXISTS "Characters" (
"Id" integer primary key not null ,
"CoordinateId" integer ,
"Guid" varchar ,
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
"VendorDesc" varchar
);

CREATE TABLE IF NOT EXISTS "SpawnPoints" (
"Id" integer primary key not null ,
"CoordinateId" integer ,
"IsEnabled" integer ,
"RareNPCChance" integer ,
"LevelMod" integer ,
"SpawnDelay1" float ,
"SpawnDelay2" float ,
"SpawnDelay3" float ,
"SpawnDelay4" float ,
"Staggerable" integer ,
"StaggerMod" float ,
"NightSpawn" integer ,
"PatrolPoints" varchar ,
"LoopPatrol" integer ,
"RandomWanderRange" float ,
"SpawnUponQuestCompleteDBName" varchar ,
"StopIfQuestCompleteDBNames" varchar ,
"ProtectorName" varchar
);

CREATE TABLE IF NOT EXISTS "SpawnPointCharacters" (
"SpawnPointId" integer ,
"CharacterGuid" varchar ,
"SpawnChance" float ,
"IsCommon" integer ,
"IsRare" integer
);
CREATE UNIQUE INDEX "SpawnPointCharacters_Primary_IDX" on "SpawnPointCharacters"("SpawnPointId", "CharacterGuid");

CREATE TABLE IF NOT EXISTS "Spells" (
"SpellDBIndex" integer primary key not null ,
"Id" varchar ,
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
"StatusEffectToApply" varchar ,
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
"ResourceName" varchar
);

CREATE TABLE IF NOT EXISTS "Skills" (
"Id" varchar primary key not null ,
"SkillName" varchar ,
"SkillDesc" varchar ,
"TypeOfSkill" varchar ,
"DuelistRequiredLevel" integer ,
"PaladinRequiredLevel" integer ,
"ArcanistRequiredLevel" integer ,
"DruidRequiredLevel" integer ,
"StormcallerRequiredLevel" integer ,
"Cooldown" real ,
"EffectToApplyId" varchar ,
"CastOnTargetId" varchar ,
"RequireBow" integer ,
"RequireShield" integer ,
"DamageType" varchar ,
"ResourceName" varchar
);

CREATE TABLE IF NOT EXISTS "LootDrops" (
"CharacterPrefabGuid" varchar ,
"ItemId" varchar ,
"DropProbability" float ,
"ExpectedPerKill" float ,
"DropCountDistribution" varchar ,
"IsActual" integer ,
"IsGuaranteed" integer ,
"IsCommon" integer ,
"IsUncommon" integer ,
"IsRare" integer ,
"IsLegendary" integer ,
"IsUnique" integer ,
"IsVisible" integer
);
CREATE UNIQUE INDEX "LootDrops_Primary_IDX" on "LootDrops"("CharacterPrefabGuid", "ItemId");

CREATE TABLE IF NOT EXISTS "WaterFishables" (
"WaterId" integer ,
"Type" varchar ,
"ItemName" varchar ,
"DropChance" float
);
CREATE UNIQUE INDEX "WaterFishable_Primary_IDX" on "WaterFishables"("WaterId", "Type", "ItemName");

CREATE TABLE IF NOT EXISTS "Waters" (
"Id" integer primary key autoincrement not null ,
"CoordinateId" integer ,
"Width" float ,
"Height" float ,
"Depth" float
);
CREATE INDEX "Waters_CoordinateId" on "Waters"("CoordinateId");

CREATE TABLE IF NOT EXISTS "Factions" (
"FactionDBIndex" integer ,
"FactionName" varchar ,
"FactionDesc" varchar ,
"DefaultValue" float ,
"REFNAME" varchar primary key not null ,
"ResourceName" varchar
);

CREATE TABLE IF NOT EXISTS "Coordinates" (
"Id" integer primary key not null ,
"Scene" varchar ,
"X" float ,
"Y" float ,
"Z" float ,
"Category" varchar ,
"AchievementTriggerId" integer ,
"CharacterId" integer ,
"DoorId" integer ,
"MiningNodeId" integer ,
"SecretPassageId" integer ,
"SpawnPointId" integer ,
"TeleportId" integer ,
"TreasureLocId" integer ,
"WaterId" integer ,
"ZoneLineId" integer ,
"ItemBagId" integer
);

CREATE TABLE IF NOT EXISTS "ZoneAnnounces" (
"SceneName" varchar primary key not null ,
"ZoneName" varchar ,
"IsDungeon" integer ,
"Achievement" varchar ,
"CompleteQuestOnEnter" varchar ,
"CompleteSecondQuestOnEnter" varchar ,
"AssignQuestOnEnter" varchar
);

CREATE TABLE IF NOT EXISTS "MiningNodeItems" (
"MiningNodeId" integer ,
"ItemName" varchar ,
"DropChance" float
);
CREATE UNIQUE INDEX "MiningNodeItems_Primary_IDX" on "MiningNodeItems"("MiningNodeId", "ItemName");

CREATE TABLE IF NOT EXISTS "Quests" (
"QuestDBIndex" integer primary key not null ,
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
"ResourceName" varchar
);

-- Junction tables for many-to-many relationships
CREATE TABLE IF NOT EXISTS "ItemClasses" (
"ItemId" varchar ,
"ClassName" varchar );
CREATE UNIQUE INDEX "ItemClasses_Primary_IDX" on "ItemClasses"("ItemId", "ClassName");

CREATE TABLE IF NOT EXISTS "SpellClasses" (
"SpellId" integer ,
"ClassName" varchar );
CREATE UNIQUE INDEX "SpellClasses_Primary_IDX" on "SpellClasses"("SpellId", "ClassName");

-- Character junction tables
CREATE TABLE IF NOT EXISTS "CharacterAggressiveFactions" (
"CharacterId" integer ,
"FactionName" varchar );
CREATE UNIQUE INDEX "CharacterAggressiveFactions_Primary_IDX" on "CharacterAggressiveFactions"("CharacterId", "FactionName");

CREATE TABLE IF NOT EXISTS "CharacterAlliedFactions" (
"CharacterId" integer ,
"FactionName" varchar );
CREATE UNIQUE INDEX "CharacterAlliedFactions_Primary_IDX" on "CharacterAlliedFactions"("CharacterId", "FactionName");

CREATE TABLE IF NOT EXISTS "CharacterAttackSkills" (
"CharacterId" integer ,
"SkillId" integer );
CREATE UNIQUE INDEX "CharacterAttackSkills_Primary_IDX" on "CharacterAttackSkills"("CharacterId", "SkillId");

CREATE TABLE IF NOT EXISTS "CharacterAttackSpells" (
"CharacterId" integer ,
"SpellId" integer );
CREATE UNIQUE INDEX "CharacterAttackSpells_Primary_IDX" on "CharacterAttackSpells"("CharacterId", "SpellId");

CREATE TABLE IF NOT EXISTS "CharacterBuffSpells" (
"CharacterId" integer ,
"SpellId" integer );
CREATE UNIQUE INDEX "CharacterBuffSpells_Primary_IDX" on "CharacterBuffSpells"("CharacterId", "SpellId");

CREATE TABLE IF NOT EXISTS "CharacterCCSpells" (
"CharacterId" integer ,
"SpellId" integer );
CREATE UNIQUE INDEX "CharacterCCSpells_Primary_IDX" on "CharacterCCSpells"("CharacterId", "SpellId");

CREATE TABLE IF NOT EXISTS "CharacterFactionModifiers" (
"CharacterId" integer ,
"FactionREFNAME" varchar ,
"ModifierValue" integer );
CREATE UNIQUE INDEX "CharacterFactionModifiers_Primary_IDX" on "CharacterFactionModifiers"("CharacterId", "FactionREFNAME");

CREATE TABLE IF NOT EXISTS "CharacterGroupHealSpells" (
"CharacterId" integer ,
"SpellId" integer );
CREATE UNIQUE INDEX "CharacterGroupHealSpells_Primary_IDX" on "CharacterGroupHealSpells"("CharacterId", "SpellId");

CREATE TABLE IF NOT EXISTS "CharacterHealSpells" (
"CharacterId" integer ,
"SpellId" integer );
CREATE UNIQUE INDEX "CharacterHealSpells_Primary_IDX" on "CharacterHealSpells"("CharacterId", "SpellId");

CREATE TABLE IF NOT EXISTS "CharacterTauntSpells" (
"CharacterId" integer ,
"SpellId" integer );
CREATE UNIQUE INDEX "CharacterTauntSpells_Primary_IDX" on "CharacterTauntSpells"("CharacterId", "SpellId");

CREATE TABLE IF NOT EXISTS "CharacterVendorItems" (
"CharacterId" integer ,
"ItemName" varchar );
CREATE UNIQUE INDEX "CharacterVendorItems_Primary_IDX" on "CharacterVendorItems"("CharacterId", "ItemName");

-- Crafting junction tables
CREATE TABLE IF NOT EXISTS "CraftingRecipes" (
"RecipeItemId" varchar ,
"MaterialSlot" integer ,
"MaterialItemId" varchar ,
"MaterialQuantity" integer );
CREATE UNIQUE INDEX "CraftingRecipes_Primary_IDX" on "CraftingRecipes"("RecipeItemId", "MaterialSlot");

CREATE TABLE IF NOT EXISTS "CraftingRewards" (
"RecipeItemId" varchar ,
"RewardSlot" integer ,
"RewardItemId" varchar ,
"RewardQuantity" integer );
CREATE UNIQUE INDEX "CraftingRewards_Primary_IDX" on "CraftingRewards"("RecipeItemId", "RewardSlot");

-- Test data: Items (20 items covering all types)
-- Weapons (Primary/Secondary)
INSERT INTO Items (Id, ItemName, RequiredSlot, ThisWeaponType, ItemLevel, WeaponDly, ItemValue, SellValue, ResourceName)
VALUES
(1, 'Test Sword', 'Primary', 'Sword', 10, 2.8, 500, 325, 'TestSword'),
(2, 'Test Bow', 'PrimaryOrSecondary', 'Bow', 15, 3.0, 800, 520, 'TestBow'),
(3, 'Test Dagger', 'Secondary', 'Dagger', 5, 2.0, 200, 130, 'TestDagger');

INSERT INTO ItemStats (ItemId, Quality, WeaponDmg, Str, Dex)
VALUES
('1', '0', 15, 5, 0),
('1', '1', 22, 8, 0),
('1', '2', 30, 12, 0),
('2', '0', 18, 0, 8),
('2', '1', 27, 0, 12),
('2', '2', 36, 0, 18),
('3', '0', 12, 3, 5),
('3', '1', 18, 5, 8),
('3', '2', 24, 8, 12);

-- Armor (Head, Chest, Legs, etc.)
INSERT INTO Items (Id, ItemName, RequiredSlot, ItemLevel, ItemValue, SellValue, ResourceName)
VALUES
(4, 'Test Helm', 'Head', 10, 400, 260, 'TestHelm'),
(5, 'Test Chest', 'Chest', 10, 600, 390, 'TestChest'),
(6, 'Test Legs', 'Legs', 10, 500, 325, 'TestLegs');

INSERT INTO ItemStats (ItemId, Quality, AC, HP, Str, End)
VALUES
('4', '0', 15, 50, 5, 0),
('4', '1', 22, 75, 8, 0),
('4', '2', 30, 100, 12, 0),
('5', '0', 25, 100, 8, 5),
('5', '1', 35, 150, 12, 8),
('5', '2', 45, 200, 18, 12),
('6', '0', 20, 75, 5, 5),
('6', '1', 28, 110, 8, 8),
('6', '2', 36, 145, 12, 12);

-- Auras
INSERT INTO Items (Id, ItemName, RequiredSlot, Aura, ItemValue, SellValue, ResourceName)
VALUES
(7, 'Test Aura of Power', 'Aura', 'Increases Str by 10', 5000, 3250, 'TestAuraPower'),
(8, 'Test Aura of Wisdom', 'Aura', 'Increases Wis by 10', 5000, 3250, 'TestAuraWisdom');

-- Consumables (General slot with click effect)
INSERT INTO Items (Id, ItemName, RequiredSlot, ItemEffectOnClick, ItemValue, SellValue, Stackable, ResourceName)
VALUES
(9, 'Test Health Potion', 'General', 'Spell: Heal (100)', 50, 32, 20, 'TestHealthPotion'),
(10, 'Test Mana Potion', 'General', 'Spell: Restore Mana (100)', 50, 32, 20, 'TestManaPotion');

-- Ability Books (TeachSpell or TeachSkill)
INSERT INTO Items (Id, ItemName, RequiredSlot, TeachSpell, ItemValue, SellValue, ResourceName)
VALUES
(11, 'Test Spell Book: Fireball', 'General', 'Spell: Fireball (1)', 1000, 650, 'TestSpellBookFireball'),
(12, 'Test Spell Book: Heal', 'General', 'Spell: Heal (2)', 800, 520, 'TestSpellBookHeal');

INSERT INTO Items (Id, ItemName, RequiredSlot, TeachSkill, ItemValue, SellValue, ResourceName)
VALUES
(13, 'Test Skill Book: Mining', 'General', 'Skill: Mining (1)', 500, 325, 'TestSkillBookMining');

-- Ability book teaching new skill (for comprehensive testing)
INSERT INTO Items (Id, ItemName, Lore, RequiredSlot, TeachSkill, ItemValue, SellValue, ResourceName)
VALUES
(1001, 'Skill Book: Power Strike', 'Teaches the Power Strike skill', 'General', 'Skill: Power Strike (100)', 500, 325, 'SkillBookPowerStrike');

-- Molds (Template=1)
INSERT INTO Items (Id, ItemName, RequiredSlot, Template, ItemValue, SellValue, ResourceName)
VALUES
(14, 'Test Mold: Sword', 'General', 1, 100, 65, 'TestMoldSword');

-- General items (no special properties)
INSERT INTO Items (Id, ItemName, RequiredSlot, ItemValue, SellValue, ResourceName)
VALUES
(15, 'Test Iron Ore', 'General', 25, 16, 'TestIronOre'),
(16, 'Test Leather', 'General', 30, 19, 'TestLeather'),
(17, 'Test Gem', 'General', 500, 325, 'TestGem');

-- Edge cases
-- No sell value
INSERT INTO Items (Id, ItemName, RequiredSlot, ItemValue, SellValue, ResourceName)
VALUES
(18, 'Test Quest Item', 'General', 0, 0, 'TestQuestItem');

-- Unique item
INSERT INTO Items (Id, ItemName, RequiredSlot, ItemValue, SellValue, "Unique", ResourceName)
VALUES
(19, 'Test Legendary Sword', 'Primary', 10000, 6500, 1, 'TestLegendarySword');

INSERT INTO ItemStats (ItemId, Quality, WeaponDmg, Str, Dex)
VALUES
('19', '0', 75, 20, 10),
('19', '1', 112, 30, 15),
('19', '2', 150, 45, 22);

-- Relic
INSERT INTO Items (Id, ItemName, RequiredSlot, ItemValue, SellValue, "Relic", ResourceName)
VALUES
(20, 'Test Ancient Relic', 'General', 50000, 32500, 1, 'TestAncientRelic');

-- Test data: Characters (10 characters)
-- Unique boss
INSERT INTO Characters (Id, Guid, ObjectName, NPCName, MyWorldFaction, IsUnique, IsFriendly, Level, BaseXpMin, BaseXpMax, BaseHP, BaseAC, BaseStr, BaseEnd, BaseDex, BaseAgi, BaseInt, BaseWis, BaseCha)
VALUES
(1, 'boss001', 'TestDragon', 'Ancient Dragon', 'Hostile', 1, 0, 50, 5000, 5000, 10000, 300, 80, 60, 40, 30, 20, 20, 10);

-- Rare hostile
INSERT INTO Characters (Id, Guid, ObjectName, NPCName, MyWorldFaction, IsRare, IsFriendly, Level, BaseXpMin, BaseXpMax, BaseHP, BaseAC, BaseStr, BaseEnd, BaseDex)
VALUES
(2, 'rare001', 'TestElite', 'Elite Guard', 'Hostile', 1, 0, 30, 500, 600, 3000, 200, 50, 40, 30);

-- Common hostile
INSERT INTO Characters (Id, Guid, ObjectName, NPCName, MyWorldFaction, IsCommon, IsFriendly, Level, BaseXpMin, BaseXpMax, BaseHP, BaseAC, BaseStr)
VALUES
(3, 'common001', 'TestGoblin', 'Goblin Scout', 'Hostile', 1, 0, 10, 50, 60, 300, 50, 20),
(4, 'common002', 'TestOrc', 'Orc Warrior', 'Hostile', 1, 0, 15, 100, 120, 600, 75, 30),
(5, 'common003', 'TestWolf', 'Dire Wolf', 'Hostile', 1, 0, 12, 60, 75, 400, 60, 25);

-- Friendly NPCs
INSERT INTO Characters (Id, Guid, ObjectName, NPCName, MyWorldFaction, IsFriendly, IsNPC, IsVendor, Level)
VALUES
(6, 'npc001', 'TestVendor', 'Merchant Bob', 'Friendly', 1, 1, 1, 1),
(7, 'npc002', 'TestQuestGiver', 'Elder Sarah', 'Friendly', 1, 1, 0, 1);

-- Unique NPC with coordinates
INSERT INTO Coordinates (Id, X, Y, Z, Scene) VALUES (1, 100.5, 50.2, 200.8, 'TestZone');
INSERT INTO Characters (Id, CoordinateId, Guid, ObjectName, NPCName, MyWorldFaction, IsUnique, IsFriendly, IsNPC, Level)
VALUES
(8, 1, 'npc003', 'TestBoss', 'Dungeon Master', 'Hostile', 1, 0, 0, 40);

-- More common enemies
INSERT INTO Characters (Id, Guid, ObjectName, NPCName, MyWorldFaction, IsCommon, IsFriendly, Level, BaseXpMin, BaseXpMax, BaseHP)
VALUES
(9, 'common004', 'TestSpider', 'Giant Spider', 'Hostile', 1, 0, 8, 40, 50, 250),
(10, 'common005', 'TestBat', 'Cave Bat', 'Hostile', 1, 0, 5, 20, 25, 100);

-- Coordinates for spawn points
INSERT INTO Coordinates (Id, Scene, X, Y, Z, SpawnPointId)
VALUES
(2, 'TestZone', 100.0, 50.0, 200.0, 1),
(3, 'TestZone', 150.0, 50.0, 250.0, 2);

-- ZoneAnnounces for test zones
INSERT INTO ZoneAnnounces (SceneName, ZoneName, IsDungeon)
VALUES
('TestZone', 'Test Zone', 0),
('TestZone2', 'Test Zone 2', 0);

-- Spawn points for characters
INSERT INTO SpawnPoints (Id, CoordinateId, SpawnDelay1)
VALUES
(1, 2, 300.0),
(2, 3, 180.0);

INSERT INTO SpawnPointCharacters (SpawnPointId, CharacterGuid, SpawnChance)
VALUES
(1, 'common001', 0.5),
(1, 'common002', 0.3),
(1, 'rare001', 0.1),
(2, 'common003', 0.6),
(2, 'common004', 0.4);

-- Loot drops
INSERT INTO LootDrops (CharacterPrefabGuid, ItemId, DropProbability, IsGuaranteed, IsActual, IsVisible)
VALUES
('boss001', '19', 0.05, 0, 1, 1),  -- Boss drops legendary
('boss001', '17', 1.0, 1, 1, 1),  -- Boss guaranteed gems
('rare001', '15', 0.3, 0, 1, 1),
('common001', '15', 0.1, 0, 1, 1),
('common002', '16', 0.15, 0, 1, 1),
('common001', '17', 0.2, 0, 1, 1);  -- Goblin drops Test Gem

-- Test data: Spells (8 spells)
INSERT INTO Spells (SpellDBIndex, Id, SpellName, SpellDesc, Type, Line, Classes, RequiredLevel, ManaCost, Cooldown, SpellRange, TargetDamage, DamageType, ResourceName)
VALUES
(1, '1', 'Fireball', 'Hurls a ball of fire at target', 'Direct Damage', 'Fire', 'Wizard', 5, 50, 3.0, 30.0, 100, 'Fire', 'SpellFireball'),
(2, '2', 'Ice Lance', 'Pierces target with ice', 'Direct Damage', 'Cold', 'Wizard', 10, 75, 4.0, 30.0, 150, 'Cold', 'SpellIceLance'),
(3, '3', 'Lightning Bolt', 'Strikes target with lightning', 'Direct Damage', 'Energy', 'Wizard', 15, 100, 5.0, 30.0, 200, 'Energy', 'SpellLightningBolt');

INSERT INTO Spells (SpellDBIndex, Id, SpellName, SpellDesc, Type, Line, Classes, RequiredLevel, ManaCost, Cooldown, SpellRange, TargetHealing, ResourceName)
VALUES
(4, '4', 'Heal', 'Heals target', 'Healing', 'Healing', 'Cleric', 1, 40, 2.0, 30.0, 100, 'SpellHeal'),
(5, '5', 'Greater Heal', 'Greatly heals target', 'Healing', 'Healing', 'Cleric', 10, 100, 4.0, 30.0, 300, 'SpellGreaterHeal');

INSERT INTO Spells (SpellDBIndex, Id, SpellName, SpellDesc, Type, Line, Classes, RequiredLevel, ManaCost, Cooldown, ResourceName)
VALUES
(6, '6', 'Shield', 'Protects target', 'Buff', 'Buff', 'Cleric', 5, 50, 60.0, 'SpellShield'),
(7, '7', 'Haste', 'Increases attack speed', 'Buff', 'Buff', 'Wizard', 12, 75, 120.0, 'SpellHaste'),
(8, '8', 'Weakness', 'Reduces target strength', 'Debuff', 'Debuff', 'Necromancer', 8, 60, 30.0, 'SpellWeakness');

INSERT INTO Spells (SpellDBIndex, Id, SpellName, SpellDesc, Type, Line, Classes, RequiredLevel, ManaCost, Cooldown, SpellRange, TargetDamage, DamageType, ResourceName)
VALUES
(9, '200', 'ARC - Lingering Inferno', 'Arcanist spell that creates a lingering inferno', 'Direct Damage', 'Fire', 'Arcanist', 15, 120, 6.0, 30.0, 250, 'Fire', 'SpellLingeringInferno');

-- Test data: Skills (3 original + 8 new = 11 skills)
INSERT INTO Skills (Id, SkillName, SkillDesc, TypeOfSkill, DuelistRequiredLevel, PaladinRequiredLevel, ArcanistRequiredLevel, DruidRequiredLevel, StormcallerRequiredLevel, Cooldown, EffectToApplyId, CastOnTargetId, RequireBow, RequireShield, DamageType, ResourceName)
VALUES
('1', 'Mining', 'Passive Skill: Allows mining of ore nodes', 'Innate', 1, 1, 1, 1, 1, NULL, NULL, NULL, 0, 0, '', 'SkillMining'),
('2', 'Fishing', 'Passive Skill: Allows fishing in waters', 'Innate', 1, 1, 1, 1, 1, NULL, NULL, NULL, 0, 0, '', 'SkillFishing'),
('3', 'Arcane Proficiency', 'Passive Skill: Your spells have a chance to land with a critical hit', 'Innate', 0, 0, 8, 0, 16, NULL, NULL, NULL, 0, 0, 'Physical', 'Arcane Proficiency'),
-- New test skills for comprehensive coverage
('100', 'Power Strike', 'A powerful melee attack', 'Attack', 5, 5, 0, 0, 0, 300.0, NULL, NULL, 0, 0, 'Physical', 'PowerStrike'),
('101', 'Weakening Strike', 'Strikes enemy and weakens them', 'Attack', 8, 8, 0, 0, 0, 600.0, 'Weakness (8)', NULL, 0, 0, 'Physical', 'WeakeningStrike'),
('102', 'Fire Strike', 'Strikes with fire damage', 'Attack', 6, 0, 6, 0, 0, 450.0, NULL, 'Fireball (1)', 0, 0, 'Fire', 'FireStrike'),
('103', 'Dual Effect Strike', 'Applies shield and casts haste', 'Attack', 10, 10, 0, 0, 0, 900.0, 'Shield (6)', 'Haste (7)', 0, 0, 'Physical', 'DualEffectStrike'),
('104', 'Stunning Blow', 'Stuns the enemy', 'Attack', 7, 7, 0, 0, 0, 720.0, 'Weakness (8)', 'Weakness (8)', 0, 0, 'Physical', 'StunningBlow'),
('105', 'Piercing Shot', 'A precise arrow attack', 'Ranged', 0, 0, 0, 0, 10, 360.0, NULL, NULL, 1, 0, 'Physical', 'PiercingShot'),
('106', 'Shield Slam', 'Slam enemy with shield', 'Attack', 0, 8, 0, 0, 0, 540.0, NULL, NULL, 0, 1, 'Physical', 'ShieldSlam'),
('107', 'Aimed Shot', 'A careful aimed shot. Requires a bow.', 'Ranged', 0, 0, 0, 0, 12, 240.0, NULL, NULL, 1, 0, 'Physical', 'AimedShot'),
('201', 'Lingering Inferno', 'Causes lingering fire damage over time', 'Attack', 12, 0, 0, 0, 0, 480.0, NULL, NULL, 0, 0, 'Fire', 'LingeringInfernoSkill');

-- Test data: Fishing (3 zones)
-- Add coordinates for waters
INSERT INTO Coordinates (Id, Scene, X, Y, Z, WaterId)
VALUES
(4, 'TestZone', 10.0, 0.0, 20.0, 1),
(5, 'TestZone', 30.0, 0.0, 40.0, 2),
(6, 'TestZone2', 50.0, 0.0, 60.0, 3);

INSERT INTO Waters (Id, CoordinateId, Width, Height, Depth)
VALUES
(1, 4, 10.0, 5.0, 3.0),
(2, 5, 15.0, 8.0, 4.0),
(3, 6, 20.0, 10.0, 5.0);

INSERT INTO WaterFishables (WaterId, Type, ItemName, DropChance)
VALUES
(1, 'Fish', 'Test Iron Ore', 0.5),  -- Iron ore (common)
(1, 'Fish', 'Test Gem', 0.1),  -- Gem (rare)
(2, 'Fish', 'Test Iron Ore', 0.4),
(2, 'Fish', 'Test Leather', 0.3),  -- Leather
(3, 'Fish', 'Test Gem', 0.2),
(3, 'Fish', 'Test Ancient Relic', 0.05);  -- Ancient relic (very rare)

-- Test data: Factions
INSERT INTO Factions (FactionDBIndex, FactionName, FactionDesc, DefaultValue, REFNAME, ResourceName)
VALUES
(1, 'Hostile', 'Hostile Faction', 0.0, 'HOSTILE', 'FactionHostile'),
(2, 'Friendly', 'Friendly Faction', 1000.0, 'FRIENDLY', 'FactionFriendly'),
(3, 'Neutral', 'Neutral Faction', 500.0, 'NEUTRAL', 'FactionNeutral');

-- Test data: Junction tables (migrated from CSV Classes columns)
-- SpellClasses: Map spells to classes based on Classes column in test data
INSERT INTO SpellClasses (SpellId, ClassName)
VALUES
(1, 'Wizard'),      -- Fireball
(2, 'Wizard'),      -- Ice Lance
(3, 'Wizard'),      -- Lightning Bolt
(4, 'Cleric'),      -- Heal
(5, 'Cleric'),      -- Greater Heal
(6, 'Cleric'),      -- Shield
(7, 'Wizard'),      -- Haste
(8, 'Necromancer'), -- Weakness
(200, 'Arcanist');   -- ARC - Lingering Inferno

-- Note: Items in test data don't have Classes values, so no ItemClasses entries needed

-- CharacterFactionModifiers: Test faction relationships for characters
INSERT INTO CharacterFactionModifiers (CharacterId, FactionREFNAME, ModifierValue)
VALUES
(1, 'Humans', -100),          -- Ancient Dragon hostile to Humans
(1, 'Elves', -50),            -- Ancient Dragon hostile to Elves
(2, 'Guards', 10),            -- Elite Guard friendly to Guards faction
(3, 'Humans', -20),           -- Goblin Scout hostile to Humans
(6, 'Merchants', 100),        -- Merchant Bob friendly to Merchants
(6, 'Humans', 50);            -- Merchant Bob friendly to Humans

-- CraftingRecipes: Test crafting materials for molds
INSERT INTO CraftingRecipes (RecipeItemId, MaterialItemId, MaterialSlot, MaterialQuantity)
VALUES
(14, '15', 0, 1),  -- Test Mold: Sword requires Test Iron Ore in slot 0
(14, '16', 1, 1);  -- Test Mold: Sword requires Test Leather in slot 1

-- CraftingRewards: Test crafting rewards for molds
INSERT INTO CraftingRewards (RecipeItemId, RewardItemId, RewardSlot, RewardQuantity)
VALUES
(14, '1', 0, 1);  -- Test Mold: Sword produces item ID 1 (Test Sword) in slot 0

-- CharacterVendorItems: Test vendor inventory
INSERT INTO CharacterVendorItems (CharacterId, ItemName)
VALUES
(6, 'Test Gem'),           -- Merchant Bob sells Test Gem
(6, 'Test Health Potion'); -- Merchant Bob sells Test Health Potion
