CREATE TABLE item_provenance_meta (schema_version INTEGER NOT NULL, game_build_id TEXT NOT NULL, input_digests TEXT NOT NULL);
INSERT INTO item_provenance_meta VALUES (1, '10000001', '{}');
CREATE TABLE item_acquisitions (
    acquisition_key TEXT PRIMARY KEY NOT NULL, item_stable_key TEXT NOT NULL REFERENCES items(stable_key),
    kind TEXT NOT NULL, source_stable_key TEXT, source_group_key TEXT, source_copy_stable_key TEXT,
    variant_key TEXT, mechanic TEXT, player_access_state TEXT NOT NULL,
    probability_kind TEXT NOT NULL, probability_min REAL, probability_max REAL,
    probability_basis TEXT, probability_stage TEXT NOT NULL,
    quantity_min REAL, quantity_max REAL, quantity_kind TEXT NOT NULL,
    expected_quantity REAL, count_distribution TEXT, guarantee_scope TEXT
);
CREATE TABLE item_uses (
    use_key TEXT PRIMARY KEY NOT NULL, item_stable_key TEXT NOT NULL REFERENCES items(stable_key),
    target_stable_key TEXT, kind TEXT NOT NULL, variant_key TEXT, material_slot INTEGER,
    quantity_min REAL, quantity_max REAL, quantity_kind TEXT NOT NULL, mechanic TEXT, outcome_key TEXT
);
CREATE TABLE item_acquisition_conditions (
    owner_key TEXT NOT NULL REFERENCES item_acquisitions(acquisition_key), gate_key TEXT NOT NULL,
    group_index INTEGER NOT NULL, atom_index INTEGER NOT NULL, predicate TEXT NOT NULL,
    reference_stable_key TEXT, reference_slot TEXT, actor TEXT, value TEXT, minimum REAL, maximum REAL,
    minimum_inclusive INTEGER NOT NULL, maximum_inclusive INTEGER NOT NULL, scope TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'availability' CHECK (
        phase IN ('availability', 'source_initialization', 'operation_input', 'operation_outcome', 'mechanic_parameter')),
    PRIMARY KEY (owner_key, gate_key, group_index, atom_index, scope, phase)
);
CREATE TABLE item_use_conditions (
    owner_key TEXT NOT NULL REFERENCES item_uses(use_key), gate_key TEXT NOT NULL,
    group_index INTEGER NOT NULL, atom_index INTEGER NOT NULL, predicate TEXT NOT NULL,
    reference_stable_key TEXT, reference_slot TEXT, actor TEXT, value TEXT, minimum REAL, maximum REAL,
    minimum_inclusive INTEGER NOT NULL, maximum_inclusive INTEGER NOT NULL, scope TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'availability' CHECK (
        phase IN ('availability', 'source_initialization', 'operation_input', 'operation_outcome', 'mechanic_parameter')),
    PRIMARY KEY (owner_key, gate_key, group_index, atom_index, scope, phase)
);
CREATE TABLE item_acquisition_locations (
    owner_key TEXT NOT NULL REFERENCES item_acquisitions(acquisition_key), location_key TEXT NOT NULL,
    relation TEXT NOT NULL, scene TEXT, zone_stable_key TEXT, placement_key TEXT,
    coordinate_stable_key TEXT, x REAL, y REAL, z REAL, gate_scope TEXT,
    player_level_min INTEGER, player_level_max INTEGER, conditions TEXT NOT NULL,
    entry_zone_line_keys TEXT NOT NULL, source_copy_stable_key TEXT, PRIMARY KEY (owner_key, location_key)
);
CREATE TABLE item_use_locations (
    owner_key TEXT NOT NULL REFERENCES item_uses(use_key), location_key TEXT NOT NULL,
    relation TEXT NOT NULL, scene TEXT, zone_stable_key TEXT, placement_key TEXT,
    coordinate_stable_key TEXT, x REAL, y REAL, z REAL, gate_scope TEXT,
    player_level_min INTEGER, player_level_max INTEGER, conditions TEXT NOT NULL,
    entry_zone_line_keys TEXT NOT NULL, source_copy_stable_key TEXT, PRIMARY KEY (owner_key, location_key)
);
CREATE TABLE item_provenance_evidence (
    owner_key TEXT NOT NULL, input_relation TEXT NOT NULL, input_primary_key TEXT NOT NULL,
    PRIMARY KEY (owner_key, input_relation, input_primary_key)
);
CREATE TABLE item_dispositions (
    item_stable_key TEXT PRIMARY KEY NOT NULL, disposition TEXT NOT NULL,
    reason TEXT, evidence TEXT, current_pages TEXT NOT NULL, former_pages TEXT NOT NULL
);
INSERT INTO item_dispositions SELECT stable_key, 'current', NULL, NULL, '[]', '[]' FROM items;

