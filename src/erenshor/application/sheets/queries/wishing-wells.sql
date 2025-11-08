SELECT
    --Id,
    za.SceneName,
    za.ZoneName,
    ROUND(c.X, 2) AS PositionX,
    ROUND(c.Y, 2) AS PositionY,
    ROUND(c.Z, 2) AS PositionZ,
    'https://erenshor-maps.wowmuch1.workers.dev/' || za.SceneName || '?coordinateId=' || c.Id AS MapLink
FROM Coordinates c
JOIN Zones za ON za.SceneName = c.Scene
WHERE Category = 'WishingWell'
ORDER BY za.ZoneName;
