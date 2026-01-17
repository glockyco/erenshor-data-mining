namespace InteractiveMapCompanion.Entities;

/// <summary>
/// Determines the EntityType for a Character.
/// </summary>
public interface IEntityClassifier
{
    /// <summary>
    /// Classifies a character into an EntityType.
    /// Returns null if the character should not be tracked (e.g., mining nodes, treasure chests).
    /// </summary>
    EntityType? Classify(Character character);
}
