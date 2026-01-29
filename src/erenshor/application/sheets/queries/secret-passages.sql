SELECT
    za.SceneName,
    za.ZoneName,
    ROUND(sp.X, 2) AS PositionX,
    ROUND(sp.Y, 2) AS PositionY,
    ROUND(sp.Z, 2) AS PositionZ,
    sp.Type,
    'https://erenshor-maps.wowmuch1.workers.dev/map?marker=' || sp.StableKey AS MapLink
FROM SecretPassages sp
JOIN Zones za ON za.SceneName = sp.Scene
WHERE sp.ObjectName NOT LIKE '%nav%' OR sp.ObjectName IS NULL
ORDER BY za.ZoneName;
