SELECT
    --Id,
    za.SceneName,
    za.ZoneName,
    ROUND(c.X, 2) AS PositionX,
    ROUND(c.Y, 2) AS PositionY,
    ROUND(c.Z, 2) AS PositionZ,
    AchievementName,
    'https://erenshor-maps.wowmuch1.workers.dev/' || za.SceneName || '?coordinateId=' || c.Id AS MapLink
FROM AchievementTriggers at
JOIN Coordinates c ON c.AchievementTriggerId = at.Id
JOIN Zones za ON za.SceneName = c.Scene
ORDER BY za.ZoneName;
