SELECT
    za.SceneName,
    za.ZoneName,
    ROUND(ww.X, 2) AS PositionX,
    ROUND(ww.Y, 2) AS PositionY,
    ROUND(ww.Z, 2) AS PositionZ,
    'https://erenshor-maps.wowmuch1.workers.dev/map?marker=' || ww.StableKey AS MapLink
FROM WishingWells ww
JOIN Zones za ON za.SceneName = ww.Scene
ORDER BY za.ZoneName;
