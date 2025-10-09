SELECT
    za.ZoneName,
    ROUND(co.X, 2) AS PositionX,
    ROUND(co.Y, 2) AS PositionY,
    ROUND(co.Z, 2) AS PositionZ,
    'https://erenshor-maps.wowmuch1.workers.dev/' || za.SceneName || '?coordinateId=' || co.Id AS MapLink
FROM Coordinates co
JOIN ZoneAnnounces za ON za.SceneName = co.Scene
WHERE co.Category = 'Teleport';
