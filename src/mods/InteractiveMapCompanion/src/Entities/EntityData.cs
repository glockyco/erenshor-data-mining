namespace InteractiveMapCompanion.Entities;

/// <summary>
/// Represents the current state of a tracked entity.
/// </summary>
public sealed class EntityData
{
    public int Id { get; }
    public string EntityType { get; }
    public string Name { get; }
    public float[] Position { get; }
    public float Rotation { get; }
    public int? Level { get; }
    public string? Rarity { get; }
    public string? CharacterClass { get; }
    public string? Owner { get; }

    public EntityData(
        int Id,
        string EntityType,
        string Name,
        float[] Position,
        float Rotation,
        int? Level = null,
        string? Rarity = null,
        string? CharacterClass = null,
        string? Owner = null
    )
    {
        this.Id = Id;
        this.EntityType = EntityType;
        this.Name = Name;
        this.Position = Position;
        this.Rotation = Rotation;
        this.Level = Level;
        this.Rarity = Rarity;
        this.CharacterClass = CharacterClass;
        this.Owner = Owner;
    }
}
