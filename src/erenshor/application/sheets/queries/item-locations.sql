-- Each source's locations once. Acquisitions and uses name their source in location_source_key.
SELECT
    l.source_key,
    l.location_key,
    l.relation,
    l.scene,
    l.zone_stable_key,
    l.coordinate_stable_key,
    l.x,
    l.y,
    l.z,
    l.player_level_min,
    l.player_level_max,
    l.conditions,
    l.entry_zone_line_keys,
    l.source_copy_stable_key
FROM item_source_locations l
ORDER BY l.source_key, l.location_key;