-- The fixture seeds persisted facts independently. Runtime readers never select producer tables.
INSERT INTO item_acquisitions
SELECT 'drop:' || ld.character_stable_key || ':' || ld.item_stable_key,
    ld.item_stable_key, 'character_drop', s.group_key, s.group_key, ld.character_stable_key,
    'own-table', 'loot', 'verified_player', 'exact', ld.drop_probability, ld.drop_probability,
    'per_kill', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL
FROM loot_drops ld JOIN character_fact_sources s ON s.member_stable_key = ld.character_stable_key
WHERE NOT (COALESCE(ld.is_common_world_item, 0) = 1 AND NOT (
    COALESCE(ld.is_common, 0) OR COALESCE(ld.is_uncommon, 0) OR COALESCE(ld.is_rare, 0)
    OR COALESCE(ld.is_legendary, 0) OR COALESCE(ld.is_ultra_rare, 0)
    OR COALESCE(ld.is_guaranteed, 0) OR COALESCE(ld.is_actual, 0)));
INSERT INTO item_acquisitions
SELECT 'vendor:' || rowid, item_stable_key, 'vendor', vendor_stable_key, vendor_stable_key, copy_stable_key,
    COALESCE(quest_stable_key, 'stock'), 'vendor', 'verified_player', 'not_applicable', NULL, NULL,
    'not_applicable', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL FROM vendor_offers;
INSERT INTO item_acquisition_conditions
SELECT 'vendor:' || rowid, 'unlock', 0, 0, 'quest_done', quest_stable_key, NULL, 'player', NULL,
    NULL, NULL, 1, 1, 'source', 'availability' FROM vendor_offers WHERE quest_stable_key IS NOT NULL;
INSERT INTO item_acquisitions
SELECT 'mining:' || rowid, item_stable_key, 'mining', mining_node_stable_key, NULL, NULL,
    'ore', 'mining', 'verified_player', 'exact', drop_chance, drop_chance,
    'per_node', 'final_acquisition', 1, 3, 'bounded', 2, '[0.25,0.5,0.25]', 'successful_roll' FROM mining_node_items;
INSERT INTO item_acquisitions
SELECT 'fishing:' || rowid, item_stable_key, 'fishing', water_stable_key, NULL, NULL,
    type, 'fishing', 'verified_player', 'exact', drop_chance, drop_chance,
    'per_successful_catch', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL FROM water_fishables;
INSERT INTO item_acquisition_conditions
SELECT 'fishing:' || rowid, 'time', 0, 0, 'time_of_day', NULL, NULL, 'player',
    CASE type WHEN 'NightFishable' THEN 'night' ELSE 'day' END, NULL, NULL, 1, 1, 'source', 'availability' FROM water_fishables;
INSERT INTO item_acquisitions
SELECT 'bag:' || stable_key, item_stable_key, 'item_bag', stable_key, NULL, NULL,
    'pickup', 'pickup', 'verified_player', 'not_applicable', NULL, NULL,
    'not_applicable', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL FROM item_bags;
INSERT INTO item_acquisitions
SELECT 'common:' || ld.item_stable_key, ld.item_stable_key, 'common_world_item', NULL, NULL, NULL,
    'replacement', 'replacement', 'verified_player', 'bounded', MIN(ld.drop_probability), MAX(ld.drop_probability),
    'per_kill', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL
