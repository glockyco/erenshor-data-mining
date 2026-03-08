SELECT * FROM
(
    SELECT
        w.stable_key AS water_stable_key,
        z.zone_name,
        ROUND(w.x, 2) AS position_x,
        ROUND(w.y, 2) AS position_y,
        ROUND(w.z, 2) AS position_z,
        i.display_name,
        MAX(CASE WHEN wf.type = 'DayFishable' THEN ROUND(wf.drop_chance, 2) END) AS 'DayFishableChance (%)',
        MAX(CASE WHEN wf.type = 'NightFishable' THEN ROUND(wf.drop_chance, 2) END) AS 'NightFishableChance (%)'
    FROM waters w
    LEFT JOIN water_fishables wf ON w.stable_key = wf.water_stable_key
    LEFT JOIN items i ON i.stable_key = wf.item_stable_key
    JOIN zones z ON z.scene_name = w.scene
    GROUP BY w.stable_key, z.zone_name, w.x, w.y, w.z, i.display_name
)
ORDER BY water_stable_key, zone_name, "DayFishableChance (%)" DESC, "NightFishableChance (%)" DESC, display_name;
