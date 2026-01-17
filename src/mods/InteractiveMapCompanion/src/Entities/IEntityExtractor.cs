namespace InteractiveMapCompanion.Entities;

/// <summary>
/// Extracts entity data from a Character.
/// </summary>
public interface IEntityExtractor
{
    /// <summary>
    /// Extracts position, rotation, name, and other data from a character.
    /// </summary>
    /// <param name="character">The character to extract data from.</param>
    /// <param name="entityType">The classified type of the entity.</param>
    /// <returns>Entity data ready for serialization.</returns>
    EntityData Extract(Character character, EntityType entityType);
}
