-- Rates stay numeric. Bounds, guarantees and contributing outcomes remain separate facts.
SELECT
    CASE a.kind
        WHEN 'character_drop' THEN 'Character'
        WHEN 'common_world_item' THEN 'Common world item'
        WHEN 'special_world_drop' THEN 'World Drop'
        WHEN 'item_drop' THEN 'Item'
    END AS 'Source Type',
    CASE a.kind
        WHEN 'common_world_item' THEN 'Common world item'
        WHEN 'special_world_drop' THEN 'World Drop'
        ELSE COALESCE(c.display_name, src.display_name, a.source_stable_key)
    END AS 'Source',
    i.display_name AS 'Dropped Item',
    CASE WHEN a.probability_kind = 'exact' THEN a.probability_min END AS 'Drop Chance (%)',
    a.expected_quantity AS 'Expected Per Drop',
    a.count_distribution AS 'Drop Count Distribution',
    a.guarantee_scope AS 'Guarantee Scope',
    COALESCE(c.object_name, src.resource_name) AS 'Source Prefab/Resource',
    i.resource_name AS 'Item Resource Name',
    a.*
FROM item_acquisitions a
LEFT JOIN items i ON i.stable_key = a.item_stable_key
LEFT JOIN characters c ON c.stable_key = a.source_copy_stable_key AND a.kind = 'character_drop'
LEFT JOIN items src ON src.stable_key = a.source_stable_key AND a.kind = 'item_drop'
WHERE a.kind IN ('character_drop', 'common_world_item', 'special_world_drop', 'item_drop')
    AND a.player_access_state = 'verified_player'
    AND a.probability_stage = 'final_acquisition'
ORDER BY
    CASE a.kind WHEN 'item_drop' THEN 0 WHEN 'character_drop' THEN 1 WHEN 'common_world_item' THEN 1 ELSE 2 END,
    "Source", a.probability_min DESC, a.acquisition_key;
