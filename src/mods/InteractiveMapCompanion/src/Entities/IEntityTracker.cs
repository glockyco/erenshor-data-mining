namespace InteractiveMapCompanion.Entities;

/// <summary>
/// Tracks entities in the current scene and provides their current state.
/// </summary>
public interface IEntityTracker
{
    /// <summary>
    /// Gets all currently tracked entities.
    /// </summary>
    IReadOnlyList<EntityData> GetTrackedEntities();
}
