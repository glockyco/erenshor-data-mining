"""Clean SQLite writer for the Layer 2 processor.

Creates the clean database with a snake_case schema that mirrors the raw
Unity export but adds display_name, wiki_page_name, image_name, and
explicit visibility flags for consumers (wiki/map filters run at query
time, not by dropping rows during processing).

The Writer is the only place in the codebase that defines the clean DB
schema.  All consumers (wiki, sheets, map) read from this schema.

Design rules:
- Every table name is the snake_case equivalent of the raw PascalCase name.
- Every column name is snake_case.
- The ``characters`` table gains new columns not present in the raw DB:
  ``display_name``, ``wiki_page_name``, ``image_name``,
  ``is_wiki_generated``, and ``is_map_visible``.
- ``character_deduplications`` stores dedup group membership.
- All other tables are structural copies of the raw schema with renamed
  columns only.
- PRAGMA foreign_keys is ON during writes.
- VACUUM + ANALYZE runs after all data is inserted.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- -------------------------------------------------------------------------
-- World / placement tables
-- -------------------------------------------------------------------------

CREATE TABLE weather_trends (
    stable_key TEXT PRIMARY KEY NOT NULL,
    scene TEXT NOT NULL,
    is_enabled INTEGER NOT NULL CHECK (is_enabled IN (0, 1)),
    max_natural_cloudy REAL NOT NULL,
    max_natural_rainy REAL NOT NULL
);

CREATE TABLE world_states (
    stable_key TEXT PRIMARY KEY NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('raining')),
    zone_stable_key TEXT NOT NULL REFERENCES zones(stable_key),
    uses_sun INTEGER NOT NULL CHECK (uses_sun IN (0, 1)),
    natural_rain_can_start INTEGER NOT NULL CHECK (natural_rain_can_start IN (0, 1))
);

CREATE TABLE world_state_producers (
    state_stable_key TEXT NOT NULL REFERENCES world_states(stable_key),
    mechanism TEXT NOT NULL CHECK (mechanism IN ('natural_weather', 'spell')),
    spell_stable_key TEXT REFERENCES spells(stable_key),
    UNIQUE (state_stable_key, mechanism, spell_stable_key),
    CHECK ((mechanism = 'spell') = (spell_stable_key IS NOT NULL))
);

CREATE TABLE weather_spell_effects (
    spell_stable_key TEXT PRIMARY KEY NOT NULL REFERENCES spells(stable_key),
    weight_goal REAL NOT NULL,
    since_rain REAL,
    cloud_amount REAL NOT NULL
);

CREATE TABLE teleports (
    stable_key                  TEXT PRIMARY KEY NOT NULL,
    scene                       TEXT,
    x                           REAL,
    y                           REAL,
    z                           REAL,
    teleport_item_stable_key    TEXT
);

CREATE TABLE wishing_wells (
    stable_key  TEXT PRIMARY KEY NOT NULL,
    scene       TEXT,
    x           REAL,
    y           REAL,
    z           REAL
);

CREATE TABLE achievement_triggers (
    stable_key          TEXT PRIMARY KEY NOT NULL,
    scene               TEXT,
    x                   REAL,
    y                   REAL,
    z                   REAL,
    achievement_name    TEXT
);

CREATE TABLE doors (
    stable_key              TEXT PRIMARY KEY NOT NULL,
    scene                   TEXT,
    x                       REAL,
    y                       REAL,
    z                       REAL,
    key_item_stable_key     TEXT
);

CREATE TABLE forges (
    stable_key  TEXT PRIMARY KEY NOT NULL,
    scene       TEXT,
    x           REAL,
    y           REAL,
    z           REAL
);

CREATE TABLE item_bags (
    stable_key      TEXT PRIMARY KEY NOT NULL,
    scene           TEXT,
    x               REAL,
    y               REAL,
    z               REAL,
    item_stable_key TEXT,
    respawns        INTEGER,
    respawn_timer   REAL
);

CREATE TABLE mining_nodes (
    stable_key      TEXT PRIMARY KEY NOT NULL,
    scene           TEXT,
    x               REAL,
    y               REAL,
    z               REAL,
    npc_name        TEXT,
    respawn_time    REAL,
    common_count    INTEGER,
    rare_count      INTEGER,
    legend_count    INTEGER
);

CREATE TABLE mining_node_items (
    mining_node_stable_key  TEXT NOT NULL,
    item_stable_key         TEXT NOT NULL,
    drop_chance             REAL,
    PRIMARY KEY (mining_node_stable_key, item_stable_key)
);

CREATE TABLE treasure_locations (
    stable_key  TEXT PRIMARY KEY NOT NULL,
    scene       TEXT,
    x           REAL,
    y           REAL,
    z           REAL
);

CREATE TABLE waters (
    stable_key  TEXT PRIMARY KEY NOT NULL,
    scene       TEXT,
    x           REAL,
    y           REAL,
    z           REAL,
    width       REAL,
    height      REAL,
    depth       REAL
);

CREATE TABLE water_fishables (
    water_stable_key    TEXT NOT NULL,
    type                TEXT NOT NULL,
    item_stable_key     TEXT NOT NULL,
    drop_chance         REAL,
    PRIMARY KEY (water_stable_key, type, item_stable_key)
);

CREATE TABLE zone_lines (
    stable_key                  TEXT PRIMARY KEY NOT NULL,
    scene                       TEXT,
    x                           REAL,
    y                           REAL,
    z                           REAL,
    object_is_active            INTEGER,
    component_is_enabled        INTEGER,
    collider_is_trigger         INTEGER,
    has_enabled_trigger         INTEGER,
    is_enabled                  INTEGER,
    display_text                TEXT,
    destination_zone_stable_key TEXT,
    landing_position_x          REAL,
    landing_position_y          REAL,
    landing_position_z          REAL,
    remove_party                INTEGER,
    use_sun_in_new_zone          INTEGER
);

CREATE TABLE zone_line_destination_contexts (
    zone_line_stable_key TEXT PRIMARY KEY NOT NULL REFERENCES zone_lines(stable_key),
    kind TEXT NOT NULL CHECK (kind IN ('stored_return')),
    destination_state_key TEXT NOT NULL,
    landing_state_key TEXT NOT NULL,
    source_key TEXT NOT NULL
);

CREATE TABLE planning_portal_slots (
    zone_line_stable_key TEXT NOT NULL REFERENCES zone_lines(stable_key),
    slot TEXT NOT NULL,
    slot_kind TEXT NOT NULL CHECK (slot_kind IN ('dedicated', 'rune')),
    PRIMARY KEY (zone_line_stable_key, slot)
);

-- Zoning needs both the trigger callback and the enabled FixedUpdate transition.
CREATE VIEW zone_lines_with_zoning_capability AS
    SELECT * FROM zone_lines
    WHERE component_is_enabled = 1
      AND collider_is_trigger = 1
      AND has_enabled_trigger = 1;

-- One row per atom of a gate. A subject is available when every gate on it
-- holds, and a gate holds when every atom of one of its groups holds. An atom
-- of kind 'never' marks a gate that no game state satisfies, such as a door
-- whose key the player cannot obtain. item_stable_key names the item of a
-- vendor_item subject, and atom_slot the room slot of a room_furnished atom.
CREATE TABLE gate_conditions (
    subject_kind            TEXT NOT NULL CHECK (subject_kind IN (
                                'zone_line', 'character', 'spawn_point', 'vendor_item', 'item_bag',
                                'ui_item_access_target', 'door'
                            )),
    subject_stable_key      TEXT NOT NULL,
    item_stable_key         TEXT,
    gate                    TEXT NOT NULL,
    group_index             INTEGER NOT NULL,
    atom_kind               TEXT NOT NULL CHECK (atom_kind IN (
                                'quest_done', 'quest_not_done', 'item_held', 'key_held', 'room_furnished',
                                'planning_slot_item', 'encounter_won', 'world_state', 'never'
                            )),
    atom_stable_key         TEXT NOT NULL,
    atom_slot               TEXT,
    atom_quantity           INTEGER CHECK (
                                atom_quantity IS NULL OR (atom_kind = 'encounter_won' AND atom_quantity > 0)
                            ),
    UNIQUE (subject_kind, subject_stable_key, item_stable_key, gate, group_index,
            atom_kind, atom_stable_key, atom_slot, atom_quantity)
);

-- Zone lines through which alone a target can be reached, from the reviewed
-- [[entries]] of barriers.toml. A target without rows is reachable from every
-- zone line into its scene.
CREATE TABLE target_entries (
    target_kind             TEXT NOT NULL CHECK (target_kind IN ('character', 'spawn_point', 'item_bag')),
    target_stable_key       TEXT NOT NULL,
    zone_line_stable_key    TEXT NOT NULL REFERENCES zone_lines (stable_key),
    PRIMARY KEY (target_stable_key, zone_line_stable_key)
);

-- One row per record of barriers.toml. Gates that a barrier causes are named
-- by barrier_key, its first object.
CREATE TABLE barriers (
    barrier_key     TEXT PRIMARY KEY NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('door', 'removed', 'moved', 'guardians')),
    name            TEXT NOT NULL
);

-- Classified controllers that finish a quest themselves, such as the gaze
-- statue of Jaws of Sivakaya. event_key is the controller's exported source key.
CREATE TABLE scripted_events (
    event_key           TEXT PRIMARY KEY NOT NULL,
    quest_stable_key    TEXT NOT NULL REFERENCES quests (stable_key),
    rule                TEXT NOT NULL,
    zone_stable_key     TEXT NOT NULL REFERENCES zones (stable_key),
    note                TEXT NOT NULL
);

-- When a scripted event can happen: OR of groups, AND within a group.
CREATE TABLE scripted_event_conditions (
    event_key           TEXT NOT NULL REFERENCES scripted_events (event_key),
    group_index         INTEGER NOT NULL,
    atom_index          INTEGER NOT NULL,
    atom_kind           TEXT NOT NULL,
    atom_stable_key     TEXT NOT NULL,
    PRIMARY KEY (event_key, group_index, atom_index)
);

CREATE TABLE game_constants (
    key         TEXT PRIMARY KEY NOT NULL,
    value       TEXT,
    value_type  TEXT,
    description TEXT
);

-- -------------------------------------------------------------------------
-- Code facts (hardcoded game logic extracted from the assembly)
-- -------------------------------------------------------------------------

CREATE TABLE code_facts (
    fact_id     TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT,
    value_type  TEXT,
    PRIMARY KEY (fact_id, key)
);

CREATE TABLE code_facts_meta (
    assembly_sha256       TEXT,
    extracted_at          TEXT,
    game_build_id         TEXT,
    game_build_published_at TEXT
);

CREATE TABLE secret_passages (
    stable_key  TEXT PRIMARY KEY NOT NULL,
    scene       TEXT,
    x           REAL,
    y           REAL,
    z           REAL,
    object_name TEXT,
    type        TEXT,
    is_excluded INTEGER NOT NULL DEFAULT 0,
    exclusion_reason TEXT
);

CREATE TABLE ascensions (
    stable_key                      TEXT PRIMARY KEY NOT NULL,
    ascension_db_index              INTEGER,
    id                              TEXT,
    used_by                         TEXT,
    skill_name                      TEXT,
    skill_desc                      TEXT,
    max_rank                        INTEGER,
    sim_player_weight               INTEGER,
    increase_hp                     REAL,
    increase_def                    REAL,
    increase_mana                   REAL,
    mr                              REAL,
    pr                              REAL,
    er                              REAL,
    vr                              REAL,
    increase_dodge                  REAL,
    increase_combat_roll            REAL,
    decrease_aggro_gen              REAL,
    chance_for_extra_attack         REAL,
    chance_for_double_backstab      REAL,
    chance_to_crit_backstab         REAL,
    resist_mod_increase             REAL,
    decrease_spell_aggro_gen        REAL,
    triple_resonate_chance          REAL,
    cooldown_reduction              REAL,
    intelligence_scaling            REAL,
    triple_attack_chance            REAL,
    aggro_gen_increase              REAL,
    mitigation_increase             REAL,
    advanced_increase_hp            REAL,
    advanced_resists                REAL,
    healing_increase                 REAL,
    critical_dot_chance              REAL,
    critical_healing_chance          REAL,
    vengeful_healing_percentage      REAL,
    summoned_beast_enhancement       REAL,
    reload_haste                     REAL,
    lightning_proc_chance            REAL,
    no_cd_penalty_chance             REAL,
    killshot_chance                  REAL,
    triple_attack_chance_reav        REAL,
    resource_name                   TEXT
);

CREATE TABLE books (
    book_title      TEXT NOT NULL,
    page_number     INTEGER NOT NULL,
    page_content    TEXT,
    PRIMARY KEY (book_title, page_number)
);

CREATE TABLE classes (
    class_name          TEXT PRIMARY KEY NOT NULL,
    display_name        TEXT,
    mitigation_bonus    REAL,
    str_benefit         INTEGER,
    end_benefit         INTEGER,
    dex_benefit         INTEGER,
    agi_benefit         INTEGER,
    int_benefit         INTEGER,
    wis_benefit         INTEGER,
    cha_benefit         INTEGER,
    aggro_mod           REAL,
    resource_name       TEXT
);

CREATE TABLE class_starting_items (
    class_name      TEXT NOT NULL,
    item_stable_key TEXT NOT NULL,
    sort_order      INTEGER NOT NULL,
    PRIMARY KEY (class_name, sort_order)
);

CREATE TABLE guild_topics (
    stable_key              TEXT PRIMARY KEY NOT NULL,
    guild_topic_db_index    INTEGER,
    id                      TEXT,
    activation_words        TEXT,
    responses               TEXT,
    relevant_scenes         TEXT,
    required_level_to_know  INTEGER,
    resource_name           TEXT
);

-- min_reading_level: the lowest player level whose treasure map can point to
-- the zone, or NULL when no map can.
CREATE TABLE treasure_hunting (
    zone_name               TEXT PRIMARY KEY NOT NULL,
    zone_display_name       TEXT,
    is_pickable_always      INTEGER,
    is_pickable_greater_20  INTEGER,
    is_pickable_greater_30  INTEGER,
    min_reading_level       INTEGER
);

-- -------------------------------------------------------------------------
-- Zones
-- -------------------------------------------------------------------------

CREATE TABLE zones (
    stable_key                                TEXT PRIMARY KEY NOT NULL,
    scene_name                                TEXT,
    zone_name                                 TEXT NOT NULL,
    display_name                              TEXT NOT NULL,
    wiki_page_name                            TEXT,
    image_name                                TEXT NOT NULL,
    is_wiki_generated                         INTEGER NOT NULL DEFAULT 1,
    is_map_visible                            INTEGER NOT NULL DEFAULT 1,
    is_dungeon                                INTEGER,
    zone_type                                 TEXT NOT NULL
                                              CHECK (zone_type IN ('Outdoor', 'Dungeon', 'Raid', 'Event')),
    raid_capable                              INTEGER,
    use_zone_as_temp_bind                     TEXT,
    achievement                               TEXT,
    complete_quest_on_enter_stable_key        TEXT,
    complete_second_quest_on_enter_stable_key TEXT,
    assign_quest_on_enter_stable_key          TEXT,
    north_bearing                             REAL
);

CREATE TABLE zone_atlas_entries (
    atlas_index         INTEGER,
    id                  TEXT PRIMARY KEY NOT NULL,
    zone_name           TEXT,
    level_range_low     INTEGER,
    level_range_high    INTEGER,
    dungeon             INTEGER,
    resource_name       TEXT
);

CREATE TABLE zone_atlas_neighbors (
    zone_atlas_id               TEXT NOT NULL,
    neighbor_zone_stable_key    TEXT NOT NULL,
    PRIMARY KEY (zone_atlas_id, neighbor_zone_stable_key)
);

-- -------------------------------------------------------------------------
-- Factions
-- -------------------------------------------------------------------------

CREATE TABLE factions (
    stable_key      TEXT PRIMARY KEY NOT NULL,
    faction_db_index INTEGER,
    faction_name    TEXT,
    faction_desc    TEXT,
    display_name    TEXT NOT NULL,
    wiki_page_name  TEXT,
    image_name      TEXT NOT NULL,
    is_wiki_generated INTEGER NOT NULL DEFAULT 1,
    is_map_visible  INTEGER NOT NULL DEFAULT 1,
    default_value   REAL,
    refname         TEXT,
    resource_name   TEXT
);

-- -------------------------------------------------------------------------
-- Pictures: every game picture that the wiki or the map shows, once each
-- -------------------------------------------------------------------------

-- A picture is identified by the SHA-256 of its width, height, and RGBA
-- pixels, so its identity does not depend on how a PNG file encodes it. Its
-- file is images/catalog/<image_hash>.png of the variant.
CREATE TABLE images (
    image_hash      TEXT PRIMARY KEY NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('icon', 'render')),
    width           INTEGER NOT NULL,
    height          INTEGER NOT NULL,
    file_sha1       TEXT NOT NULL,
    file_bytes      INTEGER NOT NULL,
    capture_preset  TEXT,
    approved_build  TEXT
);

-- Where a picture came from: the export's texture asset path of an icon, or
-- the approved capture of a render. Textures with equal pixels share one
-- picture.
CREATE TABLE image_sources (
    image_hash  TEXT NOT NULL REFERENCES images (image_hash),
    source      TEXT NOT NULL,
    PRIMARY KEY (image_hash, source)
);

-- Every wiki file title that a wiki page names for a picture, with the first
-- entity that names it in the order item, spell, skill, stance, character.
CREATE TABLE image_titles (
    title       TEXT PRIMARY KEY NOT NULL,
    image_hash  TEXT NOT NULL REFERENCES images (image_hash),
    stable_key  TEXT NOT NULL
);

-- The approved renders of each item with a page, under their wiki file titles:
-- one render, or one for each body whose parts draw the item differently.
-- Items that share a subject share its renders. An item's icon stays in
-- items.image_hash.
CREATE TABLE item_renders (
    stable_key  TEXT NOT NULL REFERENCES items (stable_key),
    title       TEXT NOT NULL,
    body        TEXT CHECK (body IN ('male', 'female')),
    image_hash  TEXT NOT NULL REFERENCES images (image_hash),
    PRIMARY KEY (stable_key, title)
);

-- -------------------------------------------------------------------------
-- Items
-- -------------------------------------------------------------------------

CREATE TABLE items (
    stable_key                      TEXT PRIMARY KEY NOT NULL,
    item_db_index                   INTEGER,
    id                              TEXT,
    item_name                       TEXT,
    display_name                    TEXT NOT NULL,
    wiki_page_name                  TEXT,
    image_name                      TEXT NOT NULL,
    image_hash                      TEXT REFERENCES images (image_hash),
    is_wiki_generated               INTEGER NOT NULL DEFAULT 1,
    is_map_visible                  INTEGER NOT NULL DEFAULT 1,
    lore                            TEXT,
    required_slot                   TEXT,
    this_weapon_type                TEXT,
    item_level                      INTEGER,
    weapon_dly                      REAL,
    shield                          INTEGER,
    weapon_proc_chance              REAL,
    weapon_proc_on_hit_stable_key   TEXT,
    is_wand                         INTEGER,
    wand_range                      INTEGER,
    wand_proc_chance                REAL,
    wand_effect_stable_key          TEXT,
    wand_bolt_color_r               REAL,
    wand_bolt_color_g               REAL,
    wand_bolt_color_b               REAL,
    wand_bolt_color_a               REAL,
    wand_bolt_speed                 REAL,
    wand_attack_sound_name          TEXT,
    is_bow                          INTEGER,
    bow_effect_stable_key           TEXT,
    bow_proc_chance                 REAL,
    bow_range                       INTEGER,
    bow_arrow_speed                 REAL,
    bow_attack_sound_name           TEXT,
    item_effect_on_click_stable_key TEXT,
    item_skill_use_stable_key       TEXT,
    teach_spell_stable_key          TEXT,
    teach_skill_stable_key          TEXT,
    aura_stable_key                 TEXT,
    worn_effect_stable_key          TEXT,
    spell_cast_time                 REAL,
    assign_quest_on_read_stable_key TEXT,
    complete_on_read_stable_key     TEXT,
    template                        INTEGER,
    template_ingredient_ids         TEXT,
    template_reward_ids             TEXT,
    item_value                      INTEGER,
    sell_value                      INTEGER,
    stackable                       INTEGER,
    disposable                      INTEGER,
    is_unique                       INTEGER,
    relic                           INTEGER,
    no_trade_no_destroy             INTEGER,
    must_be_equipped_to_click       INTEGER,
    player_cannot_sell              INTEGER,
    rare_item                       INTEGER,
    is_auctionable                  INTEGER,
    -- What the item does in a cosmetic slot: mask, belt lamp, or lens.
    cosmetic_effect                 TEXT,
    book_title                      TEXT,
    mining                          INTEGER,
    fuel_source                     INTEGER,
    fuel_level                      INTEGER,
    sim_players_cant_get            INTEGER,
    furniture_set                   INTEGER,
    attack_sound_name               TEXT,
    item_icon_name                  TEXT,
    equipment_to_activate           TEXT,
    hide_hair_when_equipped         INTEGER,
    hide_head_when_equipped         INTEGER,
    resource_name                   TEXT
);

CREATE TABLE item_stats (
    item_stable_key     TEXT NOT NULL,
    quality             TEXT NOT NULL,
    weapon_dmg          INTEGER,
    hp                  INTEGER,
    ac                  INTEGER,
    mana                INTEGER,
    str                 INTEGER,
    end                 INTEGER,
    dex                 INTEGER,
    agi                 INTEGER,
    int                 INTEGER,
    wis                 INTEGER,
    cha                 INTEGER,
    res                 INTEGER,
    mr                  INTEGER,
    er                  INTEGER,
    pr                  INTEGER,
    vr                  INTEGER,
    str_scaling         REAL,
    end_scaling         REAL,
    dex_scaling         REAL,
    agi_scaling         REAL,
    int_scaling         REAL,
    wis_scaling         REAL,
    cha_scaling         REAL,
    resist_scaling      REAL,
    mitigation_scaling  REAL,
    PRIMARY KEY (item_stable_key, quality)
);

CREATE TABLE item_classes (
    item_stable_key TEXT NOT NULL,
    class_name      TEXT NOT NULL,
    PRIMARY KEY (item_stable_key, class_name)
);

CREATE TABLE crafting_recipes (
    recipe_item_stable_key      TEXT NOT NULL,
    material_slot               INTEGER NOT NULL,
    material_item_stable_key    TEXT NOT NULL,
    material_quantity           INTEGER,
    PRIMARY KEY (recipe_item_stable_key, material_slot)
);

CREATE TABLE crafting_rewards (
    recipe_item_stable_key  TEXT NOT NULL,
    reward_slot             INTEGER NOT NULL,
    reward_item_stable_key  TEXT NOT NULL,
    reward_quantity         INTEGER,
    PRIMARY KEY (recipe_item_stable_key, reward_slot)
);

CREATE TABLE item_drops (
    source_item_stable_key  TEXT NOT NULL,
    dropped_item_stable_key TEXT NOT NULL,
    pool_stable_key         TEXT NOT NULL,
    drop_probability        REAL,
    is_guaranteed           INTEGER,
    PRIMARY KEY (source_item_stable_key, dropped_item_stable_key, pool_stable_key)
);

-- Successful random listing routes, not the final draw after retry exhaustion.
-- Bounds apply only to the actor named by the column; NULL means unrestricted.
CREATE TABLE auction_house_items (
    item_stable_key  TEXT NOT NULL REFERENCES items (stable_key),
    route           TEXT NOT NULL CHECK (route IN ('direct', 'replacement', 'gear_surplus')),
    min_sim_level   INTEGER,
    max_sim_level   INTEGER,
    min_player_level INTEGER,
    max_player_level INTEGER,
    PRIMARY KEY (item_stable_key, route)
);

-- NPCDialogManager recognizes these exported GameObject identities as brokers.
CREATE TABLE auction_house_brokers (
    character_stable_key TEXT PRIMARY KEY NOT NULL REFERENCES characters (stable_key)
);

-- Ordered substitution pool; empty slots still participate in random selection.
CREATE TABLE common_world_items (
    position               INTEGER PRIMARY KEY,
    item_stable_key        TEXT REFERENCES items (stable_key)
);

-- Independent special selections from eligible loot tables. Missing hosts,
-- DestroyOnDeath and DoNotLeaveCorpse prevent these rolls. drop_probability
-- is the selection chance per eligible kill in percent at the default loot
-- rate without bonuses, before owned unique-item replacement. The killed
-- character's level must strictly exceed min_level_exclusive.
CREATE TABLE special_world_drops (
    item_stable_key         TEXT NOT NULL,
    pool                    TEXT NOT NULL,
    drop_probability        REAL NOT NULL,
    min_level_exclusive     INTEGER NOT NULL,
    PRIMARY KEY (item_stable_key, pool)
);

-- The descendants of the slot transforms of the player's male and female bodies,
-- and the mask objects, that equipping an item turns on by its
-- equipment_to_activate. meshes lists the meshes that a part draws, sorted and
-- joined by "|", so two bodies draw an item alike when their parts of its name
-- list the same meshes.
CREATE TABLE item_model_parts (
    body        TEXT NOT NULL,
    slot        TEXT NOT NULL,
    position    INTEGER NOT NULL,
    part        TEXT NOT NULL,
    meshes      TEXT NOT NULL,
    PRIMARY KEY (body, slot, position)
);

-- The furnishings of the Reliquary planning table's slots. Building a slot
-- turns on the furnishing whose name is the furniture set's
-- equipment_to_activate.
CREATE TABLE planning_table_furnishings (
    scene           TEXT NOT NULL,
    slot            TEXT NOT NULL,
    furnishing      TEXT NOT NULL,
    renderer_count  INTEGER NOT NULL,
    PRIMARY KEY (scene, slot, furnishing)
);

-- Items that a game mechanic turns into another item, such as the
-- Chessboard giving back a mold for the Candlekeeper figurine.
CREATE TABLE item_conversions (
    input_item_stable_key   TEXT NOT NULL,
    output_item_stable_key  TEXT NOT NULL,
    zone_stable_key         TEXT NOT NULL,
    mechanic                TEXT NOT NULL,
    PRIMARY KEY (input_item_stable_key, output_item_stable_key, mechanic)
);

-- Items that can replace a fishing catch in any water. chance_per_catch is
-- in percent.
CREATE TABLE fishing_bonus_catches (
    item_stable_key     TEXT PRIMARY KEY NOT NULL,
    chance_per_catch    REAL NOT NULL
);

-- Zones where using an item has a different outcome, such as the Time Stone
-- returning unused.
CREATE TABLE item_zone_restrictions (
    item_stable_key     TEXT NOT NULL,
    zone_stable_key     TEXT NOT NULL,
    outcome             TEXT NOT NULL,
    PRIMARY KEY (item_stable_key, zone_stable_key)
);

-- Characters that bless one offered piece of equipment for equal numbers of
-- the two items. Chances are out of 100: chance_per_stone_pair per pair plus
-- chance_per_improvement_level per improvement level of the piece. An
-- improved piece then becomes enhanced_quality instead of result_quality at
-- its improvement bonus plus enhance_chance_per_stone_pair per pair.
CREATE TABLE quality_offerings (
    character_stable_key            TEXT PRIMARY KEY NOT NULL,
    first_item_stable_key           TEXT NOT NULL,
    second_item_stable_key          TEXT NOT NULL,
    chance_per_stone_pair           INTEGER NOT NULL,
    chance_per_improvement_level    INTEGER NOT NULL,
    enhance_chance_per_stone_pair   INTEGER NOT NULL,
    result_quality                  TEXT NOT NULL,
    enhanced_quality                TEXT NOT NULL
);


CREATE TABLE spell_created_items (
    source_item_stable_key   TEXT NOT NULL,
    spell_stable_key         TEXT NOT NULL,
    created_item_stable_key  TEXT NOT NULL,
    grant_fact_id           TEXT NOT NULL,
    quantity                INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (source_item_stable_key, created_item_stable_key)
);

-- -------------------------------------------------------------------------
-- Spells
-- -------------------------------------------------------------------------

CREATE TABLE spells (
    stable_key                          TEXT PRIMARY KEY NOT NULL,
    spell_db_index                      INTEGER,
    id                                  TEXT,
    spell_name                          TEXT,
    display_name                        TEXT NOT NULL,
    wiki_page_name                      TEXT,
    image_name                          TEXT NOT NULL,
    image_hash                          TEXT REFERENCES images (image_hash),
    is_wiki_generated                   INTEGER NOT NULL DEFAULT 1,
    is_map_visible                      INTEGER NOT NULL DEFAULT 1,
    spell_desc                          TEXT,
    special_descriptor                  TEXT,
    type                                TEXT,
    line                                TEXT,
    required_level                      INTEGER,
    mana_cost                           INTEGER,
    sim_usable                          INTEGER,
    sims_need_help_to_learn             INTEGER,
    aggro                               INTEGER,
    spell_charge_time                   REAL,
    cooldown                            REAL,
    spell_duration_in_ticks             INTEGER,
    unstable_duration                   INTEGER,
    instant_effect                      INTEGER,
    spell_range                         REAL,
    self_only                           INTEGER,
    max_level_target                    INTEGER,
    group_effect                        INTEGER,
    can_hit_players                     INTEGER,
    apply_to_caster                     INTEGER,
    inflict_on_self                     INTEGER,
    target_damage                       INTEGER,
    target_healing                      INTEGER,
    caster_healing                      INTEGER,
    shielding_amt                       INTEGER,
    lifetap                             INTEGER,
    damage_type                         TEXT,
    resist_modifier                     REAL,
    add_proc_stable_key                 TEXT,
    add_proc_chance                     INTEGER,
    hp                                  INTEGER,
    ac                                  INTEGER,
    mana                                INTEGER,
    percent_mana_restoration            INTEGER,
    movement_speed                      REAL,
    str                                 INTEGER,
    dex                                 INTEGER,
    end                                 INTEGER,
    agi                                 INTEGER,
    wis                                 INTEGER,
    int                                 INTEGER,
    cha                                 INTEGER,
    mr                                  INTEGER,
    er                                  INTEGER,
    pr                                  INTEGER,
    vr                                  INTEGER,
    damage_shield                       INTEGER,
    haste                               REAL,
    percent_lifesteal                   REAL,
    atk_roll_modifier                   INTEGER,
    bleed_damage_percent                INTEGER,
    root_target                         INTEGER,
    stun_target                         INTEGER,
    charm_target                        INTEGER,
    fear_target                         INTEGER,
    crowd_control_spell                 INTEGER,
    break_on_damage                     INTEGER,
    break_on_any_action                 INTEGER,
    taunt_spell                         INTEGER,
    pet_to_summon_stable_key            TEXT,
    status_effect_to_apply_stable_key   TEXT,
    reap_and_renew                      INTEGER,
    resonate_chance                     INTEGER,
    xp_bonus                            REAL,
    automate_attack                     INTEGER,
    worn_effect                         INTEGER,
    grant_invisibility                  INTEGER,
    cannot_interrupt                    INTEGER,
    jolt_spell                          INTEGER,
    no_resonate                         INTEGER,
    armor_pen_percent                   INTEGER,
    level_scaled_mana_restoration       REAL,
    shapeshift_form                     TEXT,
    spell_charge_fx_index               INTEGER,
    spell_resolve_fx_index              INTEGER,
    spell_icon_name                     TEXT,
    shake_dur                           REAL,
    shake_amp                           REAL,
    color_r                             REAL,
    color_g                             REAL,
    color_b                             REAL,
    color_a                             REAL,
    status_effect_message_on_player     TEXT,
    status_effect_message_on_npc        TEXT,
    resource_name                       TEXT
);

CREATE TABLE spell_classes (
    spell_stable_key    TEXT NOT NULL,
    class_name          TEXT NOT NULL,
    PRIMARY KEY (spell_stable_key, class_name)
);

-- -------------------------------------------------------------------------
-- Skills
-- -------------------------------------------------------------------------

CREATE TABLE skills (
    stable_key                  TEXT PRIMARY KEY NOT NULL,
    skill_db_index              INTEGER,
    id                          TEXT,
    skill_name                  TEXT,
    display_name                TEXT NOT NULL,
    wiki_page_name              TEXT,
    image_name                  TEXT NOT NULL,
    image_hash                  TEXT REFERENCES images (image_hash),
    is_wiki_generated           INTEGER NOT NULL DEFAULT 1,
    is_map_visible              INTEGER NOT NULL DEFAULT 1,
    skill_desc                  TEXT,
    type_of_skill               TEXT,
    cooldown                    REAL,
    duelist_required_level      INTEGER,
    paladin_required_level      INTEGER,
    arcanist_required_level     INTEGER,
    druid_required_level        INTEGER,
    stormcaller_required_level  INTEGER,
    reaver_required_level       INTEGER,
    require_behind              INTEGER,
    require_2h                  INTEGER,
    require_dw                  INTEGER,
    require_bow                 INTEGER,
    require_shield              INTEGER,
    sim_players_autolearn       INTEGER,
    ae_skill                    INTEGER,
    interrupt                   INTEGER,
    spawn_on_use_stable_key     TEXT,
    effect_to_apply_stable_key  TEXT,
    affect_player               INTEGER,
    affect_target               INTEGER,
    skill_range                 REAL,
    skill_power                 INTEGER,
    percent_dmg                 REAL,
    damage_type                 TEXT,
    scale_off_weapon            INTEGER,
    proc_weap                   INTEGER,
    proc_shield                 INTEGER,
    guarantee_proc              INTEGER,
    skill_can_crit              INTEGER,
    automate_attack             INTEGER,
    cast_on_target_stable_key   TEXT,
    stance_to_use_stable_key    TEXT,
    skill_anim_name             TEXT,
    skill_icon_name             TEXT,
    player_uses                 TEXT,
    npc_uses                    TEXT,
    resource_name               TEXT
);

-- -------------------------------------------------------------------------
-- Stances
-- -------------------------------------------------------------------------

CREATE TABLE stances (
    stable_key              TEXT PRIMARY KEY NOT NULL,
    stance_db_index         INTEGER,
    id                      TEXT,
    display_name            TEXT NOT NULL,
    wiki_page_name          TEXT,
    image_name              TEXT NOT NULL,
    image_hash              TEXT REFERENCES images (image_hash),
    is_wiki_generated       INTEGER NOT NULL DEFAULT 1,
    is_map_visible          INTEGER NOT NULL DEFAULT 1,
    max_hp_mod              REAL,
    damage_mod              REAL,
    proc_rate_mod           REAL,
    damage_taken_mod        REAL,
    self_damage_per_attack  REAL,
    aggro_gen_mod           REAL,
    spell_damage_mod        REAL,
    self_damage_per_cast    REAL,
    lifesteal_amount        REAL,
    resonance_amount        REAL,
    stop_regen              INTEGER,
    switch_message          TEXT,
    stance_desc             TEXT,
    resource_name           TEXT
);

-- -------------------------------------------------------------------------
-- Quests
-- -------------------------------------------------------------------------

CREATE TABLE quests (
    stable_key      TEXT PRIMARY KEY NOT NULL,
    db_name         TEXT,
    display_name    TEXT NOT NULL,
    wiki_page_name  TEXT,
    image_name      TEXT NOT NULL,
    step_note       TEXT,
    is_wiki_generated INTEGER NOT NULL DEFAULT 1,
    is_map_visible  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE quest_variants (
    resource_name                               TEXT PRIMARY KEY NOT NULL,
    quest_stable_key                            TEXT,
    quest_db_index                              INTEGER,
    quest_name                                  TEXT,
    quest_desc                                  TEXT,
    xp_on_complete                              INTEGER,
    item_on_complete_stable_key                 TEXT,
    gold_on_complete                            INTEGER,
    assign_new_quest_on_complete_stable_key     TEXT,
    dialog_on_success                           TEXT,
    dialog_on_partial_success                   TEXT,
    disable_text                                TEXT,
    assign_this_quest_on_partial_complete       INTEGER,
    repeatable                                  INTEGER,
    disable_quest                               INTEGER,
    kill_turn_in_holder                         INTEGER,
    destroy_turn_in_holder                      INTEGER,
    drop_invuln_on_holder                       INTEGER,
    once_per_spawn_instance                     INTEGER,
    set_achievement_on_get                      TEXT,
    set_achievement_on_finish                   TEXT,
    unlock_item_for_vendor_stable_key           TEXT
);

CREATE TABLE quest_required_items (
    quest_variant_resource_name TEXT NOT NULL,
    required_slot               INTEGER NOT NULL,
    item_stable_key             TEXT NOT NULL,
    quantity                    INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (quest_variant_resource_name, required_slot)
);

CREATE TABLE quest_faction_affects (
    quest_variant_resource_name TEXT NOT NULL,
    faction_stable_key          TEXT NOT NULL,
    modifier_value              INTEGER,
    PRIMARY KEY (quest_variant_resource_name, faction_stable_key)
);

CREATE TABLE quest_complete_other_quests (
    quest_variant_resource_name TEXT NOT NULL,
    completed_quest_stable_key  TEXT NOT NULL,
    PRIMARY KEY (quest_variant_resource_name, completed_quest_stable_key)
);

CREATE TABLE quest_character_roles (
    quest_stable_key        TEXT NOT NULL,
    character_stable_key    TEXT NOT NULL,
    role                    TEXT NOT NULL,
    PRIMARY KEY (quest_stable_key, character_stable_key, role)
);

CREATE TABLE quest_completion_sources (
    quest_stable_key    TEXT NOT NULL,
    method              TEXT,
    source_type         TEXT,
    source_stable_key   TEXT,
    note                TEXT
);
CREATE INDEX quest_completion_sources_quest_idx
    ON quest_completion_sources (quest_stable_key);

CREATE TABLE quest_acquisition_sources (
    quest_stable_key    TEXT NOT NULL,
    method              TEXT,
    source_type         TEXT,
    source_stable_key   TEXT,
    note                TEXT
);
CREATE INDEX quest_acquisition_sources_quest_idx
    ON quest_acquisition_sources (quest_stable_key);

CREATE TABLE quest_routes (
    route_key TEXT PRIMARY KEY NOT NULL,
    quest_stable_key TEXT NOT NULL REFERENCES quests(stable_key),
    phase TEXT NOT NULL CHECK (phase IN ('start', 'completion')),
    method TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_stable_key TEXT,
    source_group_key TEXT,
    variant_resource_name TEXT,
    dialog_index INTEGER,
    keywords TEXT,
    note TEXT,
    grants_resource_rewards INTEGER NOT NULL CHECK (grants_resource_rewards IN (0, 1))
);
CREATE INDEX quest_routes_quest_idx ON quest_routes(quest_stable_key, phase);
CREATE TABLE quest_route_conditions (
    route_key TEXT NOT NULL REFERENCES quest_routes(route_key),
    gate_key TEXT NOT NULL,
    group_index INTEGER NOT NULL,
    atom_index INTEGER NOT NULL,
    atom_kind TEXT NOT NULL CHECK (atom_kind IN ('quest_done', 'quest_not_done', 'item_not_owned', 'item_held')),
    atom_stable_key TEXT NOT NULL,
    PRIMARY KEY (route_key, gate_key, group_index, atom_index)
);

CREATE TABLE progression_nodes (
    stable_key TEXT PRIMARY KEY NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN (
        'zone', 'quest', 'quest_start', 'item', 'character', 'barrier',
        'mechanism', 'class', 'spell', 'world_state', 'account_state'
    )),
    is_milestone INTEGER NOT NULL CHECK (is_milestone IN (0, 1)),
    tier INTEGER CHECK (tier >= 0),
    first_way_key TEXT,
    CHECK ((tier IS NULL) = (first_way_key IS NULL))
);
-- tier and depth rank a way as first ways are chosen. A way with a need
-- that has no tier has neither.
CREATE TABLE progression_ways (
    node_stable_key TEXT NOT NULL REFERENCES progression_nodes(stable_key),
    way_key TEXT NOT NULL,
    tier INTEGER CHECK (tier >= 0),
    depth INTEGER CHECK (depth >= 0),
    PRIMARY KEY (node_stable_key, way_key),
    CHECK ((tier IS NULL) = (depth IS NULL))
);
-- The clean facts that produced a way, such as an item acquisition key.
CREATE TABLE progression_way_facts (
    node_stable_key TEXT NOT NULL,
    way_key TEXT NOT NULL,
    fact TEXT NOT NULL,
    PRIMARY KEY (node_stable_key, way_key, fact),
    FOREIGN KEY (node_stable_key, way_key) REFERENCES progression_ways(node_stable_key, way_key)
);
CREATE INDEX progression_way_facts_fact_idx ON progression_way_facts(fact);
CREATE TABLE progression_needs (
    node_stable_key TEXT NOT NULL,
    way_key TEXT NOT NULL,
    need_index INTEGER NOT NULL CHECK (need_index >= 0),
    relation TEXT NOT NULL,
    need_stable_key TEXT REFERENCES progression_nodes(stable_key),
    quantity REAL,
    slot TEXT,
    keywords TEXT,
    condition_key TEXT,
    advisory INTEGER NOT NULL CHECK (advisory IN (0, 1)),
    unconfirmed INTEGER NOT NULL CHECK (unconfirmed IN (0, 1)),
    required_level INTEGER CHECK (required_level >= 0),
    PRIMARY KEY (node_stable_key, way_key, need_index),
    FOREIGN KEY (node_stable_key, way_key) REFERENCES progression_ways(node_stable_key, way_key),
    CHECK (need_stable_key IS NOT NULL OR condition_key IS NOT NULL)
);
CREATE INDEX progression_needs_target_idx ON progression_needs(need_stable_key);
CREATE TABLE progression_meta (
    contract_version INTEGER NOT NULL,
    game_build_id TEXT NOT NULL
);

-- Prefab defaults of explicitly referenced authored sims. No world-NPC semantics.
CREATE TABLE authored_sims (
    stable_key                  TEXT PRIMARY KEY NOT NULL,
    prefab_guid                 TEXT NOT NULL,
    prefab_local_id             INTEGER NOT NULL,
    prefab_path                 TEXT NOT NULL,
    object_name                 TEXT NOT NULL,
    raw_character_stable_key    TEXT NOT NULL,
    npc_name                    TEXT NOT NULL,
    seed_class_name             TEXT NOT NULL REFERENCES classes (class_name),
    seed_level                  INTEGER NOT NULL,
    seed_skill_level            REAL NOT NULL,
    seed_is_male                INTEGER NOT NULL,
    seed_hair_name              TEXT NOT NULL,
    seed_hair_color             INTEGER NOT NULL,
    seed_skin_color             INTEGER NOT NULL,
    is_gm_character             INTEGER NOT NULL,
    rival                       INTEGER NOT NULL,
    UNIQUE (prefab_guid, prefab_local_id)
);

CREATE TABLE authored_sim_references (
    source_component_key        TEXT NOT NULL,
    reference_index             INTEGER NOT NULL,
    source_scene                TEXT NOT NULL,
    source_scene_path           TEXT NOT NULL,
    authored_sim_stable_key     TEXT NOT NULL REFERENCES authored_sims (stable_key),
    PRIMARY KEY (source_component_key, reference_index)
);

CREATE TABLE authored_sim_equipment (
    authored_sim_stable_key     TEXT NOT NULL REFERENCES authored_sims (stable_key),
    position                    INTEGER NOT NULL,
    item_stable_key             TEXT REFERENCES items (stable_key),
    PRIMARY KEY (authored_sim_stable_key, position)
);

-- Zone-wide eligibility is not a fixed placement. Runtime cosmetic equipment,
-- the recent successful-spawn scene history, and registered SpawnPoints remain
-- prerequisites, not exported player-state facts.
CREATE TABLE zone_wide_spawn_rules (
    rule_id                         TEXT PRIMARY KEY NOT NULL,
    source_script                   TEXT NOT NULL,
    candidate_script                TEXT NOT NULL,
    candidate_field                 TEXT NOT NULL,
    required_cosmetic_item_stable_key TEXT NOT NULL REFERENCES items (stable_key),
    attempt_probability             REAL NOT NULL CHECK (attempt_probability BETWEEN 0 AND 1),
    entry_delay_ticks               REAL NOT NULL CHECK (entry_delay_ticks > 0),
    entry_delay_ticks_per_second    REAL NOT NULL CHECK (entry_delay_ticks_per_second > 0),
    attempt_trigger                 TEXT NOT NULL CHECK (attempt_trigger = 'entry_timer_crosses_below_zero'),
    max_attempts_per_entry           INTEGER NOT NULL CHECK (max_attempts_per_entry = 1),
    recent_successful_zone_limit     INTEGER NOT NULL CHECK (recent_successful_zone_limit > 0),
    requires_registered_spawn_point  INTEGER NOT NULL CHECK (requires_registered_spawn_point = 1)
);

CREATE TABLE zone_wide_spawn_candidates (
    rule_id                TEXT NOT NULL REFERENCES zone_wide_spawn_rules (rule_id),
    character_stable_key   TEXT NOT NULL REFERENCES characters (stable_key),
    weight                 INTEGER NOT NULL CHECK (weight > 0),
    total_weight           INTEGER NOT NULL CHECK (total_weight >= weight),
    PRIMARY KEY (rule_id, character_stable_key)
);

-- A scene with authored SpawnPoints can qualify when at least one registers at
-- runtime. The enabled count describes the asset, not the player's live scene.
CREATE TABLE zone_wide_spawn_zones (
    rule_id                    TEXT NOT NULL REFERENCES zone_wide_spawn_rules (rule_id),
    zone_stable_key            TEXT NOT NULL REFERENCES zones (stable_key),
    authored_spawn_point_count INTEGER NOT NULL CHECK (authored_spawn_point_count > 0),
    enabled_spawn_point_count  INTEGER NOT NULL CHECK (
                                   enabled_spawn_point_count BETWEEN 0 AND authored_spawn_point_count
                               ),
    PRIMARY KEY (rule_id, zone_stable_key)
);

-- -------------------------------------------------------------------------
-- Characters
-- -------------------------------------------------------------------------

CREATE TABLE characters (
    stable_key                  TEXT PRIMARY KEY NOT NULL,
    object_name                 TEXT,
    npc_name                    TEXT,
    display_name                TEXT NOT NULL,
    wiki_page_name              TEXT,
    image_name                  TEXT NOT NULL,
    image_hash                  TEXT REFERENCES images (image_hash),
    is_wiki_generated           INTEGER NOT NULL DEFAULT 1,
    is_map_visible              INTEGER NOT NULL DEFAULT 1,
    scene                       TEXT,
    x                           REAL,
    y                           REAL,
    z                           REAL,
    guid                        TEXT,
    resources_path              TEXT,
    my_world_faction_stable_key TEXT,
    my_faction                  TEXT,
    aggro_range                 REAL,
    attack_range                REAL,
    aggressive_towards          TEXT,
    allies                      TEXT,
    is_prefab                   INTEGER,
    encounter_tier              TEXT NOT NULL CHECK (encounter_tier IN ('npc', 'chest', 'boss', 'elite', 'enemy')),
    is_friendly                 INTEGER,
    is_npc                      INTEGER,
    is_vendor                   INTEGER,
    is_mining_node              INTEGER,
    has_stats                   INTEGER,
    has_dialog                  INTEGER,
    has_modify_faction          INTEGER,
    is_enabled                  INTEGER,
    invulnerable                INTEGER,
    can_be_damaged              INTEGER NOT NULL DEFAULT 0 CHECK (can_be_damaged IN (0, 1)),
    can_never_see_invis         INTEGER,
    dps_dummy                   INTEGER,
    is_wyrm                     INTEGER,
    no_run                      INTEGER,
    never_aggro                 INTEGER,
    no_dmg_cap                  INTEGER,
    can_phantom_strike          INTEGER,
    no_self_heal                INTEGER,
    aggro_regardless_of_los     INTEGER,
    ignore_los_for_aggro        INTEGER,
    sim_players_ignore_until_ordered INTEGER,
    enrage                      REAL,
    shout_on_death              TEXT,
    quest_complete_on_death     TEXT,
    shout_trigger_quest_stable_key TEXT,
    shout_trigger_keyword       TEXT,
    destroy_on_death            INTEGER,
    level                       INTEGER,
    -- 1 when the game sets the level from the player's level: treasure
    -- guardians, and training dummies below level 42. Then level is only the
    -- prefab value, and an effective stat that depends on the player's level
    -- is NULL.
    level_scales_with_player    INTEGER NOT NULL,
    -- When the AC depends on the player's level as this many times it.
    ac_per_player_level         INTEGER,
    base_xp_min                 REAL,
    base_xp_max                 REAL,
    boss_xp_multiplier          REAL,
    initialized_xp              INTEGER,
    xp_per_player_level         INTEGER,
    effective_xp_multiplier     REAL,
    start_components_listed     TEXT,
    start_components_by_file_id TEXT,
    is_active_at_load           INTEGER,
    base_hp                     INTEGER,
    base_ac                     INTEGER,
    base_mana                   INTEGER,
    base_str                    INTEGER,
    base_end                    INTEGER,
    base_dex                    INTEGER,
    base_agi                    INTEGER,
    base_int                    INTEGER,
    base_wis                    INTEGER,
    base_cha                    INTEGER,
    base_res                    INTEGER,
    base_mr                     INTEGER,
    base_er                     INTEGER,
    base_pr                     INTEGER,
    base_vr                     INTEGER,
    run_speed                   REAL,
    base_life_steal             REAL,
    base_mh_atk_delay          REAL,
    base_oh_atk_delay          REAL,
    base_armor_pen_percentage   REAL,
    base_attack_roll_modifier   INTEGER,
    cannot_be_snared            INTEGER,
    class_resource_name         TEXT,
    effective_hp                INTEGER,
    effective_ac                INTEGER,
    effective_base_atk_dmg     INTEGER,
    effective_attack_ability    REAL,
    effective_min_mr            INTEGER,
    effective_max_mr            INTEGER,
    effective_min_er            INTEGER,
    effective_max_er            INTEGER,
    effective_min_pr            INTEGER,
    effective_max_pr            INTEGER,
    effective_min_vr            INTEGER,
    effective_max_vr            INTEGER,
    pet_spell_stable_key        TEXT,
    spawn_with_status_stable_key TEXT,
    group_hot_spell_stable_key  TEXT,
    emit_vitae_spell_stable_key TEXT,
    hot_spell_stable_key        TEXT,
    ae_taunt_spell_stable_key   TEXT,
    proc_on_hit_stable_key      TEXT,
    proc_on_hit_chance          REAL,
    hand_set_resistances        INTEGER,
    stats_starts_before_npc     INTEGER,
    -- TestDummy.HandSetAC: NULL without a TestDummy component, 0 without a
    -- hand-set AC.
    test_dummy_hand_set_ac      INTEGER,
    hard_set_ac                 INTEGER,
    base_atk_dmg                INTEGER,
    oh_atk_dmg                  INTEGER,
    min_atk_dmg                 INTEGER,
    damage_range_min            REAL,
    damage_range_max            REAL,
    damage_mult                 REAL,
    armor_pen_mult              REAL,
    power_attack_base_dmg       INTEGER,
    power_attack_freq           REAL,
    heal_tolerance              REAL,
    leash_range                 REAL,
    aggro_regardless_of_level   INTEGER,
    mobile                      INTEGER,
    group_encounter             INTEGER,
    treasure_chest              INTEGER,
    -- How many items LootTable.InitLootTable picks from the guaranteed pool.
    -- NULL when the character has no loot table.
    guaranteed_drop_rolls       INTEGER,
    do_not_leave_corpse         INTEGER,
    set_achievement_on_defeat   TEXT,
    set_achievement_on_spawn    TEXT,
    aggro_msg                   TEXT,
    aggro_emote                 TEXT,
    spawn_emote                 TEXT,
    guild_name                  TEXT,
    modify_factions             TEXT,
    vendor_desc                 TEXT,
    items_for_sale              TEXT,
    quest_manager_sim_usable    INTEGER
);

CREATE TABLE character_deduplications (
    group_key           TEXT NOT NULL,
    member_stable_key   TEXT PRIMARY KEY NOT NULL,
    is_wiki_generated   INTEGER NOT NULL DEFAULT 1,
    is_map_visible      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE character_spawns (
    character_stable_key    TEXT NOT NULL REFERENCES characters (stable_key),
    spawn_point_stable_key  TEXT,
    zone_stable_key         TEXT,
    scene                   TEXT,
    x                       REAL,
    y                       REAL,
    z                       REAL,
    is_enabled              INTEGER,
    is_directly_placed      INTEGER,
    is_trigger_spawn        INTEGER NOT NULL DEFAULT 0,
    rare_npc_chance         INTEGER,
    level_mod               INTEGER,
    spawn_delay_1           REAL,
    spawn_delay_2           REAL,
    spawn_delay_3           REAL,
    spawn_delay_4           REAL,
    staggerable             INTEGER,
    stagger_mod             REAL,
    night_spawn             INTEGER,
    patrol_points           TEXT,
    loop_patrol             INTEGER,
    random_wander_range     REAL,
    spawn_upon_quest_complete_stable_key TEXT,
    protector_stable_key    TEXT,
    spawn_chance            REAL,
    is_common               INTEGER,
    is_rare                 INTEGER,
    is_wiki_generated       INTEGER,
    is_map_visible          INTEGER,
    source_script           TEXT,
    event_x                 REAL,
    event_y                 REAL,
    event_z                 REAL,
    trigger_item_stable_key TEXT,
    trigger_mode            TEXT,
    event_display_name     TEXT,
    trigger_bounds_center_x REAL,
    trigger_bounds_center_y REAL,
    trigger_bounds_center_z REAL,
    trigger_bounds_extents_x REAL,
    trigger_bounds_extents_y REAL,
    trigger_bounds_extents_z REAL,
    -- The furniture set whose placement in a room of the Reliquary's planning
    -- table turns on this directly placed character. The character stands at
    -- its spot only in the rooms that hold the set.
    furniture_item_stable_key TEXT REFERENCES items (stable_key),
    -- The planning-table room slot (L1-L4 or R1-R4) containing this furnishing.
    -- Set exactly when furniture_item_stable_key is set.
    furniture_slot TEXT,
    PRIMARY KEY (character_stable_key, spawn_point_stable_key, is_directly_placed)
);

CREATE TABLE encounter_placements (
    encounter_key TEXT NOT NULL,
    root_spawn_stable_key TEXT NOT NULL,
    member_spawn_stable_key TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('root', 'support')),
    context_kind TEXT NOT NULL CHECK (context_kind IN ('account_claim')),
    post_completion_role TEXT NOT NULL CHECK (post_completion_role IN ('player_home')),
    PRIMARY KEY (encounter_key, member_spawn_stable_key)
);
CREATE TABLE encounter_conditions (
    encounter_key TEXT NOT NULL,
    state_scope TEXT NOT NULL CHECK (state_scope IN ('account', 'character')),
    state_key TEXT NOT NULL,
    required_value TEXT NOT NULL,
    PRIMARY KEY (encounter_key, state_scope, state_key)
);
CREATE TABLE encounter_completions (
    encounter_key TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    state_scope TEXT NOT NULL CHECK (state_scope IN ('account', 'character')),
    state_key TEXT NOT NULL,
    result_value TEXT NOT NULL,
    PRIMARY KEY (encounter_key, event_kind, state_scope, state_key)
);
CREATE TABLE encounter_event_conditions (
    encounter_key TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    state_scope TEXT NOT NULL CHECK (state_scope IN ('account', 'character')),
    state_key TEXT NOT NULL,
    required_value TEXT NOT NULL,
    PRIMARY KEY (encounter_key, event_kind, state_scope, state_key)
);

CREATE TABLE character_damage_releases (
    character_stable_key TEXT NOT NULL REFERENCES characters(stable_key),
    mechanism TEXT NOT NULL,
    source_stable_key TEXT NOT NULL,
    condition_kind TEXT NOT NULL,
    condition_stable_key TEXT NOT NULL DEFAULT '',
    can_release INTEGER NOT NULL CHECK (can_release IN (0, 1)),
    controller_enabled INTEGER NOT NULL CHECK (controller_enabled IN (0, 1)),
    PRIMARY KEY (character_stable_key, mechanism, source_stable_key, condition_kind, condition_stable_key)
);

CREATE TABLE character_chained_spawns (
    parent_stable_key  TEXT NOT NULL,
    child_stable_key   TEXT NOT NULL,
    source_script      TEXT NOT NULL,
    PRIMARY KEY (parent_stable_key, child_stable_key, source_script)
);

CREATE TABLE spawn_point_patrol_points (
    spawn_point_stable_key  TEXT NOT NULL,
    sequence_index          INTEGER NOT NULL,
    x                       REAL,
    y                       REAL,
    z                       REAL,
    PRIMARY KEY (spawn_point_stable_key, sequence_index)
);

CREATE TABLE spawn_point_stop_quests (
    spawn_point_stable_key  TEXT NOT NULL,
    quest_stable_key        TEXT NOT NULL,
    PRIMARY KEY (spawn_point_stable_key, quest_stable_key)
);

CREATE TABLE spawnpoint_essential_links (
    source_spawn_point_stable_key      TEXT NOT NULL,
    essential_spawn_point_stable_key   TEXT NOT NULL,
    source_scene                       TEXT,
    PRIMARY KEY (source_spawn_point_stable_key, essential_spawn_point_stable_key)
);

-- level_min/level_max: the dig levels [level_min, level_max) that spawn the
-- chest at the site. player_level_min/player_level_max: the player levels,
-- inclusive, at which digging at the site brings up the chest, after the
-- zone's lowest reading level and the level cap.
CREATE TABLE treasure_chest_possible_spawns (
    chest_character_stable_key  TEXT NOT NULL REFERENCES characters (stable_key),
    treasure_location_stable_key TEXT NOT NULL REFERENCES treasure_locations (stable_key),
    level_min                    INTEGER NOT NULL,
    level_max                    INTEGER NOT NULL,
    player_level_min             INTEGER NOT NULL,
    player_level_max             INTEGER NOT NULL,
    scene                        TEXT,
    x                            REAL,
    y                            REAL,
    z                            REAL,
    PRIMARY KEY (chest_character_stable_key, treasure_location_stable_key)
);

-- One row per number of waves that a dug-up treasure chest has spawned.
-- strike_break_chance is the chance that a strike then breaks the chest open.
-- Every strike rolls for that first, also while guardians are alive. A strike
-- that does not break the chest starts the next wave of next_wave_guardians_min
-- to next_wave_guardians_max guardians after next_wave_delay_seconds, but only
-- when no guardian is alive. The next_wave columns are NULL in the last row,
-- where every strike breaks the chest.
CREATE TABLE treasure_chest_waves (
    waves_spawned            INTEGER PRIMARY KEY,
    strike_break_chance      REAL NOT NULL,
    next_wave_guardians_min  INTEGER,
    next_wave_guardians_max  INTEGER,
    next_wave_delay_seconds  REAL
);

-- One row per guardian and player level: the stats of that guardian when a
-- player of that level strikes a dug-up treasure chest. Every stat is a
-- range, because the game rolls them. attack is the base damage per hit and
-- attack_delay the base swing delay in 1/60 s.
CREATE TABLE treasure_guardian_scaling (
    guardian_character_stable_key TEXT NOT NULL REFERENCES characters (stable_key),
    player_level                  INTEGER NOT NULL,
    level_min                     INTEGER NOT NULL,
    level_max                     INTEGER NOT NULL,
    health_min                    INTEGER NOT NULL,
    health_max                    INTEGER NOT NULL,
    attack_min                    INTEGER NOT NULL,
    attack_max                    INTEGER NOT NULL,
    attack_delay_min              INTEGER NOT NULL,
    attack_delay_max              INTEGER NOT NULL,
    ac_min                        INTEGER NOT NULL,
    ac_max                        INTEGER NOT NULL,
    resist_min                    INTEGER NOT NULL,
    resist_max                    INTEGER NOT NULL,
    PRIMARY KEY (guardian_character_stable_key, player_level)
);

CREATE TABLE character_ae_events (
    character_stable_key         TEXT NOT NULL REFERENCES characters (stable_key),
    component_type               TEXT NOT NULL,
    tick_damage                  INTEGER,
    tick_time                    REAL,
    tick_range                   INTEGER,
    resist_modifier              INTEGER,
    resist_type                  TEXT,
    event_happens                TEXT,
    damage_reason                TEXT,
    add_effect_spell_stable_key  TEXT,
    is_lifetap                   INTEGER,
    lifetap_heal_mod             REAL,
    trigger_only                 INTEGER,
    PRIMARY KEY (character_stable_key, component_type)
);

CREATE TABLE ae_event_mutations (
    character_stable_key          TEXT,
    script_type                   TEXT NOT NULL,
    trigger                       TEXT NOT NULL,
    trigger_condition             TEXT,
    tick_damage_formula           TEXT,
    tick_time_formula             TEXT,
    resist_modifier_formula       TEXT,
    other_field_formulas           TEXT,
    documented_limitation         TEXT,
    PRIMARY KEY (script_type, character_stable_key, trigger_condition)
);

CREATE TABLE loot_drops (
    character_stable_key    TEXT NOT NULL,
    item_stable_key         TEXT NOT NULL,
    loot_table_stable_key   TEXT NOT NULL,
    source_component_is_enabled INTEGER NOT NULL CHECK (source_component_is_enabled IN (0, 1)),
    drop_probability        REAL,
    expected_per_kill       REAL,
    drop_count_distribution TEXT,
    is_actual               INTEGER,
    is_guaranteed           INTEGER,
    is_common               INTEGER,
    is_common_world_item    INTEGER,
    is_uncommon             INTEGER,
    is_rare                 INTEGER,
    is_legendary            INTEGER,
    is_ultra_rare           INTEGER,
    is_unique               INTEGER,
    is_visible               INTEGER,
    zone                    TEXT,
    PRIMARY KEY (character_stable_key, item_stable_key)
);

CREATE TABLE arena_rounds (
    stable_key                        TEXT PRIMARY KEY,
    scene                             TEXT,
    arena_object_name                 TEXT,
    round_index                       INTEGER NOT NULL,
    coin_item_stable_key              TEXT NOT NULL,
    award_chest_character_stable_key  TEXT NOT NULL,
    trigger_mode                      TEXT,
    event_display_name                TEXT,
    event_x                           REAL,
    event_y                           REAL,
    event_z                           REAL,
    trigger_bounds_center_x           REAL,
    trigger_bounds_center_y           REAL,
    trigger_bounds_center_z           REAL,
    trigger_bounds_extents_x          REAL,
    trigger_bounds_extents_y          REAL,
    trigger_bounds_extents_z          REAL
);

CREATE TABLE arena_round_enemies (
    arena_round_stable_key  TEXT NOT NULL,
    sequence_index          INTEGER NOT NULL,
    enemy_character_stable_key TEXT NOT NULL,
    PRIMARY KEY (arena_round_stable_key, sequence_index)
);

CREATE TABLE character_dialogs (
    character_stable_key        TEXT NOT NULL,
    dialog_index                INTEGER NOT NULL,
    dialog_text                 TEXT,
    keywords                    TEXT,
    give_item_stable_key        TEXT,
    assign_quest_stable_key     TEXT,
    assign_quest_variant_resource_name TEXT REFERENCES quest_variants(resource_name),
    complete_quest_stable_key   TEXT,
    repeating_quest_dialog      TEXT,
    kill_self_on_say            INTEGER,
    required_quest_stable_key   TEXT,
    spawn_character_stable_key  TEXT,
    PRIMARY KEY (character_stable_key, dialog_index)
);

CREATE TABLE character_attack_skills (
    character_stable_key    TEXT NOT NULL,
    skill_stable_key        TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, skill_stable_key)
);

CREATE TABLE character_attack_spells (
    character_stable_key    TEXT NOT NULL,
    spell_stable_key        TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, spell_stable_key)
);

CREATE TABLE character_buff_spells (
    character_stable_key    TEXT NOT NULL,
    spell_stable_key        TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, spell_stable_key)
);

CREATE TABLE character_heal_spells (
    character_stable_key    TEXT NOT NULL,
    spell_stable_key        TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, spell_stable_key)
);

CREATE TABLE character_group_heal_spells (
    character_stable_key    TEXT NOT NULL,
    spell_stable_key        TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, spell_stable_key)
);

CREATE TABLE character_cc_spells (
    character_stable_key    TEXT NOT NULL,
    spell_stable_key        TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, spell_stable_key)
);

CREATE TABLE character_taunt_spells (
    character_stable_key    TEXT NOT NULL,
    spell_stable_key        TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, spell_stable_key)
);

CREATE TABLE character_vendor_items (
    character_stable_key    TEXT NOT NULL,
    item_slot              INTEGER NOT NULL,
    item_stable_key         TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, item_slot)
);

CREATE TABLE character_aggressive_factions (
    character_stable_key    TEXT NOT NULL,
    faction_name            TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, faction_name)
);

CREATE TABLE character_allied_factions (
    character_stable_key    TEXT NOT NULL,
    faction_name            TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, faction_name)
);

CREATE TABLE character_faction_modifiers (
    character_stable_key    TEXT NOT NULL,
    faction_stable_key      TEXT NOT NULL,
    modifier_value          INTEGER,
    PRIMARY KEY (character_stable_key, faction_stable_key)
);

CREATE TABLE character_death_shouts (
    character_stable_key    TEXT NOT NULL,
    sequence_index          INTEGER NOT NULL,
    shout_text              TEXT,
    PRIMARY KEY (character_stable_key, sequence_index)
);

CREATE TABLE character_vendor_quest_unlocks (
    character_stable_key    TEXT NOT NULL,
    quest_stable_key        TEXT NOT NULL,
    quest_slot             INTEGER NOT NULL,
    quest_variant_resource_name TEXT NOT NULL REFERENCES quest_variants(resource_name),
    PRIMARY KEY (character_stable_key, quest_slot)
);

CREATE TABLE character_quest_manager_quests (
    character_stable_key    TEXT NOT NULL,
    quest_stable_key        TEXT NOT NULL,
    quest_slot             INTEGER NOT NULL,
    quest_variant_resource_name TEXT NOT NULL REFERENCES quest_variants(resource_name),
    PRIMARY KEY (character_stable_key, quest_slot)
);

-- -------------------------------------------------------------------------
-- Knowledge base of simulated-player chat, as the game ships it. Chat reads
-- the entries in position order, and an entry can be stale. zone_name is the
-- zone display name that chat says, or NULL when the entry has none.
-- -------------------------------------------------------------------------

CREATE TABLE knowledge_entries (
    position        INTEGER PRIMARY KEY,
    npc_name        TEXT NOT NULL,
    zone_name       TEXT,
    level           INTEGER NOT NULL,
    is_boss         INTEGER NOT NULL,
    prefab_path     TEXT NOT NULL
);

CREATE TABLE knowledge_entry_drops (
    entry_position  INTEGER NOT NULL REFERENCES knowledge_entries (position),
    position        INTEGER NOT NULL,
    item_name       TEXT NOT NULL,
    PRIMARY KEY (entry_position, position)
);

-- Every prefab character that matches the prefab file name in prefab_path,
-- the NPC name, and the level of an entry. Twin prefabs link both keys, and
-- an entry whose prefab no longer exists links none.
CREATE TABLE knowledge_entry_characters (
    entry_position        INTEGER NOT NULL REFERENCES knowledge_entries (position),
    character_stable_key  TEXT NOT NULL REFERENCES characters (stable_key),
    PRIMARY KEY (entry_position, character_stable_key)
);

-- -------------------------------------------------------------------------
-- Coordinates view (mirrors raw DB view, updated to snake_case tables)
-- -------------------------------------------------------------------------

CREATE VIEW coordinates AS
    SELECT stable_key, scene, x, y, z, 'Character'   AS category FROM characters WHERE scene IS NOT NULL
    UNION ALL
    SELECT spawn_point_stable_key AS stable_key, scene, x, y, z, 'SpawnPoint' AS category FROM character_spawns
        WHERE scene IS NOT NULL AND spawn_point_stable_key IS NOT NULL
    UNION ALL
    SELECT stable_key, scene, x, y, z, 'Door'        AS category FROM doors
    UNION ALL
    SELECT stable_key, scene, x, y, z, 'MiningNode'  AS category FROM mining_nodes
    UNION ALL
    SELECT stable_key, scene, x, y, z, 'Teleport'    AS category FROM teleports
    UNION ALL
    SELECT stable_key, scene, x, y, z, 'ZoneLine'    AS category FROM zone_lines
    UNION ALL
    SELECT stable_key, scene, x, y, z, 'Water'       AS category FROM waters
    UNION ALL
    SELECT stable_key, scene, x, y, z, 'ItemBag'     AS category FROM item_bags
    UNION ALL
    SELECT stable_key, scene, x, y, z, 'SecretPassage' AS category FROM secret_passages WHERE is_excluded = 0
    UNION ALL
    SELECT stable_key, scene, x, y, z, 'AchievementTrigger' AS category FROM achievement_triggers
    UNION ALL
    SELECT stable_key, scene, x, y, z, 'Forge'       AS category FROM forges
    UNION ALL
    SELECT stable_key, scene, x, y, z, 'WishingWell' AS category FROM wishing_wells
    UNION ALL
    SELECT stable_key, scene, x, y, z, 'TreasureLocation' AS category FROM treasure_locations;

-- -------------------------------------------------------------------------
-- Filtered spawn views
--
-- Use these views instead of character_spawns directly whenever filtering
-- by visibility is needed. The COALESCE ensures NULL (= inherit from
-- character-level) defaults to visible.
-- -------------------------------------------------------------------------

CREATE VIEW wiki_character_spawns AS
    SELECT * FROM character_spawns
    WHERE COALESCE(is_wiki_generated, 1) = 1;

CREATE VIEW map_character_spawns AS
    SELECT * FROM character_spawns
    WHERE COALESCE(is_map_visible, 1) = 1;

-- -------------------------------------------------------------------------
-- Characters and vendors in the game
--
-- A dedup group can hold copies that players never meet, such as unplaced
-- backup prefabs. Vendor items, vendor status, spells, and dialogs are not
-- part of the dedup identity, so such a copy can sell, cast, or give what the
-- copy in the game does not. Read a group's facts through
-- character_fact_sources and what vendors sell from vendor_offers, never
-- from the junction tables across a whole group.
-- -------------------------------------------------------------------------

-- Characters that a player can meet: placed or spawned, summoned by a spell,
-- a possible treasure chest, or a zone-wide candidate with a potential scene.
CREATE VIEW characters_in_game AS
    SELECT c.stable_key
    FROM characters c
    WHERE EXISTS (SELECT 1 FROM character_spawns s WHERE s.character_stable_key = c.stable_key)
       OR EXISTS (SELECT 1 FROM spells sp WHERE sp.pet_to_summon_stable_key = c.stable_key)
       OR EXISTS (
            SELECT 1 FROM treasure_chest_possible_spawns t WHERE t.chest_character_stable_key = c.stable_key
       )
       OR EXISTS (
            SELECT 1 FROM zone_wide_spawn_candidates candidate
            JOIN zone_wide_spawn_zones zone ON zone.rule_id = candidate.rule_id
            WHERE candidate.character_stable_key = c.stable_key
       );

-- The copies whose facts a dedup group shows: its copies in the game, or,
-- when the export places none of them, its copies that the mapping generates.
-- The second case keeps facts from unresolved scripted sources without claiming
-- a placement. The mapping excludes copies that a review found unused, such as
-- the Shopkeeper Treven prefab, which would otherwise sell Samuel Thatcher's
-- old stock.
CREATE VIEW character_fact_sources AS
    SELECT d.group_key, d.member_stable_key
    FROM character_deduplications d
    WHERE d.member_stable_key IN (SELECT stable_key FROM characters_in_game)
       OR d.is_wiki_generated = 1 AND NOT EXISTS (
            SELECT 1
            FROM character_deduplications other
            JOIN characters_in_game g ON g.stable_key = other.member_stable_key
            WHERE other.group_key = d.group_key
       );

-- One row per item that a copy of a vendor sells, among the copies of
-- character_fact_sources. The vendor is the copy's dedup group.
-- quest_stable_key names the quest whose completion adds the item to the
-- stock, and is NULL for an item that is always in stock.
CREATE VIEW vendor_offers AS
    SELECT s.group_key AS vendor_stable_key, s.member_stable_key AS copy_stable_key,
           cvi.item_stable_key AS item_stable_key, NULL AS quest_stable_key,
           'base' AS offer_kind, cvi.item_slot AS offer_slot, NULL AS quest_variant_key
    FROM character_fact_sources s
    JOIN character_vendor_items cvi ON cvi.character_stable_key = s.member_stable_key
    UNION ALL
    SELECT s.group_key, s.member_stable_key, qv.unlock_item_for_vendor_stable_key, cvqu.quest_stable_key,
           'quest_unlock', cvqu.quest_slot, cvqu.quest_variant_resource_name
    FROM character_fact_sources s
    JOIN character_vendor_quest_unlocks cvqu ON cvqu.character_stable_key = s.member_stable_key
    JOIN quest_variants qv ON qv.resource_name = cvqu.quest_variant_resource_name
    WHERE qv.unlock_item_for_vendor_stable_key IS NOT NULL;

CREATE TABLE ui_item_sources (
    stable_key TEXT PRIMARY KEY NOT NULL,
    component_type TEXT NOT NULL,
    scene TEXT NOT NULL,
    hierarchy_path TEXT NOT NULL,
    slot TEXT NOT NULL,
    icon_hierarchy_path TEXT NOT NULL,
    serialized_item_stable_key TEXT REFERENCES items(stable_key),
    serialized_quantity INTEGER NOT NULL,
    replenish_item_stable_key TEXT REFERENCES items(stable_key),
    replenish_source_key TEXT,
    display_only INTEGER NOT NULL,
    vendor_slot INTEGER NOT NULL,
    loot_slot INTEGER NOT NULL,
    bank_slot INTEGER NOT NULL,
    mouse_slot INTEGER NOT NULL,
    player_owned INTEGER NOT NULL,
    not_in_inventory INTEGER NOT NULL,
    slot_type TEXT NOT NULL
);
CREATE TABLE ui_item_access_targets (
    stable_key TEXT PRIMARY KEY NOT NULL,
    scene TEXT NOT NULL,
    hierarchy_path TEXT NOT NULL,
    tag TEXT NOT NULL,
    active_self INTEGER NOT NULL,
    active_in_hierarchy INTEGER NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL
);

CREATE TABLE item_access_observations (
    component_type TEXT NOT NULL,
    slot TEXT NOT NULL,
    assembly_sha256 TEXT NOT NULL,
    player_access_state TEXT NOT NULL,
    transfer TEXT NOT NULL,
    replenishment TEXT NOT NULL,
    receipt TEXT NOT NULL,
    PRIMARY KEY (component_type, slot, assembly_sha256)
);

CREATE TABLE item_provenance_meta (
    schema_version INTEGER NOT NULL,
    game_build_id TEXT NOT NULL,
    input_digests TEXT NOT NULL
);
CREATE TABLE item_acquisitions (
    acquisition_key TEXT PRIMARY KEY NOT NULL,
    item_stable_key TEXT NOT NULL REFERENCES items(stable_key),
    kind TEXT NOT NULL,
    source_stable_key TEXT,
    source_group_key TEXT,
    source_copy_stable_key TEXT,
    variant_key TEXT,
    mechanic TEXT,
    player_access_state TEXT NOT NULL CHECK (player_access_state IN
        ('verified_player', 'unconfirmed_player', 'internal_only', 'non_acquirable')),
    probability_kind TEXT NOT NULL CHECK (probability_kind IN
        ('exact', 'bounded', 'unknown', 'not_applicable')),
    probability_min REAL,
    probability_max REAL,
    probability_basis TEXT,
    probability_stage TEXT NOT NULL CHECK (probability_stage IN ('native_pool', 'final_acquisition')),
    quantity_min REAL,
    quantity_max REAL,
    quantity_kind TEXT NOT NULL,
    expected_quantity REAL,
    count_distribution TEXT,
    guarantee_scope TEXT,
    guaranteed_roll_count INTEGER
);
CREATE INDEX item_acquisitions_item_idx ON item_acquisitions(item_stable_key);
CREATE INDEX item_acquisitions_source_idx ON item_acquisitions(source_stable_key);
CREATE INDEX item_acquisitions_copy_idx ON item_acquisitions(source_copy_stable_key);
CREATE TABLE item_uses (
    use_key TEXT PRIMARY KEY NOT NULL,
    item_stable_key TEXT NOT NULL REFERENCES items(stable_key),
    target_stable_key TEXT,
    kind TEXT NOT NULL,
    variant_key TEXT,
    material_slot INTEGER,
    quantity_min REAL,
    quantity_max REAL,
    quantity_kind TEXT NOT NULL,
    mechanic TEXT,
    outcome_key TEXT
);
CREATE INDEX item_uses_item_idx ON item_uses(item_stable_key);
CREATE INDEX item_uses_target_idx ON item_uses(target_stable_key);
CREATE TABLE item_acquisition_conditions (
    owner_key TEXT NOT NULL REFERENCES item_acquisitions(acquisition_key),
    gate_key TEXT NOT NULL,
    group_index INTEGER NOT NULL,
    atom_index INTEGER NOT NULL,
    predicate TEXT NOT NULL,
    reference_stable_key TEXT,
    reference_slot TEXT,
    actor TEXT,
    value TEXT,
    minimum REAL,
    maximum REAL,
    minimum_inclusive INTEGER NOT NULL,
    maximum_inclusive INTEGER NOT NULL,
    scope TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'availability' CHECK (
        phase IN ('availability', 'source_initialization', 'operation_input', 'operation_outcome', 'mechanic_parameter')
    ),
    PRIMARY KEY (owner_key, gate_key, group_index, atom_index, scope, phase)
);
CREATE TABLE item_use_conditions (
    owner_key TEXT NOT NULL REFERENCES item_uses(use_key),
    gate_key TEXT NOT NULL,
    group_index INTEGER NOT NULL,
    atom_index INTEGER NOT NULL,
    predicate TEXT NOT NULL,
    reference_stable_key TEXT,
    reference_slot TEXT,
    actor TEXT,
    value TEXT,
    minimum REAL,
    maximum REAL,
    minimum_inclusive INTEGER NOT NULL,
    maximum_inclusive INTEGER NOT NULL,
    scope TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'availability' CHECK (
        phase IN ('availability', 'source_initialization', 'operation_input', 'operation_outcome', 'mechanic_parameter')
    ),
    PRIMARY KEY (owner_key, gate_key, group_index, atom_index, scope, phase)
);
CREATE TABLE item_acquisition_locations (
    owner_key TEXT NOT NULL REFERENCES item_acquisitions(acquisition_key),
    location_key TEXT NOT NULL,
    relation TEXT NOT NULL,
    scene TEXT,
    zone_stable_key TEXT,
    placement_key TEXT,
    coordinate_stable_key TEXT,
    x REAL, y REAL, z REAL,
    gate_scope TEXT,
    player_level_min INTEGER,
    player_level_max INTEGER,
    conditions TEXT NOT NULL,
    entry_zone_line_keys TEXT NOT NULL,
    source_copy_stable_key TEXT,
    PRIMARY KEY (owner_key, location_key)
);
CREATE TABLE item_use_locations (
    owner_key TEXT NOT NULL REFERENCES item_uses(use_key),
    location_key TEXT NOT NULL,
    relation TEXT NOT NULL,
    scene TEXT,
    zone_stable_key TEXT,
    placement_key TEXT,
    coordinate_stable_key TEXT,
    x REAL, y REAL, z REAL,
    gate_scope TEXT,
    player_level_min INTEGER,
    player_level_max INTEGER,
    conditions TEXT NOT NULL,
    entry_zone_line_keys TEXT NOT NULL,
    source_copy_stable_key TEXT,
    PRIMARY KEY (owner_key, location_key)
);
CREATE TABLE item_provenance_evidence (
    owner_key TEXT NOT NULL,
    input_relation TEXT NOT NULL,
    input_primary_key TEXT NOT NULL,
    PRIMARY KEY (owner_key, input_relation, input_primary_key)
);
CREATE INDEX item_provenance_evidence_input_idx
    ON item_provenance_evidence(input_relation, input_primary_key);
CREATE TABLE item_dispositions (
    item_stable_key TEXT PRIMARY KEY NOT NULL,
    disposition TEXT NOT NULL CHECK (disposition IN ('current', 'removed', 'unobtainable', 'unused')),
    reason TEXT,
    evidence TEXT,
    current_pages TEXT NOT NULL,
    former_pages TEXT NOT NULL
);
"""


