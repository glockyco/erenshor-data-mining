SELECT
    'acquisition' AS fact_type,
    l.owner_key,
    l.location_key,
    l.relation,
    l.scene,
    l.zone_stable_key,
    l.placement_key,
    l.coordinate_stable_key,
    l.x,
    l.y,
    l.z,
    l.gate_scope,
    l.player_level_min,
    l.player_level_max,
    l.conditions,
    l.entry_zone_line_keys,
    l.source_copy_stable_key
FROM item_acquisition_locations l
UNION ALL
SELECT
    'use' AS fact_type,
    l.owner_key,
    l.location_key,
    l.relation,
    l.scene,
    l.zone_stable_key,
    l.placement_key,
    l.coordinate_stable_key,
    l.x,
    l.y,
    l.z,
    l.gate_scope,
    l.player_level_min,
    l.player_level_max,
    l.conditions,
    l.entry_zone_line_keys,
    l.source_copy_stable_key
FROM item_use_locations l
ORDER BY fact_type, owner_key, location_key;
