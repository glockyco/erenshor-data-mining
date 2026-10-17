-- Day, night and bonus routes remain separate acquisitions with typed conditions.
SELECT
    a.source_stable_key AS water_stable_key,
    z.zone_name,
    l.x AS position_x,
    l.y AS position_y,
    l.z AS position_z,
    i.display_name,
    CASE WHEN a.probability_kind = 'exact' THEN a.probability_min END AS 'Chance (%)',
    l.location_key,
    a.*
FROM item_acquisitions a
LEFT JOIN items i ON i.stable_key = a.item_stable_key
LEFT JOIN item_acquisition_locations l ON l.owner_key = a.acquisition_key
LEFT JOIN zones z ON z.stable_key = l.zone_stable_key
WHERE a.kind IN ('fishing', 'fishing_bonus')
    AND a.player_access_state = 'verified_player'
    AND a.probability_stage = 'final_acquisition'
ORDER BY a.source_stable_key, a.item_stable_key, a.acquisition_key, l.location_key;