class Writer:
    """Writes the clean SQLite database.

    Usage::

        writer = Writer(Path("erenshor-main.sqlite"))
        writer.create_schema()
        writer.insert_zones(rows)
        writer.insert_characters(rows)
        # ... all other entity types ...
        writer.finalize()
    """

    def __init__(self, path: Path) -> None:
        if path.exists():
            path.unlink()
            logger.debug(f"Removed existing clean DB: {path}")

        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row

    def create_schema(self) -> None:
        """Execute the full DDL to create all tables."""
        self._conn.executescript(_DDL)
        self._conn.commit()
        logger.debug("Clean DB schema created")

    @property
    def conn(self) -> sqlite3.Connection:
        """The underlying SQLite connection (for post-insert expansions)."""
        return self._conn

    # ------------------------------------------------------------------
    # Generic insert helper
    # ------------------------------------------------------------------

    def _insert(self, table: str, rows: list[dict[str, object]]) -> int:
        """Bulk-insert rows into a table.

        Args:
            table: Table name (snake_case).
            rows: List of dicts; keys are column names.

        Returns:
            Number of rows inserted.
        """
        if not rows:
            return 0
        columns = list(rows[0].keys())
        placeholders = ", ".join("?" * len(columns))
        col_list = ", ".join(columns)
        sql = f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})"
        values = [tuple(row[c] for c in columns) for row in rows]
        self._conn.executemany(sql, values)
        self._conn.commit()
        return len(rows)

    # ------------------------------------------------------------------
    # Per-table insert methods
    # ------------------------------------------------------------------

    def insert_teleports(self, rows: list[dict[str, object]]) -> int:
        return self._insert("teleports", rows)

    def insert_wishing_wells(self, rows: list[dict[str, object]]) -> int:
        return self._insert("wishing_wells", rows)

    def insert_achievement_triggers(self, rows: list[dict[str, object]]) -> int:
        return self._insert("achievement_triggers", rows)

    def insert_doors(self, rows: list[dict[str, object]]) -> int:
        return self._insert("doors", rows)

    def insert_forges(self, rows: list[dict[str, object]]) -> int:
        return self._insert("forges", rows)

    def insert_item_bags(self, rows: list[dict[str, object]]) -> int:
        return self._insert("item_bags", rows)

    def insert_mining_nodes(self, rows: list[dict[str, object]]) -> int:
        return self._insert("mining_nodes", rows)

    def insert_mining_node_items(self, rows: list[dict[str, object]]) -> int:
        return self._insert("mining_node_items", rows)

    def insert_treasure_locations(self, rows: list[dict[str, object]]) -> int:
        return self._insert("treasure_locations", rows)

    def insert_waters(self, rows: list[dict[str, object]]) -> int:
        return self._insert("waters", rows)

    def insert_water_fishables(self, rows: list[dict[str, object]]) -> int:
        return self._insert("water_fishables", rows)

    def insert_zone_lines(self, rows: list[dict[str, object]]) -> int:
        return self._insert("zone_lines", rows)

    def insert_zone_line_destination_contexts(self, rows: list[dict[str, object]]) -> int:
        return self._insert("zone_line_destination_contexts", rows)

    def insert_planning_portal_slots(self, rows: list[dict[str, object]]) -> int:
        return self._insert("planning_portal_slots", rows)

    def insert_gate_conditions(self, rows: list[dict[str, object]]) -> int:
        return self._insert("gate_conditions", rows)

    def insert_target_entries(self, rows: list[dict[str, object]]) -> int:
        return self._insert("target_entries", rows)

    def insert_barriers(self, rows: list[dict[str, object]]) -> int:
        return self._insert("barriers", rows)

    def insert_scripted_events(self, rows: list[dict[str, object]]) -> int:
        return self._insert("scripted_events", rows)

    def insert_scripted_event_conditions(self, rows: list[dict[str, object]]) -> int:
        return self._insert("scripted_event_conditions", rows)

    def insert_game_constants(self, rows: list[dict[str, object]]) -> int:
        return self._insert("game_constants", rows)

    def insert_code_facts(self, rows: list[dict[str, object]]) -> int:
        return self._insert("code_facts", rows)

    def insert_code_facts_meta(self, rows: list[dict[str, object]]) -> int:
        return self._insert("code_facts_meta", rows)

    def insert_secret_passages(self, rows: list[dict[str, object]]) -> int:
        return self._insert("secret_passages", rows)

    def insert_ascensions(self, rows: list[dict[str, object]]) -> int:
        return self._insert("ascensions", rows)

    def insert_books(self, rows: list[dict[str, object]]) -> int:
        return self._insert("books", rows)

    def insert_classes(self, rows: list[dict[str, object]]) -> int:
        return self._insert("classes", rows)

    def insert_authored_sims(self, rows: list[dict[str, object]]) -> int:
        return self._insert("authored_sims", rows)

    def insert_authored_sim_references(self, rows: list[dict[str, object]]) -> int:
        return self._insert("authored_sim_references", rows)

    def insert_authored_sim_equipment(self, rows: list[dict[str, object]]) -> int:
        return self._insert("authored_sim_equipment", rows)

    def insert_class_starting_items(self, rows: list[dict[str, object]]) -> int:
        return self._insert("class_starting_items", rows)

    def insert_guild_topics(self, rows: list[dict[str, object]]) -> int:
        return self._insert("guild_topics", rows)

    def insert_treasure_hunting(self, rows: list[dict[str, object]]) -> int:
        return self._insert("treasure_hunting", rows)

    def insert_zone_wide_spawn_rules(self, rows: list[dict[str, object]]) -> int:
        return self._insert("zone_wide_spawn_rules", rows)

    def insert_zone_wide_spawn_candidates(self, rows: list[dict[str, object]]) -> int:
        return self._insert("zone_wide_spawn_candidates", rows)

    def insert_zone_wide_spawn_zones(self, rows: list[dict[str, object]]) -> int:
        return self._insert("zone_wide_spawn_zones", rows)

    def insert_treasure_chest_possible_spawns(self, rows: list[dict[str, object]]) -> int:
        return self._insert("treasure_chest_possible_spawns", rows)

    def insert_treasure_guardian_scaling(self, rows: list[dict[str, object]]) -> int:
        return self._insert("treasure_guardian_scaling", rows)

    def insert_treasure_chest_waves(self, rows: list[dict[str, object]]) -> int:
        return self._insert("treasure_chest_waves", rows)

    def insert_character_ae_events(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_ae_events", rows)

    def insert_ae_event_mutations(self, rows: list[dict[str, object]]) -> int:
        return self._insert("ae_event_mutations", rows)

    def insert_zones(self, rows: list[dict[str, object]]) -> int:
        return self._insert("zones", rows)

    def insert_zone_atlas_entries(self, rows: list[dict[str, object]]) -> int:
        return self._insert("zone_atlas_entries", rows)

    def insert_zone_atlas_neighbors(self, rows: list[dict[str, object]]) -> int:
        return self._insert("zone_atlas_neighbors", rows)

    def insert_factions(self, rows: list[dict[str, object]]) -> int:
        return self._insert("factions", rows)

    def insert_items(self, rows: list[dict[str, object]]) -> int:
        return self._insert("items", rows)

    def insert_images(self, rows: list[dict[str, object]]) -> int:
        return self._insert("images", rows)

    def insert_image_sources(self, rows: list[dict[str, object]]) -> int:
        return self._insert("image_sources", rows)

    def insert_image_titles(self, rows: list[dict[str, object]]) -> int:
        return self._insert("image_titles", rows)

    def insert_item_renders(self, rows: list[dict[str, object]]) -> int:
        return self._insert("item_renders", rows)

    def insert_item_stats(self, rows: list[dict[str, object]]) -> int:
        return self._insert("item_stats", rows)

    def insert_item_classes(self, rows: list[dict[str, object]]) -> int:
        return self._insert("item_classes", rows)

    def insert_crafting_recipes(self, rows: list[dict[str, object]]) -> int:
        return self._insert("crafting_recipes", rows)

    def insert_crafting_rewards(self, rows: list[dict[str, object]]) -> int:
        return self._insert("crafting_rewards", rows)

    def insert_item_drops(self, rows: list[dict[str, object]]) -> int:
        return self._insert("item_drops", rows)

    def insert_auction_house_items(self, rows: list[dict[str, object]]) -> int:
        return self._insert("auction_house_items", rows)

    def insert_auction_house_brokers(self, rows: list[dict[str, object]]) -> int:
        return self._insert("auction_house_brokers", rows)

    def insert_common_world_items(self, rows: list[dict[str, object]]) -> int:
        return self._insert("common_world_items", rows)

    def insert_special_world_drops(self, rows: list[dict[str, object]]) -> int:
        return self._insert("special_world_drops", rows)

    def insert_item_model_parts(self, rows: list[dict[str, object]]) -> int:
        return self._insert("item_model_parts", rows)

    def insert_planning_table_furnishings(self, rows: list[dict[str, object]]) -> int:
        return self._insert("planning_table_furnishings", rows)

    def insert_item_conversions(self, rows: list[dict[str, object]]) -> int:
        return self._insert("item_conversions", rows)

    def insert_fishing_bonus_catches(self, rows: list[dict[str, object]]) -> int:
        return self._insert("fishing_bonus_catches", rows)

    def insert_item_zone_restrictions(self, rows: list[dict[str, object]]) -> int:
        return self._insert("item_zone_restrictions", rows)

    def insert_quality_offerings(self, rows: list[dict[str, object]]) -> int:
        return self._insert("quality_offerings", rows)

    def insert_spell_created_items(self, rows: list[dict[str, object]]) -> int:
        return self._insert("spell_created_items", rows)

    def insert_spells(self, rows: list[dict[str, object]]) -> int:
        return self._insert("spells", rows)

    def insert_spell_classes(self, rows: list[dict[str, object]]) -> int:
        return self._insert("spell_classes", rows)

    def insert_skills(self, rows: list[dict[str, object]]) -> int:
        return self._insert("skills", rows)

    def insert_stances(self, rows: list[dict[str, object]]) -> int:
        return self._insert("stances", rows)

    def insert_quests(self, rows: list[dict[str, object]]) -> int:
        return self._insert("quests", rows)

    def insert_quest_variants(self, rows: list[dict[str, object]]) -> int:
        return self._insert("quest_variants", rows)

    def insert_quest_required_items(self, rows: list[dict[str, object]]) -> int:
        return self._insert("quest_required_items", rows)

    def insert_quest_faction_affects(self, rows: list[dict[str, object]]) -> int:
        return self._insert("quest_faction_affects", rows)

    def insert_quest_complete_other_quests(self, rows: list[dict[str, object]]) -> int:
        return self._insert("quest_complete_other_quests", rows)

    def insert_quest_character_roles(self, rows: list[dict[str, object]]) -> int:
        return self._insert("quest_character_roles", rows)

    def insert_quest_completion_sources(self, rows: list[dict[str, object]]) -> int:
        return self._insert("quest_completion_sources", rows)

    def insert_quest_acquisition_sources(self, rows: list[dict[str, object]]) -> int:
        return self._insert("quest_acquisition_sources", rows)

    def insert_characters(self, rows: list[dict[str, object]]) -> int:
        return self._insert("characters", rows)

    def insert_character_damage_releases(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_damage_releases", rows)

    def insert_encounter_placements(self, rows: list[dict[str, object]]) -> int:
        return self._insert("encounter_placements", rows)

    def insert_encounter_conditions(self, rows: list[dict[str, object]]) -> int:
        return self._insert("encounter_conditions", rows)

    def insert_encounter_completions(self, rows: list[dict[str, object]]) -> int:
        return self._insert("encounter_completions", rows)

    def insert_encounter_event_conditions(self, rows: list[dict[str, object]]) -> int:
        return self._insert("encounter_event_conditions", rows)

    def insert_character_deduplications(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_deduplications", rows)

    def insert_knowledge_entries(self, rows: list[dict[str, object]]) -> int:
        return self._insert("knowledge_entries", rows)

    def insert_knowledge_entry_drops(self, rows: list[dict[str, object]]) -> int:
        return self._insert("knowledge_entry_drops", rows)

    def insert_knowledge_entry_characters(self, rows: list[dict[str, object]]) -> int:
        return self._insert("knowledge_entry_characters", rows)

    def insert_character_spawns(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_spawns", rows)

    def insert_character_chained_spawns(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_chained_spawns", rows)

    def insert_spawn_point_patrol_points(self, rows: list[dict[str, object]]) -> int:
        return self._insert("spawn_point_patrol_points", rows)

    def insert_spawn_point_stop_quests(self, rows: list[dict[str, object]]) -> int:
        return self._insert("spawn_point_stop_quests", rows)

    def insert_spawnpoint_essential_links(self, rows: list[dict[str, object]]) -> int:
        return self._insert("spawnpoint_essential_links", rows)

    def insert_loot_drops(self, rows: list[dict[str, object]]) -> int:
        return self._insert("loot_drops", rows)

    def insert_arena_rounds(self, rows: list[dict[str, object]]) -> int:
        return self._insert("arena_rounds", rows)

    def insert_arena_round_enemies(self, rows: list[dict[str, object]]) -> int:
        return self._insert("arena_round_enemies", rows)

    def insert_character_dialogs(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_dialogs", rows)

    def insert_character_attack_skills(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_attack_skills", rows)

    def insert_character_attack_spells(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_attack_spells", rows)

    def insert_character_buff_spells(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_buff_spells", rows)

    def insert_character_heal_spells(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_heal_spells", rows)

    def insert_character_group_heal_spells(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_group_heal_spells", rows)

    def insert_character_cc_spells(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_cc_spells", rows)

    def insert_character_taunt_spells(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_taunt_spells", rows)

    def insert_character_vendor_items(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_vendor_items", rows)

    def insert_character_aggressive_factions(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_aggressive_factions", rows)

    def insert_character_allied_factions(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_allied_factions", rows)

    def insert_character_faction_modifiers(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_faction_modifiers", rows)

    def insert_character_death_shouts(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_death_shouts", rows)

    def insert_character_vendor_quest_unlocks(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_vendor_quest_unlocks", rows)

    def insert_character_quest_manager_quests(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_quest_manager_quests", rows)

    # ------------------------------------------------------------------
    # Finalise
    # ------------------------------------------------------------------

    def finalize(self) -> None:
        """Run VACUUM + ANALYZE, switch to DELETE journal mode, and close.

        VACUUM rebuilds the database. We then switch journal mode back to
        DELETE so the file is self-contained (no -shm/-wal siblings) and
        readable with any SQLite connection flags.
        """
        self._conn.execute("PRAGMA foreign_keys = OFF")
        self._conn.execute("VACUUM")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("ANALYZE")
        self._conn.execute("PRAGMA journal_mode = DELETE")
        self._conn.commit()
        self._conn.close()
        logger.info(f"Clean DB finalised: {self._path}")
