namespace InteractiveMapCompanion.Entities;

/// <summary>
/// Generic, testable entity tracker that combines finding, classifying, and extracting entities.
/// Uses delegates to abstract away Unity/game type dependencies.
/// </summary>
/// <typeparam name="TCharacter">The character type (Character in production, mock type in tests).</typeparam>
public sealed class EntityTracker<TCharacter>
    where TCharacter : class
{
    private readonly Func<IEnumerable<TCharacter>> _findEntities;
    private readonly Func<TCharacter, EntityType?> _classify;
    private readonly Func<TCharacter, EntityType, EntityData> _extract;
    private readonly Func<EntityType, bool> _shouldTrack;

    /// <summary>
    /// Creates a new EntityTracker with the specified delegates.
    /// </summary>
    /// <param name="findEntities">Function to find all characters in the current scene.</param>
    /// <param name="classify">Function to classify a character into an EntityType (null = excluded).</param>
    /// <param name="extract">Function to extract EntityData from a character.</param>
    /// <param name="shouldTrack">Filter function to determine which entity types to track.</param>
    public EntityTracker(
        Func<IEnumerable<TCharacter>> findEntities,
        Func<TCharacter, EntityType?> classify,
        Func<TCharacter, EntityType, EntityData> extract,
        Func<EntityType, bool> shouldTrack
    )
    {
        _findEntities = findEntities;
        _classify = classify;
        _extract = extract;
        _shouldTrack = shouldTrack;
    }

    /// <summary>
    /// Gets all currently tracked entities.
    /// Entities are re-scanned and re-classified on each call to reflect current game state.
    /// </summary>
    public IReadOnlyList<EntityData> GetTrackedEntities()
    {
        var results = new List<EntityData>();

        foreach (var character in _findEntities())
        {
            // Classify the character
            var entityType = _classify(character);
            if (entityType == null)
                continue;

            // Check if we should track this type
            if (!_shouldTrack(entityType.Value))
                continue;

            // Extract and add to results
            var data = _extract(character, entityType.Value);
            results.Add(data);
        }

        return results;
    }
}
