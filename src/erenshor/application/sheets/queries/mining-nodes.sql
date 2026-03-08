SELECT
    m.stable_key AS mining_node_stable_key,
    z.zone_name,
    ROUND(m.x, 2) AS position_x,
    ROUND(m.y, 2) AS position_y,
    ROUND(m.z, 2) AS position_z,
    m.respawn_time,
    i.display_name,
    ROUND(mi.drop_chance, 2) AS 'DropChance (%)'
FROM mining_nodes m
JOIN mining_node_items mi ON m.stable_key = mi.mining_node_stable_key
JOIN items i ON i.stable_key = mi.item_stable_key
JOIN zones z ON z.scene_name = m.scene
ORDER BY z.zone_name, m.stable_key, mi.drop_chance DESC;
