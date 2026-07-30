PRAGMA foreign_keys = ON;

-- Minimum clean-database surface read by RepositoryBase and the prerender loaders.
CREATE TABLE zones (
    stable_key TEXT PRIMARY KEY,
    scene_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    is_map_visible INTEGER NOT NULL,
    north_bearing REAL NOT NULL
);

CREATE TABLE classes (
    class_name TEXT PRIMARY KEY
);

CREATE TABLE quests (
    stable_key TEXT PRIMARY KEY
);

CREATE TABLE items (
    stable_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    wiki_page_name TEXT,
    item_icon_name TEXT,
    item_value INTEGER NOT NULL,
    is_map_visible INTEGER NOT NULL
);

CREATE TABLE characters (
    stable_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    npc_name TEXT NOT NULL,
    wiki_page_name TEXT,
    level INTEGER NOT NULL,
    is_vendor INTEGER NOT NULL,
    has_dialog INTEGER NOT NULL,
    invulnerable INTEGER NOT NULL,
    is_common INTEGER NOT NULL,
    is_rare INTEGER NOT NULL,
    is_unique INTEGER NOT NULL,
    is_friendly INTEGER NOT NULL
);

CREATE TABLE spells (
    pet_to_summon_stable_key TEXT REFERENCES characters(stable_key)
);

CREATE TABLE character_deduplications (
    group_key TEXT NOT NULL,
    member_stable_key TEXT NOT NULL REFERENCES characters(stable_key),
    is_map_visible INTEGER NOT NULL,
    PRIMARY KEY (group_key, member_stable_key)
);

CREATE TABLE map_character_spawns (
    character_stable_key TEXT NOT NULL REFERENCES characters(stable_key),
    spawn_point_stable_key TEXT NOT NULL,
    scene TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    spawn_delay_4 REAL,
    is_enabled INTEGER NOT NULL,
    night_spawn INTEGER NOT NULL,
    random_wander_range REAL,
    loop_patrol INTEGER NOT NULL,
    spawn_chance REAL,
    source_script TEXT,
    event_x REAL,
    event_y REAL,
    event_z REAL
);

CREATE TABLE spawn_point_patrol_points (
    spawn_point_stable_key TEXT NOT NULL,
    sequence_index INTEGER NOT NULL,
    x REAL NOT NULL,
    z REAL NOT NULL,
    PRIMARY KEY (spawn_point_stable_key, sequence_index)
);

CREATE TABLE achievement_triggers (
    stable_key TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    achievement_name TEXT NOT NULL
);

CREATE TABLE doors (
    stable_key TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    key_item_stable_key TEXT REFERENCES items(stable_key)
);

CREATE TABLE forges (
    stable_key TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL
);

CREATE TABLE item_bags (
    stable_key TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    item_stable_key TEXT NOT NULL REFERENCES items(stable_key),
    respawns INTEGER NOT NULL,
    respawn_timer REAL NOT NULL
);

CREATE TABLE mining_nodes (
    stable_key TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    respawn_time REAL NOT NULL
);

CREATE TABLE mining_node_items (
    mining_node_stable_key TEXT NOT NULL REFERENCES mining_nodes(stable_key),
    item_stable_key TEXT NOT NULL REFERENCES items(stable_key),
    drop_chance REAL NOT NULL,
    PRIMARY KEY (mining_node_stable_key, item_stable_key)
);

CREATE TABLE secret_passages (
    stable_key TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    type TEXT NOT NULL,
    is_excluded INTEGER NOT NULL
);

CREATE TABLE teleports (
    stable_key TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    teleport_item_stable_key TEXT NOT NULL REFERENCES items(stable_key)
);

CREATE TABLE treasure_locations (
    stable_key TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL
);

CREATE TABLE waters (
    stable_key TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    width REAL NOT NULL,
    depth REAL NOT NULL
);

