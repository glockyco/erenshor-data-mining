SELECT
    i.StableKey AS ItemStableKey,
    i.ItemName,
    za.ZoneName,
    ROUND(ib.X, 2) AS PositionX,
    ROUND(ib.Y, 2) AS PositionY,
    ROUND(ib.Z, 2) AS PositionZ,
    'https://erenshor-maps.wowmuch1.workers.dev/map?marker=' || ib.StableKey AS MapLink
FROM ItemBags ib
JOIN Items i ON i.StableKey = ib.ItemStableKey
JOIN Zones za ON za.SceneName = ib.Scene
ORDER by ib.Scene, ItemName;