FROM loot_drops ld JOIN character_fact_sources s ON s.member_stable_key = ld.character_stable_key
WHERE COALESCE(ld.is_common_world_item, 0) = 1 AND ld.drop_probability > 0 AND NOT (
    COALESCE(ld.is_common, 0) OR COALESCE(ld.is_uncommon, 0) OR COALESCE(ld.is_rare, 0)
    OR COALESCE(ld.is_legendary, 0) OR COALESCE(ld.is_ultra_rare, 0)
    OR COALESCE(ld.is_guaranteed, 0) OR COALESCE(ld.is_actual, 0)) GROUP BY ld.item_stable_key;
INSERT INTO item_acquisitions
SELECT 'world:' || rowid, item_stable_key, 'special_world_drop', pool, NULL, NULL, pool,
    'world_drop', 'verified_player', 'exact', drop_probability, drop_probability,
    'per_kill', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL FROM special_world_drops;
INSERT INTO item_acquisition_conditions
SELECT 'world:' || rowid, 'level', 0, 0, 'actor_level', NULL, NULL, 'enemy', NULL,
    min_level_exclusive, NULL, 0, 1, 'source', 'source_initialization' FROM special_world_drops;
INSERT INTO item_acquisitions
SELECT 'dialog:' || cd.rowid, cd.give_item_stable_key, 'dialog', s.group_key, s.group_key, cd.character_stable_key,
    CAST(cd.dialog_index AS TEXT), 'dialog', 'verified_player', 'not_applicable', NULL, NULL,
    'not_applicable', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL
FROM character_dialogs cd JOIN character_fact_sources s ON s.member_stable_key = cd.character_stable_key
WHERE cd.give_item_stable_key IS NOT NULL;
INSERT INTO item_acquisition_conditions
SELECT 'dialog:' || cd.rowid, 'quest', 0, 0, 'quest_done', cd.required_quest_stable_key,
    NULL, 'player', NULL, NULL, NULL, 1, 1, 'source', 'availability'
FROM character_dialogs cd JOIN character_fact_sources s ON s.member_stable_key = cd.character_stable_key
WHERE cd.required_quest_stable_key IS NOT NULL;
INSERT INTO item_acquisitions
SELECT 'quest:' || rowid, item_on_complete_stable_key, 'quest_reward', quest_stable_key, NULL, NULL,
    CAST(rowid AS TEXT), 'completion', 'verified_player', 'not_applicable', NULL, NULL,
    'not_applicable', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL FROM quest_variants;
INSERT INTO item_acquisitions
SELECT 'craft:' || rowid, reward_item_stable_key, 'crafting', recipe_item_stable_key, NULL, NULL,
    'recipe', 'craft', 'verified_player', 'not_applicable', NULL, NULL,
    'not_applicable', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL FROM crafting_rewards;
INSERT INTO item_acquisitions
SELECT 'use:' || rowid, dropped_item_stable_key, 'item_drop', source_item_stable_key, NULL, NULL,
    'drop', 'use', 'verified_player', 'exact', drop_probability, drop_probability,
    'per_use', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL FROM item_drops;
INSERT INTO item_acquisitions
SELECT 'spell:' || rowid, created_item_stable_key, 'spell_created', source_item_stable_key, NULL, NULL,
    'cast', 'cast', 'verified_player', 'not_applicable', NULL, NULL,
    'not_applicable', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL FROM spell_created_items;
INSERT INTO item_acquisitions
SELECT 'conversion:' || rowid, output_item_stable_key, 'item_conversion', input_item_stable_key, NULL, NULL,
    zone_stable_key, 'conversion', 'verified_player', 'not_applicable', NULL, NULL,
    'not_applicable', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL FROM item_conversions;
INSERT INTO item_acquisitions
SELECT 'starting:' || rowid, item_stable_key, 'starting_class', class_name, NULL, NULL,
    'slot', 'new_character', 'verified_player', 'not_applicable', NULL, NULL,
    'not_applicable', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL FROM class_starting_items WHERE class_name != 'Default';
