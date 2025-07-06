-- drop-chances
WITH
    drops AS (
        SELECT
            c.NPCName AS 'NPC Name',
            i.ItemName AS 'Item Name',
            ROUND(ld.DropProbability, 2) AS 'Drop Chance Per Kill (%)',
            ROUND(ld.ExpectedPerKill, 4) AS 'Expected Per Kill',
            ld.DropCountDistribution,
            ld.IsGuaranteed,
            ld.IsUnique,
            ld.IsVisible,
            c.ObjectName AS 'NPC Prefab Name',
            i.ResourceName AS 'Item Resource Name'
        FROM Characters c
        LEFT JOIN LootDrops ld ON c.Guid = ld.CharacterPrefabGuid
        INNER JOIN Items i ON ld.ItemId = i.Id
        ORDER BY c.NPCName, c.Guid
    )
SELECT * FROM drops
ORDER BY "NPC Name", "NPC Prefab Name", "Drop Chance Per Kill (%)" DESC;

-- items
SELECT
    ItemDBIndex,
    Id,
    ItemName,
    Lore,
    RequiredSlot,
    ThisWeaponType,
    Classes,
    Quality,
    ItemLevel,
    HP,
    AC,
    Mana,
    Str,
    End,
    Dex,
    Agi,
    Int,
    Wis,
    Cha,
    Res,
    MR,
    ER,
    PR,
    VR,
    WeaponDmg,
    WeaponDly,
    Shield,
    WeaponProcChance,
    WeaponProcOnHit,
    IsWand,
    WandRange,
    WandProcChance,
    WandEffect,
    ItemEffectOnClick,
    ItemSkillUse,
    TeachSpell,
    TeachSkill,
    Aura,
    WornEffect,
    SpellCastTime,
    AssignQuestOnRead,
    CompleteOnRead,
    Template,
    TemplateIngredientIds,
    TemplateRewardIds,
    ItemValue,
    SellValue,
    Stackable,
    Disposable,
    "Unique",
    Relic,
    BookTitle,
    Mining,
    FuelSource,
    FuelLevel,
    SimPlayersCantGet,
    AttackSoundName,
    ItemIconName,
    EquipmentToActivate,
    HideHairWhenEquipped,
    HideHeadWhenEquipped,
    ResourceName,
    WikiString
FROM items i
JOIN ItemStats s ON s.ItemId = i.Id;

-- characters
SELECT
    --Id,
    --CoordinateId,
   Guid,
   ObjectName,
   NPCName,
   MyWorldFaction,
   MyFaction,
   AggroRange,
   AttackRange,
   AggressiveTowards,
   Allies,
   IsNPC,
   IsSimPlayer,
   IsVendor,
   IsMiningNode,
   HasDialog,
   HasStats,
   HasModifyFaction,
   IsEnabled,
   Invulnerable,
   ShoutOnDeath,
   QuestCompleteOnDeath,
   DestroyOnDeath,
   Level,
   BaseXpMin,
   BaseXpMax,
   BossXpMultiplier,
   BaseHP,
   BaseAC,
   BaseMana,
   BaseStr,
   BaseEnd,
   BaseDex,
   BaseAgi,
   BaseInt,
   BaseWis,
   BaseCha,
   BaseRes,
   BaseMR,
   BaseER,
   BasePR,
   BaseVR,
   RunSpeed,
   BaseLifeSteal,
   BaseMHAtkDelay,
   BaseOHAtkDelay,
   AttackSkills,
   AttackSpells,
   BuffSpells,
   HealSpells,
   GroupHealSpells,
   CCSpells,
   TauntSpells,
   PetSpell,
   ProcOnHit,
   ProcOnHitChance,
   ModifyFactions,
   VendorDesc,
   ItemsForSale
FROM Characters;

-- character-dialogs
SELECT 
    CharacterId,
    NPCName,
    DialogIndex,
    DialogText,
    Keywords,
    GiveItemName,
    AssignQuestDBName,
    CompleteQuestDBName,
    RepeatingQuestDialog,
    KillSelfOnSay,
    RequiredQuestDBName,
    SpawnName
FROM CharacterDialogs cd
JOIN Characters c ON c.Id = cd.CharacterId
ORDER BY NPCName, CharacterId, DialogIndex;

