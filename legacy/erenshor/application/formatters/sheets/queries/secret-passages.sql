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
