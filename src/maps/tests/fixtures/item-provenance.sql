CREATE TABLE item_provenance_meta (schema_version INTEGER NOT NULL, game_build_id TEXT NOT NULL, input_digests TEXT NOT NULL);
INSERT INTO item_provenance_meta VALUES (3, '10000001', '{}');
CREATE TABLE item_sources (
    source_key TEXT PRIMARY KEY NOT NULL, item_stable_key TEXT NOT NULL REFERENCES items(stable_key),
    kind TEXT NOT NULL, source_stable_key TEXT, source_group_key TEXT, source_copy_stable_key TEXT,
    variant_key TEXT, mechanic TEXT, probability_kind TEXT NOT NULL, probability_min REAL, probability_max REAL,
    probability_basis TEXT, quantity_kind TEXT NOT NULL, quantity_min REAL, quantity_max REAL,
    expected_quantity REAL, guaranteed INTEGER NOT NULL CHECK (guaranteed IN (0, 1)), place_set_key TEXT
);
CREATE TABLE item_conditions (
    owner_key TEXT NOT NULL, gate_index INTEGER NOT NULL, alternative_index INTEGER NOT NULL,
    atom_index INTEGER NOT NULL, gate_key TEXT NOT NULL, predicate TEXT NOT NULL,
    reference_stable_key TEXT, reference_slot TEXT, actor TEXT, value TEXT, minimum REAL, maximum REAL,
    minimum_inclusive INTEGER NOT NULL, maximum_inclusive INTEGER NOT NULL, phase TEXT NOT NULL,
    PRIMARY KEY (owner_key, gate_index, alternative_index, atom_index)
) WITHOUT ROWID;
CREATE TABLE item_places (
    place_set_key TEXT NOT NULL, place_key TEXT NOT NULL, relation TEXT NOT NULL,
    scene TEXT, zone_stable_key TEXT, marker_stable_key TEXT, x REAL, y REAL, z REAL,
    player_level_min INTEGER, player_level_max INTEGER, source_copy_stable_key TEXT, entry_zone_line_keys TEXT,
    PRIMARY KEY (place_set_key, place_key)
) WITHOUT ROWID;
CREATE TABLE item_place_conditions (
    place_set_key TEXT NOT NULL, place_key TEXT NOT NULL,
    gate_index INTEGER NOT NULL, alternative_index INTEGER NOT NULL, atom_index INTEGER NOT NULL,
    gate_key TEXT NOT NULL, predicate TEXT NOT NULL, reference_stable_key TEXT, reference_slot TEXT,
    actor TEXT, value TEXT, minimum REAL, maximum REAL, minimum_inclusive INTEGER NOT NULL,
    maximum_inclusive INTEGER NOT NULL, phase TEXT NOT NULL,
    PRIMARY KEY (place_set_key, place_key, gate_index, alternative_index, atom_index)
) WITHOUT ROWID;
CREATE TABLE item_statuses (
    item_stable_key TEXT PRIMARY KEY NOT NULL,
    disposition TEXT NOT NULL CHECK (disposition IN ('current', 'removed', 'unobtainable', 'unused')),
    reason TEXT, current_pages TEXT NOT NULL, former_pages TEXT NOT NULL
);
CREATE TABLE item_source_contributors (
    source_key TEXT NOT NULL REFERENCES item_sources(source_key), character_stable_key TEXT NOT NULL,
    PRIMARY KEY (source_key, character_stable_key)
) WITHOUT ROWID;

INSERT INTO items VALUES
    ('item:fixture meditate retired', 'Retired Meditative Trance', 'Spell Scroll: Meditative Trance', NULL, 10, 0),
    ('item:fixture unknown', 'Unknown Fixture', NULL, NULL, 1, 0);
INSERT INTO item_statuses SELECT stable_key, 'current', NULL, '[]', '[]' FROM items;
UPDATE item_statuses SET disposition = 'removed', reason = 'Reviewed retired fixture',
    former_pages = '["Wood Training Set"]' WHERE item_stable_key = 'item:furniture - wood training';
UPDATE item_statuses SET disposition = 'removed', reason = 'Reviewed retired variant',
    former_pages = '["Spell Scroll: Meditative Trance"]' WHERE item_stable_key = 'item:fixture meditate retired';