INSERT INTO item_acquisitions
SELECT 'auction:' || rowid, item_stable_key, 'auction_house', 'auction_house', NULL, NULL,
    route, 'listing', 'verified_player', 'unknown', NULL, NULL,
    'per_listing_opportunity', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL FROM auction_house_items;
INSERT INTO item_acquisitions VALUES
    ('ui:fixture', 'item:fixture relic', 'ui_grant', 'native:reliquary', NULL, NULL, 'room:1', 'furniture_reward',
    'verified_player', 'unknown', NULL, NULL, NULL, 'final_acquisition', 1, 2, 'bounded', 1.5, '[0.5,0.5]', NULL),
    ('internal:fixture', 'item:fixture relic', 'internal_equipment', 'character:fixture enemy', NULL, NULL,
    'equipment:1', 'equipment', 'internal_only', 'not_applicable', NULL, NULL, NULL, 'final_acquisition', NULL, NULL, 'unknown', NULL, NULL, NULL),
    ('fishing:bonus', 'item:fixture fish', 'fishing_bonus', 'water:stowaway-fixture', NULL, NULL, 'bonus:1', 'bonus',
    'verified_player', 'bounded', 1, 4, 'per_successful_catch', 'native_pool', 1, 1, 'exact', NULL, NULL, NULL);
INSERT INTO item_acquisition_locations
SELECT a.acquisition_key, 'placement:' || p.spawn_point_stable_key, 'spawn', p.scene, z.stable_key,
    p.character_stable_key || ':' || p.spawn_point_stable_key || ':direct', p.spawn_point_stable_key,
    p.x, p.y, p.z, p.character_stable_key || ':' || p.spawn_point_stable_key || ':direct', NULL, NULL, '[]', '[]', p.character_stable_key
FROM item_acquisitions a JOIN map_character_spawns p ON p.character_stable_key = a.source_copy_stable_key
JOIN zones z ON z.scene_name = p.scene;
INSERT INTO item_acquisition_locations
SELECT a.acquisition_key, 'site:' || t.stable_key, 'possible_treasure', t.scene, z.stable_key,
    t.stable_key, t.stable_key, t.x, t.y, t.z, t.stable_key,
    s.player_level_min, s.player_level_max, '[]', '[]', a.source_copy_stable_key
FROM item_acquisitions a JOIN treasure_chest_possible_spawns s ON s.chest_character_stable_key = a.source_copy_stable_key
JOIN treasure_locations t ON t.stable_key = s.treasure_location_stable_key JOIN zones z ON z.scene_name = t.scene;
INSERT INTO item_acquisition_locations
SELECT a.acquisition_key, 'fixed:' || p.stable_key, 'fixed', p.scene, z.stable_key, p.stable_key, p.stable_key,
    p.x, p.y, p.z, NULL, NULL, NULL, '[]', '[]', NULL
FROM item_acquisitions a JOIN (
    SELECT stable_key, scene, x, y, z FROM mining_nodes UNION ALL
    SELECT stable_key, scene, x, y, z FROM waters UNION ALL
    SELECT stable_key, scene, x, y, z FROM item_bags
) p ON p.stable_key = a.source_stable_key JOIN zones z ON z.scene_name = p.scene;
INSERT INTO item_acquisition_locations VALUES
    ('ui:fixture', 'room:unlocated', 'unlocated', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'room:1', 10, 35,
    '[{"gate_key":"room","group_index":0,"atom_index":0,"predicate":"room_furnished","reference_stable_key":"item:furniture - wood training","reference_slot":"room:1","actor":"player","value":"placed","minimum":null,"maximum":null,"minimum_inclusive":true,"maximum_inclusive":true,"scope":"room:unlocated","phase":"availability"},{"gate_key":"claim","group_index":0,"atom_index":0,"predicate":"account_state","reference_stable_key":"account_state:reliquary_claimed","reference_slot":null,"actor":"account","value":"false","minimum":null,"maximum":null,"minimum_inclusive":true,"maximum_inclusive":true,"scope":"room:unlocated","phase":"availability"},{"gate_key":"claim","group_index":0,"atom_index":0,"predicate":"account_state","reference_stable_key":"account_state:reliquary_claimed","reference_slot":null,"actor":"account","value":"true","minimum":null,"maximum":null,"minimum_inclusive":true,"maximum_inclusive":true,"scope":"room:unlocated","phase":"operation_outcome"}]', '["zone-line:stowaway-fixture"]', NULL);