CREATE TABLE water_fishables (
    water_stable_key TEXT NOT NULL REFERENCES waters(stable_key),
    type TEXT NOT NULL,
    item_stable_key TEXT NOT NULL REFERENCES items(stable_key),
    drop_chance REAL NOT NULL,
    PRIMARY KEY (water_stable_key, type, item_stable_key)
);

CREATE TABLE wishing_wells (
    stable_key TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL
);

CREATE TABLE zone_lines (
    stable_key TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    is_enabled INTEGER NOT NULL,
    landing_position_x REAL NOT NULL,
    landing_position_y REAL NOT NULL,
    landing_position_z REAL NOT NULL,
    destination_zone_stable_key TEXT NOT NULL REFERENCES zones(stable_key)
);

CREATE TABLE zone_atlas_entries (
    zone_name TEXT PRIMARY KEY,
    level_range_low INTEGER,
    level_range_high INTEGER
);

CREATE TABLE loot_drops (
    character_stable_key TEXT NOT NULL REFERENCES characters(stable_key),
    item_stable_key TEXT NOT NULL REFERENCES items(stable_key),
    drop_probability REAL NOT NULL,
    PRIMARY KEY (character_stable_key, item_stable_key)
);

CREATE TABLE character_vendor_items (
    character_stable_key TEXT NOT NULL REFERENCES characters(stable_key),
    item_stable_key TEXT NOT NULL REFERENCES items(stable_key),
    PRIMARY KEY (character_stable_key, item_stable_key)
);

CREATE TABLE character_vendor_quest_unlocks (
    character_stable_key TEXT NOT NULL REFERENCES characters(stable_key),
    quest_stable_key TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, quest_stable_key)
);

CREATE TABLE quest_variants (
    quest_stable_key TEXT NOT NULL,
    unlock_item_for_vendor_stable_key TEXT REFERENCES items(stable_key)
);

-- Read by the shared site footer through `getDataProvenance`, so the (app)
-- layout load fails and every page 500s during prerender without it.
CREATE TABLE code_facts_meta (
    assembly_sha256 TEXT,
    extracted_at TEXT,
    game_build_id TEXT,
    game_build_published_at TEXT
);

