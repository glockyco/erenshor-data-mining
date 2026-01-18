SELECT
    za.SceneName,
    za.ZoneName,
    ROUND(at.X, 2) AS PositionX,
    ROUND(at.Y, 2) AS PositionY,
    ROUND(at.Z, 2) AS PositionZ,
    AchievementName,
    'https://erenshor-maps.wowmuch1.workers.dev/map?marker=' || at.StableKey AS MapLink
FROM AchievementTriggers at
JOIN Zones za ON za.SceneName = at.Scene
ORDER BY za.ZoneName;
