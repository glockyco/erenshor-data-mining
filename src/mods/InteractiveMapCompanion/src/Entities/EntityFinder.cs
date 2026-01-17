namespace InteractiveMapCompanion.Entities;

/// <summary>
/// Production implementation that finds all Characters using Unity's FindObjectsOfType.
/// </summary>
public sealed class EntityFinder : IEntityFinder
{
    public IEnumerable<Character> FindAll()
    {
        return UnityEngine.Object.FindObjectsOfType<Character>();
    }
}
