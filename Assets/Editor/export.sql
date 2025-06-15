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
        INNER JOIN Items i ON ld.ItemId = i.BaseItemId
        WHERE i.Quality = 'Normal'
        ORDER BY c.NPCName, c.Guid
    )
SELECT * FROM drops
ORDER BY "NPC Name", "NPC Prefab Name", "Drop Chance Per Kill (%)" DESC;

-- items
SELECT * FROM items;

-- characters
SELECT * FROM Characters;

-- classes
SELECT * FROM classes;

-- spells
SELECT * FROM spells;

-- skills
SELECT * FROM skills;

-- ascensions
SELECT * FROM ascensions;

-- npc-dialogs
SELECT * FROM NPCDialogs;

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

-- treasure-locations
SELECT th.*, tl.Id AS Location
FROM TreasureHunting th
JOIN TreasureLocs tl ON th.ZoneName = tl.SceneName
ORDER BY th.IsPickableAlways DESC, th.IsPickableGreater20 DESC, th.IsPickableGreater30;

-- fishing
SELECT
    w.SceneName,
    w."Index" AS WaterIndex,
    wf.Type,
    wf."Index" AS FishableIndex,
    wf.ItemId,
    wf.ItemName,
    ROUND(wf.DropChance, 2) AS 'DropChance (%)',
    ROUND(wf.TotalDropChance, 2) AS 'TotalDropChance (%)'
FROM Waters w LEFT JOIN WaterFishables wf ON w.Id = wf.WaterId;

-- mining-nodes
SELECT
    m.Id MiningNodeId,
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
    spc.SpawnType,
    c.NPCName,
    c.ObjectName,
    ROUND(spc.SpawnChance, 2) AS 'Spawn Chance (%)',
    ROUND(spc.TotalSpawnChance, 2) AS 'Total Spawn Chance (%)',
    
    sp.LevelMod,
    sp.SpawnDelay,
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
    JOIN Characters c ON spc.CharacterPrefabGuid = c.Guid
    JOIN Coordinates co ON co.SpawnPointId = sp.Id
ORDER BY
    sp.Id,
    spc.SpawnType,
    spc.SpawnListIndex;

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