-- The world map builds every registered zone, so every MAPS key needs a bearing.
INSERT INTO zones (stable_key, scene_name, display_name, is_map_visible, north_bearing) VALUES
    ('zone:abyssal', 'Abyssal', 'Abyssal Lake', 1, 0),
    ('zone:azure', 'Azure', 'Port Azure', 1, 0),
    ('zone:azynthi', 'Azynthi', 'Azynthi Garden Rift', 1, 0),
    ('zone:azynthi-clear', 'AzynthiClear', 'Azynthi Garden', 1, 0),
    ('zone:blight', 'Blight', 'The Blight', 1, 0),
    ('zone:blooming-sepulcher', 'BloomingSepulcher', 'Blooming Sepulcher', 1, 0),
    ('zone:bonepits', 'Bonepits', 'The Bonepits', 1, 0),
    ('zone:brake', 'Brake', 'Faerie Brake', 1, 0),
    ('zone:braxonia', 'Braxonia', 'Fallen Braxonia', 1, 0),
    ('zone:braxonian', 'Braxonian', 'Braxonian Desert', 1, 0),
    ('zone:detention', 'Detention', 'Prison', 1, 0),
    ('zone:dusken-portal', 'DuskenPortal', 'Mysterious Portal', 1, 0),
    ('zone:duskenlight', 'Duskenlight', 'The Duskenlight Coast', 1, 0),
    ('zone:elderstone', 'Elderstone', 'The Elderstone Mines', 1, 0),
    ('zone:fernalla-field', 'FernallaField', 'Fernalla Revival Plains', 1, 0),
    ('zone:fernalla-portal', 'FernallaPortal', 'Mysterious Portal', 1, 0),
    ('zone:hidden', 'Hidden', 'Hidden Hills', 1, 0),
    ('zone:jaws', 'Jaws', 'Jaws of Sivakaya', 1, 0),
    ('zone:krakengard', 'Krakengard', 'Old Krakengard', 1, 0),
    ('zone:loomingwood', 'Loomingwood', 'Loomingwood Forest', 1, 0),
    ('zone:malaroth', 'Malaroth', 'Malaroth Nesting Grounds', 1, 0),
    ('zone:plane-of-brax', 'PlaneOfBrax', 'Brax Plane of Elements', 1, 0),
    ('zone:plane-of-fernalla', 'PlaneOfFernalla', 'Plane of the Willow', 1, 0),
    ('zone:plane-of-soluna', 'PlaneOfSoluna', 'Soluna Celestial Plane', 1, 0),
    ('zone:plane-of-vitheo', 'PlaneOfVitheo', 'Vitheo Plane of Valor', 1, 0),
    ('zone:priel-plateau', 'PrielPlateau', 'Prielian Cascade', 1, 0),
    ('zone:reliquary', 'Reliquary', 'Reliquary Hall', 1, 0),
    ('zone:ripper', 'Ripper', 'Ripper Keep', 1, 0),
    ('zone:ripper-portal', 'RipperPortal', 'Mysterious Portal', 1, 0),
    ('zone:rockshade', 'Rockshade', 'Rockshade Hold', 1, 0),
    ('zone:rottenfoot', 'Rottenfoot', 'Rottenfoot', 1, 0),
    ('zone:salted-strand', 'SaltedStrand', 'Blacksalt Strand', 1, 0),
    ('zone:shivering-step', 'ShiveringStep', 'Shivering Step', 1, 0),
    ('zone:shivering-tomb', 'ShiveringTomb', 'Shivering Tomb', 1, 0),
    ('zone:shivering-tomb-2', 'ShiveringTomb2', 'Shivering Tomb', 1, 0),
    ('zone:silkengrass', 'Silkengrass', 'Silkengrass Meadowlands', 1, 0),
    ('zone:soluna', 'Soluna', 'Soluna Landing', 1, 0),
    ('zone:stowaway', 'Stowaway', 'Stowaway Step', 1, 0),
    ('zone:stowaway-portal', 'StowawayPortal', 'Secluded Sanctuary', 1, 0),
    ('zone:summer-event', 'SummerEvent', 'Bellwain Island', 1, 0),
    ('zone:tutorial', 'Tutorial', 'Island Tomb', 1, 0),
    ('zone:undercity', 'Undercity', 'Lost Cellar', 1, 0),
    ('zone:underspine', 'Underspine', 'Underspine Hollow', 1, 0),
    ('zone:vitheo', 'Vitheo', 'Vitheo Watch', 1, 0),
    ('zone:vitheos-end', 'VitheosEnd', 'Vitheo Rest', 1, 0),
    ('zone:willowwatch', 'Willowwatch', 'Willowwatch Ridge', 1, 0),
    ('zone:windwashed', 'Windwashed', 'Windwashed Pass', 1, 0);

INSERT INTO classes (class_name) VALUES ('Nightblade'), ('Paladin');
INSERT INTO quests (stable_key) VALUES ('quest:vendor-unlock'), ('quest:fixture-secondary');

INSERT INTO items (
    stable_key, display_name, wiki_page_name, item_icon_name, item_value, is_map_visible
) VALUES
    ('item:fixture key', 'Fixture Key', 'Fixture Key', 'fixture_key', 10, 1),
    ('item:fixture ore', 'Fixture Ore', 'Fixture Ore', 'fixture_ore', 20, 1),
    ('item:fixture fish', 'Fixture Fish', 'Fixture Fish', 'fixture_fish', 5, 1),
    ('item:fixture bag', 'Fixture Bag Item', 'Fixture Bag Item', 'fixture_bag', 15, 1),
    ('item:fixture drop', 'Fixture Drop', 'Fixture Drop', 'fixture_drop', 30, 1),
    ('item:furniture - enchanted smithy', 'Enchanted Smithy', 'Enchanted Smithy', 'enchanted_smithy', 250, 1);

