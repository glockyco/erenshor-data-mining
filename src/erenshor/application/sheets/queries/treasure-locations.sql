SELECT
    za.SceneName,
    za.ZoneName,
    ROUND(tl.X, 2) AS PositionX,
    ROUND(tl.Y, 2) AS PositionY,
    ROUND(tl.Z, 2) AS PositionZ,
    th.IsPickableAlways,
    th.IsPickableGreater20,
    th.IsPickableGreater30,
    'https://erenshor-maps.wowmuch1.workers.dev/map?marker=' || tl.StableKey AS MapLink
FROM TreasureHunting th
JOIN TreasureLocations tl ON tl.Scene = th.ZoneName
JOIN Zones za ON za.SceneName = th.ZoneName
ORDER BY th.IsPickableAlways DESC, th.IsPickableGreater20 DESC, th.IsPickableGreater30;
