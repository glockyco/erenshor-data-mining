INSERT INTO characters (stable_key, display_name, npc_name, wiki_page_name, level,
    is_vendor, has_dialog, invulnerable, can_be_damaged, encounter_tier, is_friendly) VALUES
    ('character:eligibility ward', 'Ward', 'Ward', NULL, 99, 0, 0, 1, 0, 'enemy', 0),
    ('character:eligibility stardust', 'Stardust', 'Stardust', NULL, 28, 0, 0, 1, 1, 'enemy', 0),
    ('character:eligibility shadow', 'Warded Shadow', 'Warded Shadow', NULL, 34, 0, 0, 1, 1, 'enemy', 0),
    ('character:eligibility evadne', 'Evadne', 'Evadne', NULL, 35, 0, 0, 1, 1, 'enemy', 0),
    ('character:copygroup 0 representative', 'Shared Sentinel', 'Shared Sentinel', NULL, 99, 0, 0, 1, 0, 'boss', 0),
    ('character:copygroup 1 released', 'Shared Sentinel', 'Shared Sentinel', NULL, 24, 0, 0, 1, 1, 'boss', 0),
    ('character:copygroup 2 vulnerable', 'Shared Sentinel', 'Shared Sentinel', NULL, 26, 0, 0, 0, 1, 'boss', 0);
INSERT INTO character_deduplications (group_key, member_stable_key, is_map_visible) VALUES
    ('group:eligibility ward', 'character:eligibility ward', 1),
    ('group:eligibility stardust', 'character:eligibility stardust', 1),
    ('group:eligibility shadow', 'character:eligibility shadow', 1),
    ('group:eligibility evadne', 'character:eligibility evadne', 1),
    ('group:eligibility shared', 'character:copygroup 0 representative', 1),
    ('group:eligibility shared', 'character:copygroup 1 released', 1),
    ('group:eligibility shared', 'character:copygroup 2 vulnerable', 1);
INSERT INTO map_character_spawns (character_stable_key, spawn_point_stable_key, scene, x, y, z,
    spawn_delay_4, is_enabled, night_spawn, random_wander_range, loop_patrol, spawn_chance) VALUES
    ('character:eligibility ward', 'spawn:eligibility ward', 'Reliquary', 100, 0, 100, 30, 1, 0, 0, 0, 100),
    ('character:eligibility stardust', 'spawn:eligibility stardust', 'Reliquary', 110, 0, 100, 30, 1, 0, 0, 0, 100),
    ('character:eligibility shadow', 'spawn:eligibility shadow', 'Reliquary', 120, 0, 100, 30, 1, 0, 0, 0, 100),
    ('character:eligibility evadne', 'spawn:eligibility evadne', 'Reliquary', 130, 0, 100, 30, 1, 0, 0, 0, 100),
    ('character:copygroup 0 representative', 'spawn:eligibility immune copy', 'Reliquary', 140, 0, 100, 30, 1, 0, 0, 0, 100),
    ('character:copygroup 1 released', 'spawn:eligibility shared', 'Reliquary', 150, 0, 100, 30, 1, 0, 0, 0, 50),
    ('character:copygroup 2 vulnerable', 'spawn:eligibility shared', 'Reliquary', 150, 0, 100, 30, 1, 0, 0, 0, 50);
