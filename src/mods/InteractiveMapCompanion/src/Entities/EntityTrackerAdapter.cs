namespace InteractiveMapCompanion.Entities;

/// <summary>
/// Production adapter that wires the generic EntityTracker to game types.
/// This is the class registered in the DI container.
/// </summary>
public sealed class EntityTrackerAdapter : IEntityTracker
{
    private readonly EntityTracker<Character> _inner;

    /// <summary>
    /// Creates a new EntityTrackerAdapter with the specified dependencies.
    /// </summary>
    /// <param name="finder">Finds all Characters in the scene.</param>
    /// <param name="classifier">Classifies Characters into EntityTypes.</param>
    /// <param name="extractor">Extracts EntityData from Characters.</param>
    /// <param name="entityFilter">Filter for which entity types to track.</param>
    public EntityTrackerAdapter(
        IEntityFinder finder,
        IEntityClassifier classifier,
        IEntityExtractor extractor,
        Func<EntityType, bool> entityFilter
    )
    {
        _inner = new EntityTracker<Character>(
            findEntities: finder.FindAll,
            classify: classifier.Classify,
            extract: extractor.Extract,
            shouldTrack: entityFilter
        );
    }

    /// <inheritdoc />
    public IReadOnlyList<EntityData> GetTrackedEntities() => _inner.GetTrackedEntities();
}