-- A loot table larger than any cap a query might reintroduce. These carry no
-- wiki page, so they stay out of item search and the searchable-item counts
-- while still exercising the drop list.
INSERT INTO items (
    stable_key, display_name, wiki_page_name, item_icon_name, item_value, is_map_visible
) VALUES
    ('item:hoard 01', 'Hoard Item 01', NULL, NULL, 1, 0),
    ('item:hoard 02', 'Hoard Item 02', NULL, NULL, 1, 0),
    ('item:hoard 03', 'Hoard Item 03', NULL, NULL, 1, 0),
    ('item:hoard 04', 'Hoard Item 04', NULL, NULL, 1, 0),
    ('item:hoard 05', 'Hoard Item 05', NULL, NULL, 1, 0),
    ('item:hoard 06', 'Hoard Item 06', NULL, NULL, 1, 0),
    ('item:hoard 07', 'Hoard Item 07', NULL, NULL, 1, 0),
    ('item:hoard 08', 'Hoard Item 08', NULL, NULL, 1, 0),
    ('item:hoard 09', 'Hoard Item 09', NULL, NULL, 1, 0),
    ('item:hoard 10', 'Hoard Item 10', NULL, NULL, 1, 0),
    ('item:hoard 11', 'Hoard Item 11', NULL, NULL, 1, 0);

INSERT INTO characters (
    stable_key, display_name, npc_name, wiki_page_name, level, is_vendor, has_dialog,
    invulnerable, is_common, is_rare, is_unique, is_friendly
) VALUES
    ('character:breena carpenter', 'Breena Carpenter', 'Breena Carpenter', 'Breena Carpenter', 5, 1, 1, 0, 1, 0, 0, 1),
    ('character:fixture enemy', 'Fixture Enemy', 'Fixture Enemy', 'Fixture Enemy', 7, 0, 0, 0, 0, 0, 1, 0),
    ('character:runtime enemy', 'Runtime Enemy', 'Runtime Enemy', 'Runtime Enemy', 12, 0, 0, 0, 0, 1, 0, 0);

INSERT INTO character_deduplications (group_key, member_stable_key, is_map_visible) VALUES
    ('character-group:breena', 'character:breena carpenter', 1),
    ('character-group:fixture-enemy', 'character:fixture enemy', 1),
    ('character-group:runtime-enemy', 'character:runtime enemy', 1);

INSERT INTO map_character_spawns (
    character_stable_key, spawn_point_stable_key, scene, x, y, z, spawn_delay_4,
    is_enabled, night_spawn, random_wander_range, loop_patrol, spawn_chance,
    source_script, event_x, event_y, event_z
) VALUES
    ('character:breena carpenter', 'spawn:stowaway-breena', 'Stowaway', 200, 0, 300, 30, 1, 0, 0, 0, 100, NULL, NULL, NULL, NULL),
    ('character:fixture enemy', 'spawn:stowaway-enemy', 'Stowaway', 220, 0, 320, 45, 1, 0, 5, 0, 100, NULL, NULL, NULL, NULL);

INSERT INTO achievement_triggers (stable_key, scene, x, y, z, achievement_name) VALUES
    ('achievement:stowaway-fixture', 'Stowaway', 240, 0, 340, 'Fixture Achievement');
INSERT INTO doors (stable_key, scene, x, y, z, key_item_stable_key) VALUES
    ('door:stowaway-fixture', 'Stowaway', 250, 0, 350, 'item:fixture key');
INSERT INTO forges (stable_key, scene, x, y, z) VALUES
    ('forge:stowaway-fixture', 'Stowaway', 260, 0, 360);
INSERT INTO item_bags (stable_key, scene, x, y, z, item_stable_key, respawns, respawn_timer) VALUES
    ('bag:stowaway-fixture', 'Stowaway', 270, 0, 370, 'item:fixture bag', 1, 60);
