-- Drop chances from characters and items (fossils, etc.)
WITH
    -- Item drops from consumables (e.g., Braxonian Fossil)
    item_drops AS (
        SELECT
            'Item' AS SourceType,
            src.ItemName AS Source,
            dropped.ItemName AS DroppedItem,
            ROUND(id.DropProbability, 2) AS DropChance,
            NULL AS ExpectedPerDrop,
            NULL AS DropCountDistribution,
            id.IsGuaranteed,
            0 AS IsUnique,
            0 AS IsVisible,
            src.ResourceName AS SourcePrefabResource,
            dropped.ResourceName AS ItemResourceName
        FROM ItemDrops id
        JOIN Items src ON id.SourceItemStableKey = src.StableKey
        JOIN Items dropped ON id.DroppedItemStableKey = dropped.StableKey
    ),
    -- Character drops
    character_drops AS (
        SELECT
            'Character' AS SourceType,
            c.NPCName AS Source,
            i.ItemName AS DroppedItem,
            ROUND(ld.DropProbability, 2) AS DropChance,
            ROUND(ld.ExpectedPerKill, 4) AS ExpectedPerDrop,
            ld.DropCountDistribution,
            ld.IsGuaranteed,
            ld.IsUnique,
            ld.IsVisible,
            c.ObjectName AS SourcePrefabResource,
            i.ResourceName AS ItemResourceName
        FROM Characters c
        LEFT JOIN LootDrops ld ON c.StableKey = ld.CharacterStableKey
        INNER JOIN Items i ON ld.ItemStableKey = i.StableKey
    ),
    combined AS (
        SELECT * FROM item_drops
        UNION ALL
        SELECT * FROM character_drops
    )
SELECT
    SourceType AS 'Source Type',
    Source,
    DroppedItem AS 'Dropped Item',
    DropChance AS 'Drop Chance (%)',
    ExpectedPerDrop AS 'Expected Per Drop',
    DropCountDistribution,
    IsGuaranteed,
    IsUnique,
    IsVisible,
    SourcePrefabResource AS 'Source Prefab/Resource',
    ItemResourceName AS 'Item Resource Name'
FROM combined
ORDER BY
    CASE SourceType WHEN 'Item' THEN 0 ELSE 1 END,
    Source,
    DropChance DESC;
