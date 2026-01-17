namespace InteractiveMapCompanion.Entities;

/// <summary>
/// Finds all Character entities in the current scene.
/// </summary>
public interface IEntityFinder
{
    /// <summary>
    /// Returns all Character components currently in the scene.
    /// </summary>
    IEnumerable<Character> FindAll();
}
