SELECT
    cs.spawn_point_stable_key AS id,
    z.scene_name,
    z.zone_name,
    ROUND(cs.x, 2) AS position_x,
    ROUND(cs.y, 2) AS position_y,
    ROUND(cs.z, 2) AS position_z,
    cs.is_directly_placed,
    cs.is_enabled,
    c.stable_key AS character_stable_key,
    c.display_name,
    ROUND(cs.spawn_chance, 2) AS spawn_chance_percent,
    cs.is_common,
    cs.is_rare,
    c.is_unique,
    cs.level_mod,
    cs.spawn_delay_1 AS spawn_delay_1_in_grp,
    ROUND(cs.spawn_delay_2, 2) AS spawn_delay_2_in_grp,
    ROUND(cs.spawn_delay_3, 2) AS spawn_delay_3_in_grp,
    ROUND(cs.spawn_delay_4, 2) AS spawn_delay_4_in_grp,
    cs.staggerable,
    cs.stagger_mod,
    cs.night_spawn AS is_night_spawn,
    cs.patrol_points,
    cs.loop_patrol,
    cs.random_wander_range,
    cs.spawn_upon_quest_complete_stable_key,
    (SELECT GROUP_CONCAT(quest_stable_key, ', ')
     FROM spawn_point_stop_quests spsq
     WHERE spsq.spawn_point_stable_key = cs.spawn_point_stable_key) AS stop_if_quest_complete_stable_keys,
    'https://erenshor-maps.wowmuch1.workers.dev/map?marker=' || cs.spawn_point_stable_key AS MapLink
FROM
    character_spawns cs
    JOIN characters c ON c.stable_key = cs.character_stable_key
    JOIN zones z ON z.stable_key = cs.zone_stable_key
WHERE
    cs.spawn_point_stable_key IS NOT NULL
ORDER BY
    z.scene_name,
    cs.is_directly_placed,
    spawn_chance_percent DESC,
    c.display_name;