INSERT INTO item_acquisition_conditions VALUES
    ('ui:fixture', 'eligibility', 0, 0, 'quest_done', 'quest:vendor-unlock', 'quest:1', 'player', 'complete', 1, 2, 1, 0, 'source', 'availability'),
    ('ui:fixture', 'eligibility', 1, 0, 'actor_class', 'class:paladin', 'class:1', 'player', 'Paladin', NULL, NULL, 1, 1, 'source', 'availability');
INSERT INTO item_provenance_evidence
SELECT acquisition_key, 'fixture_acquisition', acquisition_key FROM item_acquisitions;
INSERT INTO item_acquisitions VALUES
    ('unconfirmed:fixture', 'item:fixture relic', 'ui_grant', 'native:unknown', NULL, NULL, 'unknown', 'unknown',
    'unconfirmed_player', 'unknown', NULL, NULL, NULL, 'final_acquisition', NULL, NULL, 'unknown', NULL, NULL, NULL),
    ('impossible:fixture', 'item:fixture relic', 'dialog', 'native:impossible', NULL, NULL, 'impossible', 'dialog',
    'verified_player', 'not_applicable', NULL, NULL, NULL, 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL);
INSERT INTO item_acquisition_conditions VALUES
    ('impossible:fixture', 'gate:impossible', 0, 0, 'never', NULL, NULL, NULL, NULL, NULL, NULL, 1, 1, 'source', 'availability');
INSERT INTO item_acquisition_locations
SELECT a.acquisition_key, 'broker:' || b.character_stable_key, 'interaction', p.scene, z.stable_key,
    p.spawn_point_stable_key, p.spawn_point_stable_key, p.x, p.y, p.z, p.spawn_point_stable_key,
    NULL, NULL, '[]', '[]', b.character_stable_key
FROM item_acquisitions a CROSS JOIN auction_house_brokers b
JOIN map_character_spawns p ON p.character_stable_key = b.character_stable_key
JOIN zones z ON z.scene_name = p.scene WHERE a.kind = 'auction_house';
INSERT INTO item_acquisition_locations
SELECT a.acquisition_key, 'broker:' || b.character_stable_key, 'interaction', NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '[]', '[]', b.character_stable_key
FROM item_acquisitions a CROSS JOIN auction_house_brokers b
WHERE a.kind = 'auction_house' AND NOT EXISTS (
    SELECT 1 FROM map_character_spawns p WHERE p.character_stable_key = b.character_stable_key
);
INSERT INTO item_acquisition_conditions
SELECT 'auction:' || rowid, 'level_sim', 0, 0, 'actor_level', NULL, NULL, 'sim', NULL,
    min_sim_level, max_sim_level, 1, 1, 'source', 'availability' FROM auction_house_items;
INSERT INTO item_acquisition_conditions
SELECT 'auction:' || rowid, 'level_player', 0, 0, 'actor_level', NULL, NULL, 'player', NULL,
    min_player_level, max_player_level, 1, 1, 'source', 'availability' FROM auction_house_items
WHERE min_player_level IS NOT NULL OR max_player_level IS NOT NULL;
INSERT INTO item_acquisition_locations
SELECT a.acquisition_key, 'turnin:' || p.spawn_point_stable_key, 'interaction', p.scene, z.stable_key,
    p.spawn_point_stable_key, p.spawn_point_stable_key, p.x, p.y, p.z, p.spawn_point_stable_key,
    NULL, NULL, '[]', '[]', p.character_stable_key