INSERT INTO item_statuses VALUES
    ('item:reviewed absent', 'removed', 'Reviewed identity absent from native items', '[]', '["Former Fixture Page"]');

-- Seed the public view directly from the base fixture's producer rows.
INSERT INTO item_sources
SELECT 'drop:' || ld.character_stable_key || ':' || ld.item_stable_key,
    ld.item_stable_key, 'character_drop', s.group_key, s.group_key, ld.character_stable_key,
    'own-table', 'loot', 'exact', ld.drop_probability, ld.drop_probability,
    'per_kill', 'exact', 1, 1, NULL, 0, NULL
FROM loot_drops ld JOIN character_fact_sources s ON s.member_stable_key = ld.character_stable_key
WHERE ld.drop_probability > 0 AND NOT (COALESCE(ld.is_common_world_item, 0) = 1 AND NOT (
    COALESCE(ld.is_common, 0) OR COALESCE(ld.is_uncommon, 0) OR COALESCE(ld.is_rare, 0)
    OR COALESCE(ld.is_legendary, 0) OR COALESCE(ld.is_ultra_rare, 0)
    OR COALESCE(ld.is_guaranteed, 0) OR COALESCE(ld.is_actual, 0)));
INSERT INTO item_sources
SELECT 'vendor:' || rowid, item_stable_key, 'vendor', vendor_stable_key, vendor_stable_key, copy_stable_key,
    COALESCE(quest_stable_key, 'stock'), 'vendor', 'not_applicable', NULL, NULL,
    'not_applicable', 'exact', 1, 1, NULL, 0, NULL FROM vendor_offers;
INSERT INTO item_conditions
SELECT 'vendor:' || rowid, 0, 0, 0, 'unlock', 'quest_done', quest_stable_key, NULL, 'player', NULL,
    NULL, NULL, 1, 1, 'availability' FROM vendor_offers WHERE quest_stable_key IS NOT NULL;
INSERT INTO item_sources
SELECT 'mining:' || rowid, item_stable_key, 'mining', mining_node_stable_key, NULL, NULL,
    'ore', 'mining', 'exact', drop_chance, drop_chance,
    'per_node', 'bounded', 1, 3, 2, 0, NULL FROM mining_node_items WHERE drop_chance > 0;
INSERT INTO item_sources
SELECT 'fishing:' || rowid, item_stable_key, 'fishing', water_stable_key, NULL, NULL,
    type, 'fishing', 'exact', drop_chance, drop_chance,
    'per_successful_catch', 'exact', 1, 1, NULL, 0, NULL FROM water_fishables WHERE drop_chance > 0;
INSERT INTO item_conditions
SELECT 'fishing:' || rowid, 0, 0, 0, 'time', 'time_of_day', NULL, NULL, 'player',
    CASE type WHEN 'NightFishable' THEN 'night' ELSE 'day' END, NULL, NULL, 1, 1, 'availability'
FROM water_fishables WHERE drop_chance > 0;
INSERT INTO item_sources
SELECT 'bag:' || stable_key, item_stable_key, 'item_bag', stable_key, NULL, NULL,
    'pickup', 'pickup', 'not_applicable', NULL, NULL,
    'not_applicable', 'exact', 1, 1, NULL, 0, NULL FROM item_bags;
INSERT INTO item_sources
SELECT 'common:' || ld.item_stable_key, ld.item_stable_key, 'common_world_item', NULL, NULL, NULL,
    'replacement', 'replacement', 'bounded', MIN(ld.drop_probability), MAX(ld.drop_probability),
    'per_kill', 'exact', 1, 1, NULL, 0, NULL
FROM loot_drops ld JOIN character_fact_sources s ON s.member_stable_key = ld.character_stable_key
WHERE COALESCE(ld.is_common_world_item, 0) = 1 AND ld.drop_probability > 0 AND NOT (
    COALESCE(ld.is_common, 0) OR COALESCE(ld.is_uncommon, 0) OR COALESCE(ld.is_rare, 0)
    OR COALESCE(ld.is_legendary, 0) OR COALESCE(ld.is_ultra_rare, 0)
    OR COALESCE(ld.is_guaranteed, 0) OR COALESCE(ld.is_actual, 0)) GROUP BY ld.item_stable_key;
