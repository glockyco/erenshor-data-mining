WITH
    drops AS (
        SELECT
            c.NPCName AS 'NPC Name',
            i.ItemName AS 'Item Name',
            ROUND(ld.DropProbability, 2) AS 'Drop Chance Per Kill (%)',
            ROUND(ld.ExpectedPerKill, 4) AS 'Expected Per Kill',
            ld.DropCountDistribution,
            ld.IsGuaranteed,
            ld.IsUnique,
            ld.IsVisible,
            c.ObjectName AS 'NPC Prefab Name',
            i.ResourceName AS 'Item Resource Name'
        FROM Characters c
        LEFT JOIN LootDrops ld ON c.StableKey = ld.CharacterStableKey
        INNER JOIN Items i ON ld.ItemStableKey = i.StableKey
        ORDER BY c.NPCName, c.Guid
    )
SELECT * FROM drops
ORDER BY "NPC Name", "NPC Prefab Name", "Drop Chance Per Kill (%)" DESC;