FROM item_acquisitions a JOIN map_character_spawns p ON p.character_stable_key = 'character:breena carpenter'
JOIN zones z ON z.scene_name = p.scene
WHERE a.kind = 'quest_reward' AND a.source_stable_key = 'quest:vendor-unlock';
INSERT INTO item_acquisition_locations
SELECT a.acquisition_key, 'zone:' || z.stable_key, 'mechanic_zone', NULL, z.stable_key,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '[]', '[]', NULL
FROM item_acquisitions a JOIN zones z ON z.stable_key = a.variant_key WHERE a.kind = 'item_conversion';
INSERT INTO item_acquisition_conditions
SELECT a.acquisition_key, 'zone', 0, 0, 'zone_use', a.variant_key, NULL, 'player', NULL,
    NULL, NULL, 1, 1, 'source', 'operation_input' FROM item_acquisitions a WHERE a.kind = 'item_conversion';
ALTER TABLE item_acquisitions ADD COLUMN guaranteed_roll_count INTEGER;
UPDATE item_acquisitions SET guaranteed_roll_count = 2, guarantee_scope = 'pool'
WHERE kind = 'character_drop' AND source_copy_stable_key = 'character:fixture enemy'
    AND item_stable_key = 'item:fixture drop';

UPDATE item_acquisitions SET probability_kind = 'exact', probability_min = 1.25, probability_max = 1.25,
    source_stable_key = NULL, variant_key = NULL, mechanic = 'fishing_global_replacement'
WHERE acquisition_key = 'fishing:bonus';
DELETE FROM item_acquisition_locations WHERE owner_key = 'fishing:bonus';
UPDATE item_acquisitions SET probability_min = 7.1875, probability_max = 7.1875 WHERE acquisition_key = 'fishing:1';
INSERT INTO item_acquisitions
SELECT 'fishing:overlap-night', item_stable_key, kind, source_stable_key, source_group_key, source_copy_stable_key,
    'NightFishable', mechanic, player_access_state, probability_kind, 7.583333333333333, 7.583333333333333,
    probability_basis, probability_stage, quantity_min, quantity_max, quantity_kind, expected_quantity,
    count_distribution, guarantee_scope, guaranteed_roll_count FROM item_acquisitions WHERE acquisition_key = 'fishing:1';
INSERT INTO item_acquisition_conditions VALUES
    ('fishing:overlap-night', 'time', 0, 0, 'time_of_day', NULL, NULL, 'player', 'night', NULL, NULL, 1, 1, 'source', 'availability');
INSERT INTO item_acquisition_locations
SELECT 'fishing:overlap-night', location_key, relation, scene, zone_stable_key, placement_key,
    coordinate_stable_key, x, y, z, gate_scope, player_level_min, player_level_max, conditions,
    entry_zone_line_keys, source_copy_stable_key FROM item_acquisition_locations WHERE owner_key = 'fishing:1';
INSERT INTO waters (stable_key, scene, x, y, z, width, depth) VALUES
    ('water:pure-global-one', 'StowawayPortal', 10, 0, 20, 20, 20),
    ('water:pure-global-two', 'Brake', 30, 0, 40, 20, 20);
INSERT INTO item_acquisitions
SELECT 'global-final:' || w.stable_key || ':' || time.period, 'item:fixture fish', 'fishing', w.stable_key,
    NULL, NULL, time.period, 'fishing', 'verified_player', 'exact', 1.25, 1.25, 'per_successful_catch',
    'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL, NULL
FROM waters w CROSS JOIN (SELECT 'DayFishable' AS period UNION ALL SELECT 'NightFishable') time
WHERE w.stable_key IN ('water:pure-global-one', 'water:pure-global-two');
INSERT INTO item_acquisition_conditions
SELECT acquisition_key, 'time', 0, 0, 'time_of_day', NULL, NULL, 'player',
    CASE variant_key WHEN 'DayFishable' THEN 'day' ELSE 'night' END, NULL, NULL, 1, 1, 'source', 'availability'
FROM item_acquisitions WHERE acquisition_key LIKE 'global-final:%';
INSERT INTO item_acquisition_locations
SELECT a.acquisition_key, 'fixed:' || w.stable_key, 'fixed', w.scene, z.stable_key, w.stable_key, w.stable_key,
    w.x, w.y, w.z, NULL, NULL, NULL, '[]', '[]', NULL
