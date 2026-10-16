SELECT
    class_name,
    display_name,
    mitigation_bonus,
    str_benefit,
    end_benefit,
    dex_benefit,
    agi_benefit,
    int_benefit,
    wis_benefit,
    cha_benefit,
    aggro_mod,
    resource_name
FROM classes
-- Default is the game's template class, which players cannot pick.
WHERE class_name != 'Default'
ORDER BY class_name;