INSERT INTO mining_nodes (stable_key, scene, x, y, z, respawn_time) VALUES
    ('mining:stowaway-fixture', 'Stowaway', 280, 0, 380, 90);
INSERT INTO mining_node_items (mining_node_stable_key, item_stable_key, drop_chance) VALUES
    ('mining:stowaway-fixture', 'item:fixture ore', 75);
INSERT INTO secret_passages (stable_key, scene, x, y, z, type, is_excluded) VALUES
    ('passage:stowaway-fixture', 'Stowaway', 290, 0, 390, 'HiddenDoor', 0);
INSERT INTO teleports (stable_key, scene, x, y, z, teleport_item_stable_key) VALUES
    ('teleport:stowaway-fixture', 'Stowaway', 300, 0, 400, 'item:fixture key');
INSERT INTO treasure_locations (stable_key, scene, x, y, z) VALUES
    ('treasure:stowaway-fixture', 'Stowaway', 310, 0, 410);
INSERT INTO waters (stable_key, scene, x, y, z, width, depth) VALUES
    ('water:stowaway-fixture', 'Stowaway', 320, 0, 420, 20, 20);
INSERT INTO water_fishables (water_stable_key, type, item_stable_key, drop_chance) VALUES
    ('water:stowaway-fixture', 'DayFishable', 'item:fixture fish', 60);
INSERT INTO wishing_wells (stable_key, scene, x, y, z) VALUES
    ('well:stowaway-fixture', 'Stowaway', 330, 0, 430);
INSERT INTO zone_lines (
    stable_key, scene, x, y, z, is_enabled, landing_position_x, landing_position_y,
    landing_position_z, destination_zone_stable_key
) VALUES
    ('zone-line:stowaway-fixture', 'Stowaway', 340, 0, 440, 1, 0, 0, 0, 'zone:stowaway-portal');
INSERT INTO zone_atlas_entries (zone_name, level_range_low, level_range_high) VALUES
    ('StowawayPortal', 5, 8);

INSERT INTO loot_drops (character_stable_key, item_stable_key, drop_probability) VALUES
    ('character:fixture enemy', 'item:fixture drop', 25);

-- Twelve drops in total for one character, so a reinstated `LIMIT 10` fails
-- instead of quietly hiding the tail. Two share a probability to pin the
-- name tiebreaker that keeps rendering order stable.
INSERT INTO loot_drops (character_stable_key, item_stable_key, drop_probability) VALUES
    ('character:fixture enemy', 'item:hoard 01', 90),
    ('character:fixture enemy', 'item:hoard 02', 80),
    ('character:fixture enemy', 'item:hoard 03', 70),
    ('character:fixture enemy', 'item:hoard 04', 60),
    ('character:fixture enemy', 'item:hoard 05', 50),
    ('character:fixture enemy', 'item:hoard 06', 40),
    ('character:fixture enemy', 'item:hoard 07', 30),
    ('character:fixture enemy', 'item:hoard 08', 20),
    ('character:fixture enemy', 'item:hoard 09', 15),
    ('character:fixture enemy', 'item:hoard 10', 10),
    ('character:fixture enemy', 'item:hoard 11', 25);
INSERT INTO character_vendor_quest_unlocks (character_stable_key, quest_stable_key) VALUES
    ('character:breena carpenter', 'quest:vendor-unlock');
INSERT INTO quest_variants (quest_stable_key, unlock_item_for_vendor_stable_key) VALUES
    ('quest:vendor-unlock', 'item:furniture - enchanted smithy');

-- A build id and publish time distinct from any real one, so a fixture render
-- can never be mistaken for a render of the live data.
INSERT INTO code_facts_meta (assembly_sha256, extracted_at, game_build_id, game_build_published_at) VALUES
    ('fixture-sha', '2020-01-02T03:04:05+00:00', '10000001', '2020-01-01T00:00:00+00:00');
