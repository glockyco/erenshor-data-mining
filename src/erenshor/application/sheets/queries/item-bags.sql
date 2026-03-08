SELECT
    i.stable_key AS item_stable_key,
    i.display_name,
    z.zone_name,
    ROUND(ib.x, 2) AS position_x,
    ROUND(ib.y, 2) AS position_y,
    ROUND(ib.z, 2) AS position_z,
    'https://erenshor-maps.wowmuch1.workers.dev/map?sel=marker:' || ib.stable_key AS map_link
FROM item_bags ib
JOIN items i ON i.stable_key = ib.item_stable_key
JOIN zones z ON z.scene_name = ib.scene
ORDER BY ib.scene, i.display_name;
