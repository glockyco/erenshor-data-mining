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
    --c.ObjectName,
    ROUND(spc.SpawnChance, 2) AS 'Spawn Chance (%)',
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
    sp.NightSpawn AS 'IsNightSpawn',
    sp.PatrolPoints,
    sp.LoopPatrol,
    sp.RandomWanderRange,
    sp.SpawnUponQuestCompleteStableKey,
    (SELECT GROUP_CONCAT(QuestStableKey, ', ')
     FROM SpawnPointStopQuests spsq
     WHERE spsq.SpawnPointId = sp.Id) AS StopIfQuestCompleteStableKeys,
    'https://erenshor-maps.wowmuch1.workers.dev/' || za.SceneName || '?coordinateId=' || co.Id AS MapLink
FROM
    main.SpawnPoints sp
    JOIN SpawnPointCharacters spc ON sp.Id = spc.SpawnPointId
    JOIN Characters c ON spc.CharacterStableKey = c.StableKey
    JOIN Coordinates co ON co.SpawnPointId = sp.Id
    JOIN Zones za ON za.SceneName = co.Scene
ORDER BY
    sp.Id,
    spc.SpawnChance DESC,
    c.NPCName;