-- classes
SELECT * FROM classes;

-- spells
SELECT * FROM spells;

-- skills
SELECT * FROM skills;

-- ascensions
SELECT * FROM ascensions;

-- quests
SELECT * FROM quests;

-- books
SELECT * FROM Books;

-- factions
SELECT * FROM factions;

-- zones
SELECT
    za.SceneName AS 'Zone:SceneName',
    za.ZoneName AS 'Zone:ZoneName',
    za.IsDungeon AS 'Zone:IsDungeon',
    za.Achievement AS 'Zone:Achievement',
    za.CompleteQuestOnEnter AS 'Zone:CompleteQuestOnEnter',
    za.CompleteSecondQuestOnEnter AS 'Zone:CompleteSecondQuestOnEnter',
    za.AssignQuestOnEnter AS 'Zone:AssignQuestOnEnter',
    zae.AtlasIndex AS 'Atlas:Index',
    zae.Id AS 'Atlas:Id',
    zae.ZoneName AS 'Atlas:ZoneName',
    zae.LevelRangeLow AS 'Atlas:LevelRangeLow',
    zae.LevelRangeHigh AS 'Atlas:LevelRangeHigh',
    zae.Dungeon AS 'Atlas:Dungeon',
    zae.NeighboringZones AS 'Atlas:NeighboringZones',
    zae.ResourceName AS 'Atlas:ResourceName'
FROM ZoneAnnounces za
LEFT JOIN ZoneAtlasEntries zae ON
    zae.ZoneName = za.SceneName
    OR (za.SceneName = 'PrielPlateau' AND zae.ZoneName = 'PrielianPlateau')
    OR (za.SceneName LIKE 'Undercity' AND zae.ResourceName = 'Undercity')
UNION
SELECT za.*, zae.*
FROM ZoneAtlasEntries zae
LEFT JOIN ZoneAnnounces za ON
    zae.ZoneName = za.SceneName
    OR (za.SceneName = 'PrielPlateau' AND zae.ZoneName = 'PrielianPlateau')
    OR (za.SceneName LIKE 'Undercity' AND zae.ResourceName = 'Undercity');

-- teleports
SELECT
    i.Id AS TeleportItemId,
    i.ItemName AS TeleportItemName,
    za.ZoneName,
    ROUND(co.X, 2) AS PositionX,
    ROUND(co.Y, 2) AS PositionY,
    ROUND(co.Z, 2) AS PositionZ
FROM Teleports t
JOIN Coordinates co ON co.TeleportId = t.Id
JOIN ZoneAnnounces za ON za.SceneName = co.Scene
JOIN Items i ON i.Id = t.TeleportItemId
ORDER BY i.ItemName;

-- treasure-locations
SELECT
    za.ZoneName,
    ROUND(co.X, 2) AS PositionX,
    ROUND(co.Y, 2) AS PositionY,
    ROUND(co.Z, 2) AS PositionZ,
    th.IsPickableAlways,
    th.IsPickableGreater20,
    th.IsPickableGreater30
FROM TreasureHunting th
JOIN Coordinates co ON co.Scene = th.ZoneName AND co.Category = 'TreasureLoc'
JOIN ZoneAnnounces za ON za.SceneName = th.ZoneName
ORDER BY th.IsPickableAlways DESC, th.IsPickableGreater20 DESC, th.IsPickableGreater30;

-- wishing-wells
SELECT
    --Id,
    za.SceneName,
    za.ZoneName,
    ROUND(c.X, 2) AS PositionX,
    ROUND(c.Y, 2) AS PositionY,
    ROUND(c.Z, 2) AS PositionZ,
    'https://erenshor-maps.wowmuch1.workers.dev/' || za.SceneName || '?coordinateId=' || c.Id AS MapLink
FROM Coordinates c
JOIN ZoneAnnounces za ON za.SceneName = c.Scene
WHERE Category = 'WishingWell'
ORDER BY za.ZoneName;