INSERT INTO item_source_contributors
SELECT 'common:' || ld.item_stable_key, ld.character_stable_key
FROM loot_drops ld JOIN character_fact_sources s ON s.member_stable_key = ld.character_stable_key
WHERE COALESCE(ld.is_common_world_item, 0) = 1 AND ld.drop_probability > 0 AND NOT (
    COALESCE(ld.is_common, 0) OR COALESCE(ld.is_uncommon, 0) OR COALESCE(ld.is_rare, 0)
    OR COALESCE(ld.is_legendary, 0) OR COALESCE(ld.is_ultra_rare, 0)
    OR COALESCE(ld.is_guaranteed, 0) OR COALESCE(ld.is_actual, 0));
INSERT INTO item_sources
SELECT 'world:' || rowid, item_stable_key, 'special_world_drop', pool, NULL, NULL, pool,
    'world_drop', 'exact', drop_probability, drop_probability,
    'per_kill', 'exact', 1, 1, NULL, 0, NULL FROM special_world_drops WHERE drop_probability > 0;
INSERT INTO item_conditions
SELECT 'world:' || rowid, 0, 0, 0, 'level', 'actor_level', NULL, NULL, 'enemy', NULL,
    min_level_exclusive, NULL, 0, 1, 'source_initialization' FROM special_world_drops WHERE drop_probability > 0;
INSERT INTO item_sources
SELECT 'dialog:' || cd.rowid, cd.give_item_stable_key, 'dialog', s.group_key, s.group_key, cd.character_stable_key,
    CAST(cd.dialog_index AS TEXT), 'dialog', 'not_applicable', NULL, NULL,
    'not_applicable', 'exact', 1, 1, NULL, 0, NULL
FROM character_dialogs cd JOIN character_fact_sources s ON s.member_stable_key = cd.character_stable_key
WHERE cd.give_item_stable_key IS NOT NULL;
INSERT INTO item_conditions
SELECT 'dialog:' || cd.rowid, 0, 0, 0, 'quest', 'quest_done', cd.required_quest_stable_key,
    NULL, 'player', NULL, NULL, NULL, 1, 1, 'availability'
FROM character_dialogs cd JOIN character_fact_sources s ON s.member_stable_key = cd.character_stable_key
WHERE cd.give_item_stable_key IS NOT NULL AND cd.required_quest_stable_key IS NOT NULL;
INSERT INTO item_sources
SELECT 'quest:' || rowid, item_on_complete_stable_key, 'quest_reward', quest_stable_key, NULL, NULL,
    CAST(rowid AS TEXT), 'completion', 'not_applicable', NULL, NULL,
    'not_applicable', 'exact', 1, 1, NULL, 0, NULL FROM quest_variants;
INSERT INTO item_sources
SELECT 'craft:' || rowid, reward_item_stable_key, 'crafting', recipe_item_stable_key, NULL, NULL,
    'recipe', 'craft', 'not_applicable', NULL, NULL,
    'not_applicable', 'exact', 1, 1, NULL, 0, NULL FROM crafting_rewards;
INSERT INTO item_sources
SELECT 'use:' || rowid, dropped_item_stable_key, 'item_drop', source_item_stable_key, NULL, NULL,
    'drop', 'use', 'exact', drop_probability, drop_probability,
    'per_use', 'exact', 1, 1, NULL, 0, NULL FROM item_drops WHERE drop_probability > 0;
INSERT INTO item_sources
SELECT 'spell:' || rowid, created_item_stable_key, 'spell_created', source_item_stable_key, NULL, NULL,
    'cast', 'cast', 'not_applicable', NULL, NULL,
    'not_applicable', 'exact', 1, 1, NULL, 0, NULL FROM spell_created_items;
INSERT INTO item_sources
SELECT 'conversion:' || rowid, output_item_stable_key, 'item_conversion', input_item_stable_key, NULL, NULL,
    zone_stable_key, 'conversion', 'not_applicable', NULL, NULL,
    'not_applicable', 'exact', 1, 1, NULL, 0, 'zone:' || zone_stable_key FROM item_conversions;
