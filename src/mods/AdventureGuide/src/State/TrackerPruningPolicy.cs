namespace AdventureGuide.State;

/// <summary>Determines whether a tracked quest identity should be removed.</summary>
public static class TrackerPruningPolicy
{
    /// <summary>
    /// Missing guide identities are always pruned. Existing completed quests
    /// are pruned only when they are not repeatable.
    /// </summary>
    public static bool ShouldPrune(bool questExists, bool isCompleted, bool isRepeatable) =>
        !questExists || (isCompleted && !isRepeatable);
}
