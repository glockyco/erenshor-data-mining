SELECT * FROM
(
    SELECT
        w.Id AS WaterId,
        za.ZoneName,
        ROUND(c.X, 2) AS PositionX,
        ROUND(c.Y, 2) AS PositionY,
        ROUND(c.Z, 2) AS PositionZ,
        wf.ItemName,
        MAX(CASE WHEN wf.Type = 'DayFishable' THEN ROUND(wf.DropChance, 2) END) AS 'DayFishableChance (%)',
        MAX(CASE WHEN wf.Type = 'NightFishable' THEN ROUND(wf.DropChance, 2) END) AS 'NightFishableChance (%)'
    FROM Waters w
    LEFT JOIN WaterFishables wf ON w.Id = wf.WaterId
    JOIN Coordinates c ON c.WaterId = w.Id
    JOIN ZoneAnnounces za ON za.SceneName = c.Scene
    GROUP BY w.Id, za.ZoneName, c.X, c.Y, c.Z, wf.ItemName
)
ORDER BY WaterId, ZoneName, "DayFishableChance (%)" DESC, "NightFishableChance (%)" DESC, ItemName;
