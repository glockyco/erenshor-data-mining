SELECT
    i.StableKey AS TeleportItemStableKey,
    i.ItemName AS TeleportItemName,
    za.ZoneName,
    ROUND(co.X, 2) AS PositionX,
    ROUND(co.Y, 2) AS PositionY,
    ROUND(co.Z, 2) AS PositionZ,
    'https://erenshor-maps.wowmuch1.workers.dev/' || za.SceneName || '?coordinateId=' || co.Id AS MapLink
FROM Teleports t
JOIN Coordinates co ON co.TeleportId = t.Id
JOIN Zones za ON za.SceneName = co.Scene
JOIN Items i ON i.StableKey = t.TeleportItemStableKey
ORDER BY i.ItemName;
