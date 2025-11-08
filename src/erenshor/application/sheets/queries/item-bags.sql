SELECT
    i.StableKey AS ItemStableKey,
    i.ItemName,
    za.ZoneName,
    ROUND(co.X, 2) AS PositionX,
    ROUND(co.Y, 2) AS PositionY,
    ROUND(co.Z, 2) AS PositionZ
FROM ItemBags ib
JOIN Items i ON i.StableKey = ib.ItemStableKey
JOIN Coordinates co ON co.Id = ib.CoordinateId
JOIN Zones za ON za.SceneName = co.Scene
ORDER by Scene, ItemName;
