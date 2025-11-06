SELECT
    m.Id AS MiningNodeId,
    za.ZoneName,
    ROUND(c.X, 2) AS PositionX,
    ROUND(c.Y, 2) AS PositionY,
    ROUND(c.Z, 2) AS PositionZ,
    m.RespawnTime,
    i.ItemName,
    ROUND(mi.DropChance, 2) AS 'DropChance (%)'
FROM MiningNodes m
JOIN MiningNodeItems mi ON m.Id = mi.MiningNodeId
JOIN Items i ON i.StableKey = mi.ItemStableKey
JOIN Coordinates c ON c.MiningNodeId = m.Id
JOIN Zones za ON za.SceneName = c.Scene
ORDER BY za.ZoneName, m.Id, mi.DropChance DESC;
