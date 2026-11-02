-- Day, night and global replacement routes remain separate public sources.
SELECT
    a.source_stable_key AS water_stable_key,
    z.zone_name,
    l.x AS position_x,
    l.y AS position_y,
    l.z AS position_z,
    i.display_name,
    CASE WHEN a.probability_kind = 'exact' THEN a.probability_min END AS 'Chance (%)',
    l.place_key,
    a.*
FROM item_sources a
LEFT JOIN items i ON i.stable_key = a.item_stable_key
LEFT JOIN item_places l ON l.place_set_key = a.place_set_key
LEFT JOIN zones z ON z.stable_key = l.zone_stable_key
WHERE a.kind = 'fishing'
ORDER BY a.source_stable_key, a.item_stable_key, a.source_key, l.place_key;