INSERT INTO item_conditions
SELECT 'conversion:' || rowid, 0, 0, 0, 'zone', 'zone_use', zone_stable_key, NULL, 'player', NULL,
    NULL, NULL, 1, 1, 'operation_input' FROM item_conversions;
INSERT INTO item_sources
SELECT 'starting:' || rowid, item_stable_key, 'starting_class', class_name, NULL, NULL,
    'slot', 'new_character', 'not_applicable', NULL, NULL,
    'not_applicable', 'exact', 1, 1, NULL, 0, NULL FROM class_starting_items WHERE class_name != 'Default';
INSERT INTO item_sources
SELECT 'auction:' || rowid, item_stable_key, 'auction_house', 'auction_house', NULL, NULL,
    route, 'listing', 'unknown', NULL, NULL,
    'per_listing_opportunity', 'exact', 1, 1, NULL, 0, 'auction:brokers' FROM auction_house_items;
INSERT INTO item_conditions
SELECT 'auction:' || rowid, 0, 0, 0, 'level_sim', 'actor_level', NULL, NULL, 'sim', NULL,
    min_sim_level, max_sim_level, 1, 1, 'availability' FROM auction_house_items;
INSERT INTO item_conditions
SELECT 'auction:' || rowid, 1, 0, 0, 'level_player', 'actor_level', NULL, NULL, 'player', NULL,
    min_player_level, max_player_level, 1, 1, 'availability' FROM auction_house_items
WHERE min_player_level IS NOT NULL OR max_player_level IS NOT NULL;

-- Only current, final, player-visible sources are persisted.
INSERT INTO item_sources VALUES
    ('ui:fixture', 'item:fixture relic', 'ui_grant', 'native:reliquary', NULL, NULL, 'room:1', 'furniture_reward',
    'unknown', NULL, NULL, NULL, 'bounded', 1, 2, 1.5, 0, 'room:fixture'),
    ('fishing:bonus', 'item:fixture fish', 'fishing', NULL, NULL, NULL, NULL, 'fishing_global_replacement',
    'exact', 1.25, 1.25, 'per_successful_catch', 'exact', 1, 1, NULL, 0, NULL);
INSERT INTO item_conditions VALUES
    ('ui:fixture', 0, 0, 0, 'eligibility', 'quest_done', 'quest:vendor-unlock', 'quest:1', 'player', 'complete', 1, 2, 1, 0, 'availability'),
    ('ui:fixture', 0, 1, 0, 'eligibility', 'actor_class', 'class:paladin', 'class:1', 'player', 'Paladin', NULL, NULL, 1, 1, 'availability'),
    ('drop:character:fixture enemy:item:fixture drop', 0, 0, 0, 'ownership', 'item_held',
    'item:fixture key', NULL, 'player', 'inventory', 1, NULL, 1, 1, 'operation_input');

-- Enhanced local catches retain their own time gate alongside the one global source.
UPDATE item_sources SET probability_min = 7.1875, probability_max = 7.1875 WHERE source_key = 'fishing:1';
INSERT INTO item_sources
SELECT 'fishing:overlap-night', item_stable_key, kind, source_stable_key, source_group_key, source_copy_stable_key,
    'NightFishable', mechanic, probability_kind, 7.583333333333333, 7.583333333333333,
    probability_basis, quantity_kind, quantity_min, quantity_max, expected_quantity, guaranteed, NULL
FROM item_sources WHERE source_key = 'fishing:1';
INSERT INTO item_conditions VALUES
    ('fishing:overlap-night', 0, 0, 0, 'time', 'time_of_day', NULL, NULL, 'player', 'night', NULL, NULL, 1, 1, 'availability');

-- Place sets are shared by sources with the same actual copy or fixed marker.
UPDATE item_sources SET place_set_key = 'copy:' || source_copy_stable_key
WHERE source_copy_stable_key IS NOT NULL AND (
    EXISTS (SELECT 1 FROM map_character_spawns p WHERE p.character_stable_key = item_sources.source_copy_stable_key)
    OR EXISTS (SELECT 1 FROM treasure_chest_possible_spawns t WHERE t.chest_character_stable_key = item_sources.source_copy_stable_key));
