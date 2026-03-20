-- Consolidated quest information
SELECT
    qv.quest_db_index,
    q.stable_key,
    qv.quest_name,
    qv.quest_desc,
    COALESCE(
        (SELECT GROUP_CONCAT(DISTINCT method) FROM quest_completion_sources WHERE quest_stable_key = q.stable_key),
        'unknown'
    ) AS completion_methods,
    COALESCE(
        (SELECT GROUP_CONCAT(DISTINCT method) FROM quest_acquisition_sources WHERE quest_stable_key = q.stable_key),
        'unknown'
    ) AS acquisition_methods,

    -- Rewards
    qv.xp_on_complete,
    qv.gold_on_complete,
    reward_item.display_name AS reward_item,
    next_quest_variant.quest_name AS next_quest,
    unlock_item.display_name AS unlock_item_for_vendor,

    -- NPC Relationships (aggregated)
    (SELECT GROUP_CONCAT(DISTINCT c.display_name)
     FROM quest_character_roles qcr
     JOIN characters c ON c.stable_key = qcr.character_stable_key
     WHERE qcr.quest_stable_key = q.stable_key AND qcr.role = 'giver'
    ) AS giver_npcs,
    -- Acquisition sources (all methods, not just dialog givers)
    (SELECT GROUP_CONCAT(DISTINCT
        CASE qas.source_type
            WHEN 'character' THEN c.display_name || ' (' || qas.method || ')'
            WHEN 'item' THEN i.display_name || ' (' || qas.method || ')'
            WHEN 'zone' THEN z.display_name || ' (' || qas.method || ')'
            WHEN 'quest' THEN qv2.quest_name || ' (' || qas.method || ')'
            ELSE qas.note
        END)
     FROM quest_acquisition_sources qas
     LEFT JOIN characters c ON c.stable_key = qas.source_stable_key AND qas.source_type = 'character'
     LEFT JOIN items i ON i.stable_key = qas.source_stable_key AND qas.source_type = 'item'
     LEFT JOIN zones z ON z.stable_key = qas.source_stable_key AND qas.source_type = 'zone'
     LEFT JOIN quest_variants qv2 ON qv2.quest_stable_key = qas.source_stable_key AND qas.source_type = 'quest'
     WHERE qas.quest_stable_key = q.stable_key
    ) AS acquisition_sources,
    (SELECT GROUP_CONCAT(DISTINCT c.display_name)
     FROM quest_character_roles qcr
     JOIN characters c ON c.stable_key = qcr.character_stable_key
     WHERE qcr.quest_stable_key = q.stable_key AND qcr.role = 'completer'
    ) AS completer_npcs,
    (SELECT GROUP_CONCAT(DISTINCT c.display_name)
     FROM quest_character_roles qcr
     JOIN characters c ON c.stable_key = qcr.character_stable_key
     WHERE qcr.quest_stable_key = q.stable_key AND qcr.role = 'item_turnin'
    ) AS item_turnin_npcs,

    -- Required Items (aggregated)
    (SELECT GROUP_CONCAT(DISTINCT CASE WHEN qri.quantity > 1 THEN qri.quantity || 'x ' || i.display_name ELSE i.display_name END)
     FROM quest_required_items qri
     JOIN items i ON i.stable_key = qri.item_stable_key
     WHERE qri.quest_variant_resource_name = qv.resource_name
    ) AS required_items,

    -- Faction Impacts (aggregated with modifier)
    (SELECT GROUP_CONCAT(DISTINCT f.faction_name || ' (' || qfa.modifier_value || ')')
     FROM quest_faction_affects qfa
     JOIN factions f ON f.stable_key = qfa.faction_stable_key
     WHERE qfa.quest_variant_resource_name = qv.resource_name
    ) AS faction_affects,

    -- Quest Chains - this quest completes other quests
    (SELECT GROUP_CONCAT(DISTINCT completed_qv.quest_name)
     FROM quest_complete_other_quests qcoq
     JOIN quest_variants completed_qv ON completed_qv.quest_stable_key = qcoq.completed_quest_stable_key
     WHERE qcoq.quest_variant_resource_name = qv.resource_name
    ) AS completes_quests,

    -- Quest Chains - quests that complete this quest
    (SELECT GROUP_CONCAT(DISTINCT completing_qv.quest_name)
     FROM quest_complete_other_quests qcoq
     JOIN quest_variants completing_qv ON completing_qv.resource_name = qcoq.quest_variant_resource_name
     WHERE qcoq.completed_quest_stable_key = q.stable_key
    ) AS completed_by_quests,

    -- Flags
    qv.repeatable,
    qv.disable_quest,
    qv.kill_turn_in_holder,
    qv.destroy_turn_in_holder,
    qv.drop_invuln_on_holder,
    qv.once_per_spawn_instance,
    qv.assign_this_quest_on_partial_complete,

    -- Achievements
    qv.set_achievement_on_get,
    qv.set_achievement_on_finish,

    -- Dialog
    qv.dialog_on_success,
    qv.dialog_on_partial_success,
    qv.disable_text

FROM quests q
LEFT JOIN quest_variants qv ON qv.quest_stable_key = q.stable_key
LEFT JOIN items reward_item ON reward_item.stable_key = qv.item_on_complete_stable_key
LEFT JOIN items unlock_item ON unlock_item.stable_key = qv.unlock_item_for_vendor_stable_key
LEFT JOIN quest_variants next_quest_variant ON next_quest_variant.quest_stable_key = qv.assign_new_quest_on_complete_stable_key
ORDER BY qv.quest_db_index;
