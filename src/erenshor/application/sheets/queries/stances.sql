SELECT
    stable_key,
    display_name,
    stance_desc,
    max_hp_mod,
    damage_mod,
    spell_damage_mod,
    damage_taken_mod,
    proc_rate_mod,
    aggro_gen_mod,
    lifesteal_amount,
    resonance_amount,
    self_damage_per_attack,
    self_damage_per_cast,
    stop_regen,
    switch_message,
    resource_name
FROM stances
ORDER BY display_name;
