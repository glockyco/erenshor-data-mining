SELECT
    Id,
    SceneName,
    ZoneName,
    PositionX,
    PositionY,
    PositionZ,
    IsDirectlyPlaced,
    IsEnabled,
    CharacterStableKey,
    NPCName,
    SpawnChancePercent,
    IsCommon,
    IsRare,
    IsUnique,
    LevelMod,
    SpawnDelay1InGrp,
    SpawnDelay2InGrp,
    SpawnDelay3InGrp,
    SpawnDelay4InGrp,
    Staggerable,
    StaggerMod,
    IsNightSpawn,
    PatrolPoints,
    LoopPatrol,
    RandomWanderRange,
    SpawnUponQuestCompleteStableKey,
    StopIfQuestCompleteStableKeys,
    MapLink
FROM (
    -- Part 1: Spawn Points
    SELECT
        sp.Id,
        za.SceneName,
        za.ZoneName,
        ROUND(co.X, 2) AS PositionX,
        ROUND(co.Y, 2) AS PositionY,
        ROUND(co.Z, 2) AS PositionZ,
        sp.IsEnabled,
        c.StableKey AS CharacterStableKey,
        c.NPCName,
        ROUND(spc.SpawnChance, 2) AS SpawnChancePercent,
        spc.IsCommon,
        spc.IsRare,
        c.IsUnique,
        sp.LevelMod,
        sp.SpawnDelay1 AS SpawnDelay1InGrp,
        ROUND(sp.SpawnDelay2, 2) AS SpawnDelay2InGrp,
        ROUND(sp.SpawnDelay3, 2) AS SpawnDelay3InGrp,
        ROUND(sp.SpawnDelay4, 2) AS SpawnDelay4InGrp,
        sp.Staggerable,
        sp.StaggerMod,
        sp.NightSpawn AS IsNightSpawn,
        sp.PatrolPoints,
        sp.LoopPatrol,
        sp.RandomWanderRange,
        sp.SpawnUponQuestCompleteStableKey,
        (SELECT GROUP_CONCAT(QuestStableKey, ', ')
         FROM SpawnPointStopQuests spsq
         WHERE spsq.SpawnPointId = sp.Id) AS StopIfQuestCompleteStableKeys,
        'https://erenshor-maps.wowmuch1.workers.dev/' || za.SceneName || '?coordinateId=' || co.Id AS MapLink,
        0 AS IsDirectlyPlaced
    FROM
        main.SpawnPoints sp
        JOIN SpawnPointCharacters spc ON sp.Id = spc.SpawnPointId
        JOIN Characters c ON spc.CharacterStableKey = c.StableKey
        JOIN Coordinates co ON co.SpawnPointId = sp.Id
        JOIN Zones za ON za.SceneName = co.Scene

    UNION ALL

    -- Part 2: Directly Placed Characters
    SELECT
        NULL AS Id,
        za.SceneName,
        za.ZoneName,
        ROUND(co.X, 2) AS PositionX,
        ROUND(co.Y, 2) AS PositionY,
        ROUND(co.Z, 2) AS PositionZ,
        c.IsEnabled,
        c.StableKey AS CharacterStableKey,
        c.NPCName,
        100.0 AS SpawnChancePercent,
        1 AS IsCommon,
        0 AS IsRare,
        c.IsUnique,
        NULL AS LevelMod,
        NULL AS SpawnDelay1InGrp,
        NULL AS SpawnDelay2InGrp,
        NULL AS SpawnDelay3InGrp,
        NULL AS SpawnDelay4InGrp,
        NULL AS Staggerable,
        NULL AS StaggerMod,
        0 AS IsNightSpawn,
        NULL AS PatrolPoints,
        NULL AS LoopPatrol,
        NULL AS RandomWanderRange,
        NULL AS SpawnUponQuestCompleteStableKey,
        NULL AS StopIfQuestCompleteStableKeys,
        'https://erenshor-maps.wowmuch1.workers.dev/' || za.SceneName || '?coordinateId=' || co.Id AS MapLink,
        1 AS IsDirectlyPlaced
    FROM Characters c
    JOIN Coordinates co ON co.CharacterStableKey = c.StableKey
    JOIN Zones za ON za.SceneName = co.Scene
    WHERE NOT c.IsPrefab
)
ORDER BY
    SceneName,
    IsDirectlyPlaced,
    SpawnChancePercent DESC,
    NPCName;