UPDATE item_sources SET place_set_key = 'fixed:' || source_stable_key
WHERE kind IN ('mining', 'fishing', 'item_bag') AND source_stable_key IS NOT NULL;
UPDATE item_sources SET place_set_key = 'quest:vendor-unlock'
WHERE kind = 'quest_reward' AND source_stable_key = 'quest:vendor-unlock';
INSERT INTO item_places
SELECT DISTINCT a.place_set_key, 'placement:' || p.spawn_point_stable_key, 'spawn', p.scene, z.stable_key,
    p.spawn_point_stable_key, p.x, p.y, p.z, NULL, NULL, p.character_stable_key, '[]'
FROM item_sources a JOIN map_character_spawns p ON p.character_stable_key = a.source_copy_stable_key
JOIN zones z ON z.scene_name = p.scene;
INSERT INTO item_places
SELECT DISTINCT a.place_set_key, 'site:' || t.stable_key, 'possible_treasure', t.scene, z.stable_key,
    t.stable_key, t.x, t.y, t.z, s.player_level_min, s.player_level_max, a.source_copy_stable_key, '[]'
FROM item_sources a JOIN treasure_chest_possible_spawns s ON s.chest_character_stable_key = a.source_copy_stable_key
JOIN treasure_locations t ON t.stable_key = s.treasure_location_stable_key JOIN zones z ON z.scene_name = t.scene;
INSERT INTO item_places
SELECT DISTINCT a.place_set_key, 'fixed:' || p.stable_key, 'fixed', p.scene, z.stable_key, p.stable_key,
    p.x, p.y, p.z, NULL, NULL, NULL, '[]'
FROM item_sources a JOIN (
    SELECT stable_key, scene, x, y, z FROM mining_nodes UNION ALL
    SELECT stable_key, scene, x, y, z FROM waters UNION ALL
    SELECT stable_key, scene, x, y, z FROM item_bags
) p ON p.stable_key = a.source_stable_key JOIN zones z ON z.scene_name = p.scene;
INSERT INTO item_places VALUES
    ('room:fixture', 'room:unlocated', 'unlocated', NULL, NULL, NULL, NULL, NULL, NULL, 10, 35,
    NULL, '["zone-line:stowaway-fixture"]');
INSERT INTO item_place_conditions VALUES
    ('room:fixture', 'room:unlocated', 0, 0, 0, 'room', 'room_furnished', 'item:furniture - wood training',
    'room:1', 'player', 'placed', NULL, NULL, 1, 1, 'availability'),
    ('room:fixture', 'room:unlocated', 1, 0, 0, 'claim', 'account_state', 'account_state:reliquary_claimed',
    NULL, 'account', 'false', NULL, NULL, 1, 1, 'availability');
INSERT INTO item_places
SELECT DISTINCT 'auction:brokers', 'broker:' || b.character_stable_key, 'interaction', p.scene, z.stable_key,
    p.spawn_point_stable_key, p.x, p.y, p.z, NULL, NULL, b.character_stable_key, '[]'
FROM auction_house_brokers b JOIN map_character_spawns p ON p.character_stable_key = b.character_stable_key
JOIN zones z ON z.scene_name = p.scene;
INSERT INTO item_places
SELECT 'auction:brokers', 'broker:' || b.character_stable_key, 'interaction', NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, b.character_stable_key, '[]'
FROM auction_house_brokers b WHERE NOT EXISTS (
    SELECT 1 FROM map_character_spawns p WHERE p.character_stable_key = b.character_stable_key);
INSERT INTO item_places
SELECT 'quest:vendor-unlock', 'turnin:' || p.spawn_point_stable_key, 'interaction', p.scene, z.stable_key,
    p.spawn_point_stable_key, p.x, p.y, p.z, NULL, NULL, p.character_stable_key, '[]'
FROM map_character_spawns p JOIN zones z ON z.scene_name = p.scene
WHERE p.character_stable_key = 'character:breena carpenter';
INSERT INTO item_places
SELECT DISTINCT a.place_set_key, 'zone:' || z.stable_key, 'mechanic_zone', NULL, z.stable_key,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, '[]'
FROM item_sources a JOIN zones z ON z.stable_key = a.variant_key WHERE a.kind = 'item_conversion';
