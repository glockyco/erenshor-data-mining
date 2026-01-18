SELECT
    sp.StableKey AS Id,
    za.SceneName,
    za.ZoneName,
    ROUND(sp.X, 2) AS PositionX,
    ROUND(sp.Y, 2) AS PositionY,
    ROUND(sp.Z, 2) AS PositionZ,
    sp.IsDirectlyPlaced,
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
     WHERE spsq.SpawnPointStableKey = sp.StableKey) AS StopIfQuestCompleteStableKeys,
    'https://erenshor-maps.wowmuch1.workers.dev/map?marker=' || sp.StableKey AS MapLink
FROM
    main.SpawnPoints sp
    JOIN SpawnPointCharacters spc ON spc.SpawnPointStableKey = sp.StableKey
    JOIN Characters c ON spc.CharacterStableKey = c.StableKey
    JOIN Zones za ON za.SceneName = sp.Scene
ORDER BY
    SceneName,
    IsDirectlyPlaced,
    SpawnChancePercent DESC,
    NPCName;
