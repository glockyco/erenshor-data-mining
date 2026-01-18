SELECT
    i.StableKey AS TeleportItemStableKey,
    i.ItemName AS TeleportItemName,
    za.ZoneName,
    ROUND(t.X, 2) AS PositionX,
    ROUND(t.Y, 2) AS PositionY,
    ROUND(t.Z, 2) AS PositionZ,
    'https://erenshor-maps.wowmuch1.workers.dev/map?marker=' || t.StableKey AS MapLink
FROM Teleports t
JOIN Zones za ON za.SceneName = t.Scene
JOIN Items i ON i.StableKey = t.TeleportItemStableKey
ORDER BY i.ItemName;
