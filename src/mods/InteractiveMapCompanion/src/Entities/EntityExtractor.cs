namespace InteractiveMapCompanion.Entities;

/// <summary>
/// Production implementation that extracts entity data from game Character objects.
/// </summary>
public sealed class EntityExtractor : IEntityExtractor
{
    public EntityData Extract(Character character, EntityType entityType)
    {
        var transform = character.transform;
        var stats = character.MyStats;

        return new EntityData(
            Id: character.GetInstanceID(),
            EntityType: EntityTypeToString(entityType),
            Name: stats?.MyName ?? character.name,
            Position: [transform.position.x, transform.position.y, transform.position.z],
            Rotation: NormalizeRotation(transform.eulerAngles.y),
            Level: GetLevel(stats, entityType),
            Rarity: GetRarity(character, entityType)
        );
    }

    /// <summary>
    /// Converts EntityType enum to protocol string (snake_case).
    /// </summary>
    private static string EntityTypeToString(EntityType type) =>
        type switch
        {
            EntityType.Player => "player",
            EntityType.SimPlayer => "simplayer",
            EntityType.Pet => "pet",
            EntityType.NpcFriendly => "npc_friendly",
            EntityType.NpcEnemy => "npc_enemy",
            _ => "unknown",
        };

    /// <summary>
    /// Normalizes rotation to 0-360 range.
    /// </summary>
    private static float NormalizeRotation(float degrees)
    {
        degrees %= 360f;
        if (degrees < 0f)
            degrees += 360f;
        return degrees;
    }

    /// <summary>
    /// Gets level for entities that have it.
    /// </summary>
    private static int? GetLevel(Stats? stats, EntityType type)
    {
        // Only include level for NPCs
        if (type is not (EntityType.NpcEnemy or EntityType.NpcFriendly))
            return null;

        return stats?.Level;
    }

    /// <summary>
    /// Gets rarity for enemy NPCs.
    /// Currently only distinguishes boss vs common.
    /// Rare spawn detection requires spawn point context (see #188).
    /// </summary>
    private static string? GetRarity(Character character, EntityType type)
    {
        // Only enemy NPCs have rarity
        if (type != EntityType.NpcEnemy)
            return null;

        // BossXp > 1 indicates a boss (1 is the default for normal mobs)
        if (character.BossXp > 1f)
            return "boss";

        // Default to common; rare detection deferred to #188
        return "common";
    }
}
