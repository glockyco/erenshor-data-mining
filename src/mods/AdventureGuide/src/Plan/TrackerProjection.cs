namespace AdventureGuide.Plan;

/// <summary>
/// Canonical tracker-facing projection for one quest. The tracker later selects
/// the closest actionable frontier candidate from this shared projection.
/// </summary>
public sealed class TrackerProjection
{
    public IReadOnlyList<FrontierRef> Frontier { get; }

    public TrackerProjection(IReadOnlyList<FrontierRef> frontier)
    {
        Frontier = frontier;
    }
}