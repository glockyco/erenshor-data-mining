SELECT
    a.item_stable_key,
    i.display_name,
    z.zone_name,
    l.x AS position_x,
    l.y AS position_y,
    l.z AS position_z,
    CASE WHEN l.coordinate_stable_key IS NOT NULL THEN map_marker_url(l.coordinate_stable_key) END AS MapLink,
    l.location_key,
    a.acquisition_key,
    a.source_stable_key,
    a.source_group_key,
    a.source_copy_stable_key,
    a.variant_key,
    a.mechanic,
    a.player_access_state,
    a.probability_kind,
    a.probability_min,
    a.probability_max,
    a.probability_basis,
    a.probability_stage,
    a.quantity_min,
    a.quantity_max,
    a.quantity_kind,
    a.expected_quantity,
    a.count_distribution,
    a.guarantee_scope,
    a.guaranteed_roll_count
FROM item_acquisitions a
LEFT JOIN items i ON i.stable_key = a.item_stable_key
LEFT JOIN item_acquisition_locations l ON l.owner_key = a.acquisition_key
LEFT JOIN zones z ON z.stable_key = l.zone_stable_key
WHERE a.kind = 'item_bag'
    AND a.player_access_state = 'verified_player'
    AND a.probability_stage = 'final_acquisition'
ORDER BY l.scene, a.item_stable_key, a.acquisition_key, l.location_key;
