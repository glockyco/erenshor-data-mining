SELECT
    z.scene_name,
    z.zone_name,
    ROUND(sp.x, 2) AS position_x,
    ROUND(sp.y, 2) AS position_y,
    ROUND(sp.z, 2) AS position_z,
    sp.type,
    map_marker_url(sp.stable_key) AS MapLink
FROM secret_passages sp
JOIN zones z ON z.scene_name = sp.scene
WHERE sp.object_name NOT LIKE '%nav%' OR sp.object_name IS NULL
ORDER BY z.zone_name;