FROM item_acquisitions a JOIN waters w ON w.stable_key = a.source_stable_key
JOIN zones z ON z.scene_name = w.scene WHERE a.acquisition_key LIKE 'global-final:%';
INSERT INTO item_provenance_evidence
SELECT acquisition_key, 'fixture_acquisition', acquisition_key FROM item_acquisitions
WHERE acquisition_key = 'fishing:overlap-night' OR acquisition_key LIKE 'global-final:%';

UPDATE item_dispositions SET disposition = 'removed', reason = 'Reviewed retired fixture',
    evidence = 'fixture:lifecycle', current_pages = '[]', former_pages = '["Wood Training Set"]'
WHERE item_stable_key = 'item:furniture - wood training';
INSERT INTO items VALUES
    ('item:fixture meditate retired', 'Retired Meditative Trance', 'Spell Scroll: Meditative Trance', NULL, 10, 0);
INSERT INTO item_dispositions VALUES
    ('item:fixture meditate retired', 'removed', 'Reviewed retired variant', 'fixture:variant-lifecycle', '[]', '["Spell Scroll: Meditative Trance"]'),
    ('item:reviewed absent', 'removed', 'Reviewed identity absent from native items', 'fixture:absent-lifecycle', '[]', '["Former Fixture Page"]');
INSERT INTO item_acquisitions VALUES
    ('lifecycle:retired', 'item:furniture - wood training', 'vendor', 'character-group:breena', 'character-group:breena',
    'character:breena carpenter', 'retired-stock', 'vendor', 'verified_player', 'not_applicable', NULL, NULL,
    'not_applicable', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL, NULL),
    ('lifecycle:hidden-retired', 'item:fixture meditate retired', 'vendor', 'character-group:breena', 'character-group:breena',
    'character:breena carpenter', 'retired-variant', 'vendor', 'verified_player', 'not_applicable', NULL, NULL,
    'not_applicable', 'final_acquisition', 1, 1, 'exact', NULL, NULL, NULL, NULL);
INSERT INTO item_provenance_evidence
SELECT acquisition_key, 'fixture_acquisition', acquisition_key FROM item_acquisitions WHERE acquisition_key LIKE 'lifecycle:%';
INSERT INTO items VALUES ('item:fixture unknown', 'Unknown Fixture', NULL, NULL, 1, 0);
INSERT INTO item_dispositions VALUES ('item:fixture unknown', 'current', NULL, NULL, '[]', '[]');
INSERT INTO item_uses VALUES
    ('use:fixture', 'item:fixture ore', 'item:fixture key', 'crafting_material', 'recipe:fixture', 2,
    2, 3, 'bounded', 'crafting', 'outcome:fixture');
INSERT INTO item_use_conditions VALUES
    ('use:fixture', 'quality', 0, 0, 'quality', NULL, 'slot:2', 'player', 'normal', 2, 5, 1, 0, 'source', 'operation_input'),
    ('use:fixture', 'quality', 0, 0, 'quality', NULL, 'slot:2', 'player', 'normal', 8, 10, 1, 1, 'source', 'operation_outcome'),
    ('use:fixture', 'chance', 0, 0, 'formula_operand', NULL, NULL, NULL, 'chance_per_pair', 0.25, 0.25, 1, 1, 'source', 'mechanic_parameter');
INSERT INTO item_use_locations VALUES
    ('use:fixture', 'zone:fixture', 'mechanic_zone', 'Stowaway', 'zone:stowaway', NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, '[]', '[]', NULL);
INSERT INTO item_provenance_evidence VALUES ('use:fixture', 'fixture_use', '["item:fixture ore",2]');
INSERT INTO item_acquisition_conditions VALUES
    ('drop:character:fixture enemy:item:fixture drop', 'ownership', 0, 0, 'item_not_owned',
    'item:fixture key', NULL, 'player', 'inventory', NULL, NULL, 1, 1, 'source', 'source_initialization'),
    ('drop:character:fixture enemy:item:fixture drop', 'ownership', 0, 0, 'item_held',
    'item:fixture key', NULL, 'player', 'inventory', 1, NULL, 1, 1, 'source', 'operation_input');
