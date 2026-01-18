SELECT * FROM
(
    SELECT
        w.StableKey AS WaterStableKey,
        za.ZoneName,
        ROUND(w.X, 2) AS PositionX,
        ROUND(w.Y, 2) AS PositionY,
        ROUND(w.Z, 2) AS PositionZ,
        i.ItemName,
        MAX(CASE WHEN wf.Type = 'DayFishable' THEN ROUND(wf.DropChance, 2) END) AS 'DayFishableChance (%)',
        MAX(CASE WHEN wf.Type = 'NightFishable' THEN ROUND(wf.DropChance, 2) END) AS 'NightFishableChance (%)'
    FROM Waters w
    LEFT JOIN WaterFishables wf ON w.StableKey = wf.WaterStableKey
    LEFT JOIN Items i ON i.StableKey = wf.ItemStableKey
    JOIN Zones za ON za.SceneName = w.Scene
    GROUP BY w.StableKey, za.ZoneName, w.X, w.Y, w.Z, i.ItemName
)
ORDER BY WaterStableKey, ZoneName, "DayFishableChance (%)" DESC, "NightFishableChance (%)" DESC, ItemName;
