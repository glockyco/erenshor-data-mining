SELECT
    m.StableKey AS MiningNodeStableKey,
    za.ZoneName,
    ROUND(m.X, 2) AS PositionX,
    ROUND(m.Y, 2) AS PositionY,
    ROUND(m.Z, 2) AS PositionZ,
    m.RespawnTime,
    i.ItemName,
    ROUND(mi.DropChance, 2) AS 'DropChance (%)'
FROM MiningNodes m
JOIN MiningNodeItems mi ON m.StableKey = mi.MiningNodeStableKey
JOIN Items i ON i.StableKey = mi.ItemStableKey
JOIN Zones za ON za.SceneName = m.Scene
ORDER BY za.ZoneName, MiningNodeStableKey, mi.DropChance DESC;
