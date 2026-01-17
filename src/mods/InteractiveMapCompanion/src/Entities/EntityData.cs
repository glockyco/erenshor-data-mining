namespace InteractiveMapCompanion.Entities;

/// <summary>
/// Represents the current state of a tracked entity.
/// </summary>
/// <param name="Id">Unique instance ID within the session.</param>
/// <param name="EntityType">Classification of the entity.</param>
/// <param name="Name">Display name.</param>
/// <param name="Position">Zone-local coordinates [x, y, z].</param>
/// <param name="Rotation">Facing direction in degrees (0-360).</param>
/// <param name="Level">Entity level (for NPCs).</param>
/// <param name="Rarity">Rarity classification (for enemies): common, rare, unique.</param>
public record EntityData(
    int Id,
    string EntityType,
    string Name,
    float[] Position,
    float Rotation,
    int? Level = null,
    string? Rarity = null
);
