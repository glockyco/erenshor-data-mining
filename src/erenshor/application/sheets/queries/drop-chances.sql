-- Drop chances from characters and items (fossils, etc.)
WITH
    -- Item drops from consumables (e.g., Braxonian Fossil)
    consumable_drops AS (
        SELECT
            'Item' AS source_type,
            src.display_name AS source,
            dropped.display_name AS dropped_item,
            ROUND(id.drop_probability, 2) AS drop_chance,
            NULL AS expected_per_drop,
            NULL AS drop_count_distribution,
            id.is_guaranteed,
            0 AS is_unique,
            0 AS is_visible,
            src.resource_name AS source_prefab_resource,
            dropped.resource_name AS item_resource_name
        FROM item_drops id
        JOIN items src ON id.source_item_stable_key = src.stable_key
        JOIN items dropped ON id.dropped_item_stable_key = dropped.stable_key
    ),
    -- Character drops
    character_drops AS (
        SELECT
            'Character' AS source_type,
            c.display_name AS source,
            i.display_name AS dropped_item,
            ROUND(ld.drop_probability, 2) AS drop_chance,
            ROUND(ld.expected_per_kill, 4) AS expected_per_drop,
            ld.drop_count_distribution,
            ld.is_guaranteed,
            ld.is_unique,
            ld.is_visible,
            c.object_name AS source_prefab_resource,
            i.resource_name AS item_resource_name
        FROM characters c
        LEFT JOIN loot_drops ld ON c.stable_key = ld.character_stable_key
        INNER JOIN items i ON ld.item_stable_key = i.stable_key
    ),
    combined AS (
        SELECT * FROM consumable_drops
        UNION ALL
        SELECT * FROM character_drops
    )
SELECT
    source_type AS 'Source Type',
    source AS 'Source',
    dropped_item AS 'Dropped Item',
    drop_chance AS 'Drop Chance (%)',
    expected_per_drop AS 'Expected Per Drop',
    drop_count_distribution AS 'Drop Count Distribution',
    is_guaranteed AS 'Is Guaranteed',
    is_unique AS 'Is Unique',
    is_visible AS 'Is Visible',
    source_prefab_resource AS 'Source Prefab/Resource',
    item_resource_name AS 'Item Resource Name'
FROM combined
ORDER BY
    CASE source_type WHEN 'Item' THEN 0 ELSE 1 END,
    source,
    drop_chance DESC;
