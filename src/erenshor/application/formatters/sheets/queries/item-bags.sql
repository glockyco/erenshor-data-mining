SELECT
    ItemResourceName,
    ItemName,
    za.ZoneName,
    ROUND(co.X, 2) AS PositionX,
    ROUND(co.Y, 2) AS PositionY,
    ROUND(co.Z, 2) AS PositionZ
FROM ItemBags ib
JOIN Items i ON i.ResourceName = ib.ItemResourceName
JOIN Coordinates co ON co.Id = ib.CoordinateId
JOIN ZoneAnnounces za ON za.SceneName = co.Scene
ORDER by Scene, ItemName;
