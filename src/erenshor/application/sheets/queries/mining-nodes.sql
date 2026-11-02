SELECT
    a.source_stable_key AS mining_node_stable_key,
    z.zone_name,
    l.x AS position_x,
    l.y AS position_y,
    l.z AS position_z,
    m.respawn_time,
    i.display_name,
    CASE WHEN a.probability_kind = 'exact' THEN a.probability_min END AS 'DropChance (%)',
    l.place_key,
    a.*
FROM item_sources a
LEFT JOIN mining_nodes m ON m.stable_key = a.source_stable_key
LEFT JOIN items i ON i.stable_key = a.item_stable_key
LEFT JOIN item_places l ON l.place_set_key = a.place_set_key
LEFT JOIN zones z ON z.stable_key = l.zone_stable_key
WHERE a.kind = 'mining'
ORDER BY z.zone_name, a.source_stable_key, a.probability_min DESC, a.source_key, l.place_key;