-- fishing
SELECT * FROM
(
    SELECT
        w.Id AS WaterId,
        za.ZoneName,
        ROUND(c.X, 2) AS PositionX,
        ROUND(c.Y, 2) AS PositionY,
        ROUND(c.Z, 2) AS PositionZ,
        wf.ItemName,
        MAX(CASE WHEN wf.Type = 'DayFishable' THEN ROUND(wf.DropChance, 2) END) AS 'DayFishableChance (%)',
        MAX(CASE WHEN wf.Type = 'NightFishable' THEN ROUND(wf.DropChance, 2) END) AS 'NightFishableChance (%)'
    FROM Waters w
    LEFT JOIN WaterFishables wf ON w.Id = wf.WaterId
    JOIN Coordinates c ON c.WaterId = w.Id
    JOIN ZoneAnnounces za ON za.SceneName = c.Scene
    GROUP BY w.Id, za.ZoneName, c.X, c.Y, c.Z, wf.ItemName
)
ORDER BY WaterId, ZoneName, "DayFishableChance (%)" DESC, "NightFishableChance (%)" DESC, ItemName;

-- mining-nodes
SELECT
    m.Id AS MiningNodeId,
    za.ZoneName,
    ROUND(c.X, 2) AS PositionX,
    ROUND(c.Y, 2) AS PositionY,
    ROUND(c.Z, 2) AS PositionZ,
    m.RespawnTime,
    mi.ItemName,
    ROUND(mi.DropChance, 2) AS 'DropChance (%)'
FROM MiningNodes m
JOIN MiningNodeItems mi ON m.Id = mi.MiningNodeId
JOIN Coordinates c ON c.MiningNodeId = m.Id
JOIN ZoneAnnounces za ON za.SceneName = c.Scene
ORDER BY za.ZoneName, m.Id, mi.DropChance DESC;

-- spawn-points
SELECT
    sp.Id,
    co.Scene,
    ROUND(co.X, 2) AS PositionX,
    ROUND(co.Y, 2) AS PositionY,
    ROUND(co.Z, 2) AS PositionZ,
    sp.IsEnabled,
    c.NPCName,
    c.ObjectName,
    ROUND(spc.SpawnChance, 2) AS 'Spawn Chance (%)',
    spc.IsCommon,
    spc.IsRare,
    c.IsUnique,
    
    sp.LevelMod,
    sp.SpawnDelay1,
    sp.Staggerable,
    sp.StaggerMod,
    sp.NightSpawn AS 'IsNightSpawn',
    sp.PatrolPoints,
    sp.LoopPatrol,
    sp.RandomWanderRange,
    sp.SpawnUponQuestCompleteDBName,
    sp.StopIfQuestCompleteDBNames
FROM
    main.SpawnPoints sp
    JOIN SpawnPointCharacters spc ON sp.Id = spc.SpawnPointId
    JOIN Characters c ON spc.CharacterGuid = c.Guid
    JOIN Coordinates co ON co.SpawnPointId = sp.Id
ORDER BY
    sp.Id,
    spc.SpawnChance DESC,
    c.NPCName;

-- secret-passages
SELECT
    --Id,
    za.SceneName,
    za.ZoneName,
    ROUND(c.X, 2) AS PositionX,
    ROUND(c.Y, 2) AS PositionY,
    ROUND(c.Z, 2) AS PositionZ,
    --sp.ObjectName,
    sp.Type,
    'https://erenshor-maps.wowmuch1.workers.dev/' || za.SceneName || '?coordinateId=' || c.Id AS MapLink
FROM SecretPassages sp
JOIN Coordinates c ON c.SecretPassageId = sp.Id
JOIN ZoneAnnounces za ON za.SceneName = c.Scene
ORDER BY za.ZoneName;

-- achievement-triggers
SELECT
    --Id,
    za.ZoneName,
    ROUND(c.X, 2) AS PositionX,
    ROUND(c.Y, 2) AS PositionY,
    ROUND(c.Z, 2) AS PositionZ,
    AchievementName
FROM AchievementTriggers at
JOIN Coordinates c ON c.AchievementTriggerId = at.Id
JOIN ZoneAnnounces za ON za.SceneName = c.Scene
ORDER BY za.ZoneName;

-- wiki-comparison
SELECT
    WikiUrl,
    Type,
    Name,
    Tier,
    CASE
        WHEN CurrentWikiString = '' THEN 'Object is missing from the wiki.'
        ELSE ComparisonResult
        END AS ComparisonResult,
    CurrentWikiString,
    SuggestedWikiString,
    ComparisonTimestamp
FROM WikiComparison
ORDER BY Type, Name, Tier;
