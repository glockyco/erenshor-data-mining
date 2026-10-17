SELECT
    i.item_db_index,
    i.id,
    i.stable_key,
    i.display_name,
    i.lore,
    i.required_slot,
    i.this_weapon_type,
    (SELECT GROUP_CONCAT(c.display_name, ', ' ORDER BY c.display_name)
     FROM item_classes ic
     JOIN classes c ON ic.class_name = c.class_name
     WHERE ic.item_stable_key = i.stable_key) AS classes,
    s.quality,
    i.item_level,
    s.hp,
    s.ac,
    s.mana,
    s.str,
    s.end,
    s.dex,
    s.agi,
    s.int,
    s.wis,
    s.cha,
    s.res,
    s.mr,
    s.er,
    s.pr,
    s.vr,
    s.str_scaling,
    s.end_scaling,
    s.dex_scaling,
    s.agi_scaling,
    s.int_scaling,
    s.wis_scaling,
    s.cha_scaling,
    s.resist_scaling,
    s.mitigation_scaling,
    s.weapon_dmg,
    i.weapon_dly,
    i.shield,
    i.weapon_proc_chance,
    i.weapon_proc_on_hit_stable_key,
    i.is_wand,
    i.wand_range,
    i.wand_proc_chance,
    i.wand_effect_stable_key,
    i.is_bow,
    i.bow_effect_stable_key,
    i.bow_proc_chance,
    i.bow_range,
    i.item_effect_on_click_stable_key,
    i.item_skill_use_stable_key,
    i.teach_spell_stable_key,
    i.teach_skill_stable_key,
    i.aura_stable_key,
    i.worn_effect_stable_key,
    i.spell_cast_time,
    i.assign_quest_on_read_stable_key,
    i.complete_on_read_stable_key,
    i.template,
    (SELECT GROUP_CONCAT(u.item_stable_key, ', ' ORDER BY u.material_slot, u.use_key)
     FROM item_uses u
     WHERE u.kind = 'crafting_material' AND u.target_stable_key = i.stable_key
    ) AS template_ingredient_stable_keys,
    (SELECT GROUP_CONCAT(a.item_stable_key, ', ' ORDER BY a.variant_key, a.acquisition_key)
     FROM item_acquisitions a
     WHERE a.kind = 'crafting' AND a.source_stable_key = i.stable_key
         AND a.player_access_state = 'verified_player'
         AND a.probability_stage = 'final_acquisition') AS template_reward_stable_key,
    i.item_value,
    i.sell_value,
    i.stackable,
    i.disposable,
    i.is_unique,
    i.relic,
    i.furniture_set,
    i.no_trade_no_destroy,
    i.must_be_equipped_to_click,
    i.player_cannot_sell,
    i.rare_item,
    i.is_auctionable,
    EXISTS (SELECT 1 FROM item_acquisitions a
            WHERE a.item_stable_key = i.stable_key AND a.kind = 'auction_house'
                AND a.player_access_state = 'verified_player'
                AND a.probability_stage = 'final_acquisition') AS can_be_listed_by_sims,
    i.book_title,
    i.mining,
    i.fuel_source,
    i.fuel_level,
    i.sim_players_cant_get,
    i.attack_sound_name,
    i.item_icon_name,
    i.equipment_to_activate,
    i.hide_hair_when_equipped,
    i.hide_head_when_equipped,
    i.resource_name
FROM items i
LEFT JOIN item_stats s ON s.item_stable_key = i.stable_key
ORDER BY i.item_db_index,
    CASE s.quality
        WHEN 'Standard' THEN 1
        WHEN 'Improved +1' THEN 2
        WHEN 'Improved +2' THEN 3
        WHEN 'Improved +3' THEN 4
        WHEN 'Improved +4' THEN 5
        WHEN 'Improved +5' THEN 6
        WHEN 'Blessed' THEN 7
        WHEN 'Ascended' THEN 8
        ELSE 9
    END;
