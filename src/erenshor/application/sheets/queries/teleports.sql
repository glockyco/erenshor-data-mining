SELECT
    i.stable_key AS teleport_item_stable_key,
    i.display_name AS teleport_item_name,
    z.zone_name,
    ROUND(t.x, 2) AS position_x,
    ROUND(t.y, 2) AS position_y,
    ROUND(t.z, 2) AS position_z,
    'https://erenshor-maps.wowmuch1.workers.dev/map?sel=marker:' || t.stable_key AS map_link
FROM teleports t
JOIN zones z ON z.scene_name = t.scene
JOIN items i ON i.stable_key = t.teleport_item_stable_key
ORDER BY i.display_name;
