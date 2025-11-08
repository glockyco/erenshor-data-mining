SELECT
    za.SceneName,
    za.ZoneName,
    ROUND(co.X, 2) AS PositionX,
    ROUND(co.Y, 2) AS PositionY,
    ROUND(co.Z, 2) AS PositionZ,
    th.IsPickableAlways,
    th.IsPickableGreater20,
    th.IsPickableGreater30,
    'https://erenshor-maps.wowmuch1.workers.dev/' || za.SceneName || '?coordinateId=' || co.Id AS MapLink
FROM TreasureHunting th
JOIN Coordinates co ON co.Scene = th.ZoneName AND co.Category = 'TreasureLoc'
JOIN Zones za ON za.SceneName = th.ZoneName
ORDER BY th.IsPickableAlways DESC, th.IsPickableGreater20 DESC, th.IsPickableGreater30;
