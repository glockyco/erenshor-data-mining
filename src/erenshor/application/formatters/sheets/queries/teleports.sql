SELECT
    i.Id AS TeleportItemId,
    i.ItemName AS TeleportItemName,
    za.ZoneName,
    ROUND(co.X, 2) AS PositionX,
    ROUND(co.Y, 2) AS PositionY,
    ROUND(co.Z, 2) AS PositionZ
FROM Teleports t
JOIN Coordinates co ON co.TeleportId = t.Id
JOIN ZoneAnnounces za ON za.SceneName = co.Scene
JOIN Items i ON i.Id = t.TeleportItemId
ORDER BY i.ItemName;
