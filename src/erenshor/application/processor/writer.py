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
    respawn_time    REAL
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
    is_enabled                  INTEGER,
    display_text                TEXT,
    destination_zone_stable_key TEXT,
    landing_position_x          REAL,
    landing_position_y          REAL,
    landing_position_z          REAL,
    remove_party                INTEGER
);

CREATE TABLE zone_line_quest_unlocks (
    zone_line_stable_key    TEXT NOT NULL,
    unlock_group            INTEGER NOT NULL,
    quest_db_name           TEXT NOT NULL,
    PRIMARY KEY (zone_line_stable_key, unlock_group, quest_db_name)
);

CREATE TABLE character_quest_unlocks (
    character_stable_key    TEXT NOT NULL,
    unlock_group            INTEGER NOT NULL,
    quest_db_name           TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, unlock_group, quest_db_name)
);

CREATE TABLE game_constants (
    key         TEXT PRIMARY KEY NOT NULL,
    value       TEXT,
    value_type  TEXT,
    description TEXT
);

CREATE TABLE secret_passages (
    stable_key  TEXT PRIMARY KEY NOT NULL,
    scene       TEXT,
    x           REAL,
    y           REAL,
    z           REAL,
    object_name TEXT,
    type        TEXT
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
    healing_increase                REAL,
    critical_dot_chance             REAL,
    critical_healing_chance         REAL,
    vengeful_healing_percentage     REAL,
    summoned_beast_enhancement      REAL,
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

CREATE TABLE treasure_hunting (
    zone_name               TEXT PRIMARY KEY NOT NULL,
    zone_display_name       TEXT,
    is_pickable_always      INTEGER,
    is_pickable_greater_20  INTEGER,
    is_pickable_greater_30  INTEGER
);

-- -------------------------------------------------------------------------
-- Zones
-- -------------------------------------------------------------------------

CREATE TABLE zones (
    stable_key                              TEXT PRIMARY KEY NOT NULL,
    scene_name                              TEXT,
    zone_name                               TEXT NOT NULL,
    display_name                            TEXT NOT NULL,
    wiki_page_name                          TEXT,
    image_name                              TEXT NOT NULL,
    is_wiki_generated                       INTEGER NOT NULL DEFAULT 1,
    is_map_visible                          INTEGER NOT NULL DEFAULT 1,
    is_dungeon                              INTEGER,
    achievement                             TEXT,
    complete_quest_on_enter_stable_key      TEXT,
    complete_second_quest_on_enter_stable_key TEXT,
    assign_quest_on_enter_stable_key        TEXT,
    north_bearing                           REAL
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
    drop_probability        REAL,
    is_guaranteed           INTEGER,
    PRIMARY KEY (source_item_stable_key, dropped_item_stable_key)
);


CREATE TABLE spell_created_items (
    source_item_stable_key   TEXT NOT NULL,
    spell_stable_key         TEXT NOT NULL,
    created_item_stable_key  TEXT NOT NULL,
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
    is_wiki_generated                   INTEGER NOT NULL DEFAULT 1,
    is_map_visible                      INTEGER NOT NULL DEFAULT 1,
    spell_desc                          TEXT,
    special_descriptor                  TEXT,
    type                                TEXT,
    line                                TEXT,
    required_level                      INTEGER,
    mana_cost                           INTEGER,
    sim_usable                          INTEGER,
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
    item_stable_key             TEXT NOT NULL,
    quantity                    INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (quest_variant_resource_name, item_stable_key)
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
    is_wiki_generated           INTEGER NOT NULL DEFAULT 1,
    is_map_visible              INTEGER NOT NULL DEFAULT 1,
    scene                       TEXT,
    x                           REAL,
    y                           REAL,
    z                           REAL,
    guid                        TEXT,
    my_world_faction_stable_key TEXT,
    my_faction                  TEXT,
    aggro_range                 REAL,
    attack_range                REAL,
    aggressive_towards          TEXT,
    allies                      TEXT,
    is_prefab                   INTEGER,
    is_common                   INTEGER,
    is_rare                     INTEGER,
    is_unique                   INTEGER,
    is_friendly                 INTEGER,
    is_npc                      INTEGER,
    is_vendor                   INTEGER,
    is_mining_node              INTEGER,
    has_stats                   INTEGER,
    has_dialog                  INTEGER,
    has_modify_faction          INTEGER,
    is_enabled                  INTEGER,
    invulnerable                INTEGER,
    shout_on_death              TEXT,
    quest_complete_on_death     TEXT,
    shout_trigger_quest_stable_key TEXT,
    shout_trigger_keyword       TEXT,
    destroy_on_death            INTEGER,
    level                       INTEGER,
    base_xp_min                 REAL,
    base_xp_max                 REAL,
    boss_xp_multiplier          REAL,
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
    proc_on_hit_stable_key      TEXT,
    proc_on_hit_chance          REAL,
    hand_set_resistances        INTEGER,
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
    PRIMARY KEY (character_stable_key, spawn_point_stable_key, is_directly_placed)
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

CREATE TABLE loot_drops (
    character_stable_key    TEXT NOT NULL,
    item_stable_key         TEXT NOT NULL,
    drop_probability        REAL,
    expected_per_kill       REAL,
    drop_count_distribution TEXT,
    is_actual               INTEGER,
    is_guaranteed           INTEGER,
    is_common               INTEGER,
    is_uncommon             INTEGER,
    is_rare                 INTEGER,
    is_legendary            INTEGER,
    is_ultra_rare           INTEGER,
    is_unique               INTEGER,
    is_visible              INTEGER,
    zone                    TEXT,
    PRIMARY KEY (character_stable_key, item_stable_key)
);

CREATE TABLE character_dialogs (
    character_stable_key        TEXT NOT NULL,
    dialog_index                INTEGER NOT NULL,
    dialog_text                 TEXT,
    keywords                    TEXT,
    give_item_stable_key        TEXT,
    assign_quest_stable_key     TEXT,
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
    item_stable_key         TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, item_stable_key)
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
    PRIMARY KEY (character_stable_key, quest_stable_key)
);

CREATE TABLE character_quest_manager_quests (
    character_stable_key    TEXT NOT NULL,
    quest_stable_key        TEXT NOT NULL,
    PRIMARY KEY (character_stable_key, quest_stable_key)
);

-- -------------------------------------------------------------------------
-- Coordinates view (mirrors raw DB view, updated to snake_case tables)
-- -------------------------------------------------------------------------

CREATE VIEW coordinates AS
    SELECT stable_key, scene, x, y, z, 'Character'   AS category FROM characters WHERE scene IS NOT NULL
    UNION ALL
    SELECT stable_key, scene, x, y, z, 'SpawnPoint'  AS category FROM character_spawns
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
    SELECT stable_key, scene, x, y, z, 'SecretPassage' AS category FROM secret_passages
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

    def insert_zone_line_quest_unlocks(self, rows: list[dict[str, object]]) -> int:
        return self._insert("zone_line_quest_unlocks", rows)

    def insert_character_quest_unlocks(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_quest_unlocks", rows)

    def insert_game_constants(self, rows: list[dict[str, object]]) -> int:
        return self._insert("game_constants", rows)

    def insert_secret_passages(self, rows: list[dict[str, object]]) -> int:
        return self._insert("secret_passages", rows)

    def insert_ascensions(self, rows: list[dict[str, object]]) -> int:
        return self._insert("ascensions", rows)

    def insert_books(self, rows: list[dict[str, object]]) -> int:
        return self._insert("books", rows)

    def insert_classes(self, rows: list[dict[str, object]]) -> int:
        return self._insert("classes", rows)

    def insert_guild_topics(self, rows: list[dict[str, object]]) -> int:
        return self._insert("guild_topics", rows)

    def insert_treasure_hunting(self, rows: list[dict[str, object]]) -> int:
        return self._insert("treasure_hunting", rows)

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

    def insert_character_deduplications(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_deduplications", rows)

    def insert_character_spawns(self, rows: list[dict[str, object]]) -> int:
        return self._insert("character_spawns", rows)

    def insert_spawn_point_patrol_points(self, rows: list[dict[str, object]]) -> int:
        return self._insert("spawn_point_patrol_points", rows)

    def insert_spawn_point_stop_quests(self, rows: list[dict[str, object]]) -> int:
        return self._insert("spawn_point_stop_quests", rows)

    def insert_loot_drops(self, rows: list[dict[str, object]]) -> int:
        return self._insert("loot_drops", rows)

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
        """Run VACUUM + ANALYZE and close the connection."""
        self._conn.execute("PRAGMA foreign_keys = OFF")
        self._conn.execute("VACUUM")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("ANALYZE")
        self._conn.commit()
        self._conn.close()
        logger.info(f"Clean DB finalised: {self._path}")
