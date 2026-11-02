SELECT
    a.*,
    i.display_name,
    z.zone_name,
    l.x AS position_x,
    l.y AS position_y,
    l.z AS position_z,
    CASE WHEN l.marker_stable_key IS NOT NULL THEN map_marker_url(l.marker_stable_key) END AS MapLink,
    l.place_key
FROM item_sources a
LEFT JOIN items i ON i.stable_key = a.item_stable_key
LEFT JOIN item_places l ON l.place_set_key = a.place_set_key
LEFT JOIN zones z ON z.stable_key = l.zone_stable_key
WHERE a.kind = 'item_bag'
ORDER BY l.scene, a.item_stable_key, a.source_key, l.place_key;
