SELECT
    z.scene_name,
    z.zone_name,
    ROUND(tl.x, 2) AS position_x,
    ROUND(tl.y, 2) AS position_y,
    ROUND(tl.z, 2) AS position_z,
    th.is_pickable_always,
    th.is_pickable_greater_20,
    th.is_pickable_greater_30,
    map_marker_url(tl.stable_key) AS MapLink
FROM treasure_hunting th
JOIN treasure_locations tl ON tl.scene = th.zone_name
JOIN zones z ON z.scene_name = th.zone_name
ORDER BY th.is_pickable_always DESC, th.is_pickable_greater_20 DESC, th.is_pickable_greater_30;
