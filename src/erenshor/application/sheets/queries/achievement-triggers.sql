SELECT
    z.scene_name,
    z.zone_name,
    ROUND(at.x, 2) AS position_x,
    ROUND(at.y, 2) AS position_y,
    ROUND(at.z, 2) AS position_z,
    at.achievement_name,
    map_marker_url(at.stable_key) AS MapLink
FROM achievement_triggers at
JOIN zones z ON z.scene_name = at.scene
ORDER BY z.zone_name;
