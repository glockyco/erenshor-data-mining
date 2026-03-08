SELECT
    -- Identity & Basic Info
    c.stable_key,
    c.object_name,
    c.display_name,
    f.faction_desc AS my_world_faction,
    c.my_faction,
    c.level,
    -- Effective Combat Stats (calculated runtime values players encounter)
    c.effective_hp,
    c.effective_ac,
    c.effective_attack_ability,
    c.effective_base_atk_dmg,
    c.effective_min_mr,
    c.effective_max_mr,
    c.effective_min_er,
    c.effective_max_er,
    c.effective_min_pr,
    c.effective_max_pr,
    c.effective_min_vr,
    c.effective_max_vr,
    -- Base Stats (no effective version exists)
    c.base_mana,
    c.base_str,
    c.base_end,
    c.base_dex,
    c.base_agi,
    c.base_int,
    c.base_wis,
    c.base_cha,
    c.base_res,
    c.run_speed,
    c.base_life_steal,
    c.base_mh_atk_delay,
    c.base_oh_atk_delay,
    -- XP & Rewards
    c.base_xp_min,
    c.base_xp_max,
    c.boss_xp_multiplier,
    -- Combat Mechanics
    c.oh_atk_dmg,
    c.min_atk_dmg,
    c.damage_range_min,
    c.damage_range_max,
    c.damage_mult,
    c.armor_pen_mult,
    c.power_attack_base_dmg,
    c.power_attack_freq,
    c.heal_tolerance,
    -- AI Behavior & Movement
    c.aggro_range,
    c.attack_range,
    c.leash_range,
    (SELECT GROUP_CONCAT(faction_name, ', ')
     FROM character_aggressive_factions caf
     WHERE caf.character_stable_key = c.stable_key) AS aggressive_towards_factions,
    (SELECT GROUP_CONCAT(faction_name, ', ')
     FROM character_allied_factions calf
     WHERE calf.character_stable_key = c.stable_key) AS allied_factions,
    (SELECT GROUP_CONCAT(faction_stable_key || ' (' || modifier_value || ')', ', ')
     FROM character_faction_modifiers cfm
     WHERE cfm.character_stable_key = c.stable_key) AS faction_modifier_stable_keys,
    c.mobile,
    c.group_encounter,
    c.aggro_regardless_of_level,
    -- Spells & Abilities
    c.pet_spell_stable_key,
    c.proc_on_hit_stable_key,
    c.proc_on_hit_chance,
    (SELECT GROUP_CONCAT(spell_stable_key, ', ')
     FROM character_attack_spells cas
     WHERE cas.character_stable_key = c.stable_key) AS attack_spell_stable_keys,
    (SELECT GROUP_CONCAT(spell_stable_key, ', ')
     FROM character_buff_spells cbs
     WHERE cbs.character_stable_key = c.stable_key) AS buff_spell_stable_keys,
    (SELECT GROUP_CONCAT(spell_stable_key, ', ')
     FROM character_heal_spells chs
     WHERE chs.character_stable_key = c.stable_key) AS heal_spell_stable_keys,
    (SELECT GROUP_CONCAT(spell_stable_key, ', ')
     FROM character_group_heal_spells cghs
     WHERE cghs.character_stable_key = c.stable_key) AS group_heal_spell_stable_keys,
    (SELECT GROUP_CONCAT(spell_stable_key, ', ')
     FROM character_cc_spells cccs
     WHERE cccs.character_stable_key = c.stable_key) AS cc_spell_stable_keys,
    (SELECT GROUP_CONCAT(spell_stable_key, ', ')
     FROM character_taunt_spells cts
     WHERE cts.character_stable_key = c.stable_key) AS taunt_spell_stable_keys,
    (SELECT GROUP_CONCAT(skill_stable_key, ', ')
     FROM character_attack_skills cask
     WHERE cask.character_stable_key = c.stable_key) AS attack_skill_stable_keys,
    -- Special Properties & Quest Integration
    c.invulnerable,
    c.quest_complete_on_death AS quest_complete_on_death_stable_key,
    c.set_achievement_on_defeat,
    c.set_achievement_on_spawn,
    -- Flavor Text & Messages
    c.aggro_msg,
    c.aggro_emote,
    c.spawn_emote,
    c.shout_on_death,
    -- Vendor Information
    c.is_vendor,
    c.vendor_desc,
    (SELECT GROUP_CONCAT(item_stable_key, ', ')
     FROM character_vendor_items cvi
     WHERE cvi.character_stable_key = c.stable_key) AS vendor_item_stable_keys
FROM characters c
LEFT JOIN factions f ON f.stable_key = c.my_world_faction_stable_key;
