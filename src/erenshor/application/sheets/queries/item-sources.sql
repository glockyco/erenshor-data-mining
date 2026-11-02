-- Conditions are already public. Preserve every gate, alternative and atom as stored.
WITH names AS (
    SELECT stable_key, display_name AS name FROM items
    UNION ALL SELECT stable_key, display_name FROM characters
    UNION ALL SELECT stable_key, display_name FROM quests
    UNION ALL SELECT stable_key, display_name FROM zones
    UNION ALL SELECT stable_key, display_name FROM spells
    UNION ALL SELECT 'class:' || lower(class_name), display_name FROM classes
    UNION ALL SELECT stable_key, npc_name FROM mining_nodes
), atoms AS (
    SELECT owner_key, '' AS place_key, gate_index, alternative_index, atom_index,
        predicate, reference_stable_key, reference_slot, actor, value,
        minimum, maximum, minimum_inclusive, maximum_inclusive
    FROM item_conditions
    UNION ALL
    SELECT place_set_key, place_key, gate_index, alternative_index, atom_index,
        predicate, reference_stable_key, reference_slot, actor, value,
        minimum, maximum, minimum_inclusive, maximum_inclusive
    FROM item_place_conditions
), subjects AS (
    -- Words requirements as the map does. A source's own atoms can name the source's item or reward quest.
    SELECT a.*, COALESCE(n.name, substr(a.reference_stable_key, instr(a.reference_stable_key, ':') + 1), '') AS subject,
        src.item_stable_key AS source_item, CASE src.kind WHEN 'quest_reward' THEN src.source_stable_key END AS reward_quest,
        CASE
            WHEN minimum IS NOT NULL AND maximum IS NOT NULL AND minimum_inclusive = 1 AND maximum_inclusive = 1 THEN
                printf('%.15g', minimum) || CASE WHEN minimum = maximum THEN '' ELSE '–' || printf('%.15g', maximum) END
            ELSE
                CASE WHEN minimum IS NULL THEN '' WHEN minimum_inclusive = 1 THEN printf('%.15g', minimum) || ' or higher'
                    ELSE 'above ' || printf('%.15g', minimum) END ||
                CASE WHEN minimum IS NOT NULL AND maximum IS NOT NULL THEN ' and ' ELSE '' END ||
                CASE WHEN maximum IS NULL THEN '' WHEN maximum_inclusive = 1 THEN printf('%.15g', maximum) || ' or lower'
                    ELSE 'below ' || printf('%.15g', maximum) END
        END AS bounds
    FROM atoms a
    LEFT JOIN names n ON n.stable_key = a.reference_stable_key
    LEFT JOIN item_sources src ON src.source_key = a.owner_key AND a.place_key = ''
), worded AS (
    SELECT *, CASE predicate
        WHEN 'quest_done' THEN 'Requires ' || subject
        WHEN 'quest_not_done' THEN CASE WHEN reference_stable_key = reward_quest THEN 'Once per character' ELSE 'Only before ' || subject END
        WHEN 'item_held' THEN 'Requires ' || subject || CASE WHEN COALESCE(minimum, 1) > 1 THEN ' ×' || printf('%.15g', minimum) ELSE '' END
        WHEN 'key_held' THEN 'Requires ' || subject || CASE WHEN COALESCE(minimum, 1) > 1 THEN ' ×' || printf('%.15g', minimum) ELSE '' END
        WHEN 'item_not_owned' THEN CASE WHEN reference_stable_key = source_item THEN 'Only if you don''t have one'
            ELSE 'Only if you don''t have ' || subject END
        WHEN 'room_furnished' THEN 'Requires the ' || subject || COALESCE(' in room ' || reference_slot, ' in its room')
        WHEN 'encounter_won' THEN 'Requires defeating ' || subject
        WHEN 'actor_class' THEN CASE WHEN actor IN ('sim', 'sim_player') THEN 'Requires a simulated player of class ' || subject
            ELSE 'Requires the ' || subject || ' class' END
        WHEN 'account_state' THEN CASE WHEN reference_stable_key = 'account_state:reliquary_claimed' THEN
                CASE value WHEN 'false' THEN 'Only before claiming your Reliquary' ELSE 'Requires a claimed Reliquary' END
            ELSE CASE value WHEN 'false' THEN 'Only before ' ELSE 'Requires ' END || subject END
        WHEN 'never' THEN 'Never'
        WHEN 'time_of_day' THEN CASE value WHEN 'day' THEN 'Only during the day' WHEN 'night' THEN 'Only at night' ELSE 'Only during ' || value END
        WHEN 'actor_level' THEN 'Requires ' ||
            CASE WHEN actor = 'enemy' THEN 'enemy level ' WHEN actor IN ('sim', 'sim_player') THEN 'simulated player level ' ELSE 'level ' END || bounds
        WHEN 'zone_use' THEN 'Only in ' || subject
        WHEN 'quality' THEN 'Requires quality ' || COALESCE(value, NULLIF(bounds, ''), subject)
        WHEN 'route' THEN CASE value WHEN 'normal_pointer_inventory_transfer' THEN 'Drag it into your inventory'
            ELSE replace(COALESCE(value, ''), '_', ' ') END
        ELSE trim(COALESCE(replace(actor, '_', ' ') || ' ', '') || replace(predicate, '_', ' ') || ' ' || subject || ' ' || COALESCE(value, '') || ' ' || bounds)
    END AS wording
    FROM subjects
), alternatives AS (
    SELECT owner_key, place_key, gate_index, alternative_index,
        CASE WHEN count(*) > 1 THEN '(' ELSE '' END ||
        group_concat(wording, ' and ' ORDER BY atom_index) ||
        CASE WHEN count(*) > 1 THEN ')' ELSE '' END AS wording
    FROM worded
    GROUP BY owner_key, place_key, gate_index, alternative_index
), gates AS (
    SELECT owner_key, place_key, gate_index,
        CASE WHEN count(*) > 1 THEN '(' ELSE '' END ||
        group_concat(wording, ' or ' ORDER BY alternative_index) ||
        CASE WHEN count(*) > 1 THEN ')' ELSE '' END AS wording
    FROM alternatives
    GROUP BY owner_key, place_key, gate_index
), conditions AS (
    SELECT owner_key, place_key, group_concat(wording, ' and ' ORDER BY gate_index) AS wording
    FROM gates
    GROUP BY owner_key, place_key
), places AS (
    SELECT p.place_set_key, p.place_key,
        COALESCE(z.display_name, p.scene, p.zone_stable_key, p.relation) ||
        CASE WHEN c.wording IS NOT NULL THEN ' (' || c.wording || ')' ELSE '' END ||
        CASE WHEN p.player_level_min IS NOT NULL OR p.player_level_max IS NOT NULL THEN
            ' (Requires level ' ||
            CASE WHEN p.player_level_min IS NOT NULL AND p.player_level_max IS NOT NULL THEN
                p.player_level_min || CASE WHEN p.player_level_min = p.player_level_max THEN '' ELSE '–' || p.player_level_max END
            WHEN p.player_level_min IS NOT NULL THEN p.player_level_min || ' or higher'
            ELSE p.player_level_max || ' or lower' END || ')' ELSE '' END AS wording
    FROM item_places p
    LEFT JOIN zones z ON z.stable_key = p.zone_stable_key
    LEFT JOIN conditions c ON c.owner_key = p.place_set_key AND c.place_key = p.place_key
), zone_lists AS (
    SELECT place_set_key, group_concat(wording, '; ' ORDER BY wording) AS wording
    FROM (SELECT DISTINCT place_set_key, wording FROM places)
    GROUP BY place_set_key
)
SELECT
    i.display_name AS Item,
    CASE s.kind
        WHEN 'character_drop' THEN 'Dropped by'
        WHEN 'common_world_item' THEN 'Common world drop'
        WHEN 'special_world_drop' THEN 'World drop'
        WHEN 'vendor' THEN 'Sold by'
        WHEN 'dialog' THEN 'Talk to'
        WHEN 'quest_reward' THEN 'Quest reward'
        WHEN 'crafting' THEN 'Crafting recipe'
        WHEN 'item_drop' THEN 'Use item'
        WHEN 'spell_created' THEN 'Created by'
        WHEN 'mining' THEN 'Mining'
        WHEN 'fishing' THEN 'Fishing'
        WHEN 'auction_house' THEN 'Auction House'
        WHEN 'item_bag' THEN 'Ground item'
        WHEN 'starting_class' THEN 'Starting item'
        WHEN 'ui_grant' THEN 'Available from'
        WHEN 'item_conversion' THEN 'Convert item'
        ELSE replace(s.kind, '_', ' ')
    END AS Kind,
    CASE
        WHEN s.mechanic = 'fishing_global_replacement' THEN 'Any water'
        WHEN s.kind = 'common_world_item' THEN 'Any enemy with common drops'
        WHEN s.kind = 'special_world_drop' THEN 'Any enemy'
        WHEN s.kind = 'auction_house' THEN 'Auction House'
        WHEN s.kind = 'ui_grant' AND s.mechanic = 'cosmetic_panel' THEN 'Cosmetic panel'
        WHEN s.kind = 'ui_grant' AND s.mechanic = 'planning_table' THEN 'Planning table'
        WHEN s.kind = 'mining' THEN 'Mining node'
        WHEN s.kind = 'fishing' THEN 'Fishable water'
        WHEN s.kind = 'item_bag' THEN 'Ground item'
        ELSE COALESCE(n.name, copy.name, replace(s.kind, '_', ' '))
    END AS Source,
    CASE s.probability_kind
        WHEN 'not_applicable' THEN ''
        WHEN 'unknown' THEN 'Chance unknown'
        ELSE rtrim(rtrim(printf('%.2f', s.probability_min), '0'), '.') || '%' ||
            CASE WHEN s.probability_min != s.probability_max THEN
                ' to ' || rtrim(rtrim(printf('%.2f', s.probability_max), '0'), '.') || '%' ELSE '' END
    END || CASE WHEN s.probability_kind = 'not_applicable' THEN '' ELSE CASE s.probability_basis
        WHEN 'per_kill' THEN ' per kill'
        WHEN 'per_successful_catch' THEN ' per successful catch'
        WHEN 'per_node' THEN ' per node'
        WHEN 'per_use' THEN ' per use'
        WHEN 'per_listing_opportunity' THEN ' per listing opportunity'
        ELSE '' END END AS Chance,
    CASE WHEN s.quantity_kind IN ('unknown', 'not_applicable') THEN '' ELSE
        'Quantity ' || CASE WHEN s.quantity_min IS NULL THEN '?' ELSE printf('%.15g', s.quantity_min) END ||
        CASE WHEN s.quantity_min IS NOT s.quantity_max THEN
            ' to ' || CASE WHEN s.quantity_max IS NULL THEN '?' ELSE printf('%.15g', s.quantity_max) END ELSE '' END END ||
    CASE WHEN s.expected_quantity IS NOT NULL THEN
        CASE WHEN s.quantity_kind IN ('unknown', 'not_applicable') THEN '' ELSE ', ' END ||
        'Average ' || printf('%.15g', s.expected_quantity) || CASE WHEN s.probability_basis = 'per_kill' THEN ' per kill' ELSE '' END ELSE '' END ||
    CASE WHEN s.guaranteed THEN CASE WHEN s.quantity_kind NOT IN ('unknown', 'not_applicable') OR s.expected_quantity IS NOT NULL THEN ', ' ELSE '' END || 'Guaranteed' ELSE '' END ||
    CASE WHEN s.quantity_kind IN ('unknown', 'not_applicable') AND s.expected_quantity IS NULL AND NOT s.guaranteed THEN 'Quantity unknown' ELSE '' END AS Quantity,
    c.wording AS Conditions,
    CASE WHEN s.mechanic = 'fishing_global_replacement' THEN 'Any water' ELSE z.wording END AS Zones,
    (SELECT group_concat(n.name, ', ' ORDER BY n.name, sc.character_stable_key)
     FROM item_source_contributors sc
     LEFT JOIN names n ON n.stable_key = sc.character_stable_key
     WHERE sc.source_key = s.source_key) AS contributors,
    s.source_key,
    s.item_stable_key,
    s.source_stable_key,
    s.source_group_key,
    s.source_copy_stable_key,
    s.variant_key,
    s.mechanic,
    s.probability_kind,
    s.probability_min,
    s.probability_max,
    s.probability_basis,
    s.quantity_kind,
    s.quantity_min,
    s.quantity_max,
    s.expected_quantity,
    s.guaranteed,
    s.place_set_key
FROM item_sources s
LEFT JOIN items i ON i.stable_key = s.item_stable_key
LEFT JOIN names n ON n.stable_key = s.source_stable_key
LEFT JOIN names copy ON copy.stable_key = s.source_copy_stable_key
LEFT JOIN conditions c ON c.owner_key = s.source_key AND c.place_key = ''
LEFT JOIN zone_lists z ON z.place_set_key = s.place_set_key
ORDER BY i.display_name, s.kind, Source, s.source_key;
